from __future__ import annotations

from datetime import datetime
from typing import Optional, Literal

import mosaik  # type: ignore
from loguru import logger

from vessim._util import Clock, disable_rt_warnings
from vessim.actor import Actor
from vessim.controller import Controller
from vessim.dispatch_policy import DispatchPolicy, DefaultDispatchPolicy
from vessim.dispatchable import Dispatchable
from vessim.microgrid import Microgrid
from vessim.signal import Signal, SilSignal


class Environment:
    """Environment for a Vessim co-simulation.

    This class manages the simulation time, the interaction between different components,
    and the execution of the [Mosaik](https://mosaik.offis.de/) co-simulation.

    Args:
        sim_start: The start time of the simulation. Can be a `datetime` object or a
            string in the format "YYYY-MM-DD HH:MM:SS".
        step_size: The step size of the simulation in seconds. Defaults to 1.
    """

    COSIM_CONFIG: mosaik.SimConfig = {
        "Actor": {"python": "vessim.actor:_ActorSim"},
        "Controller": {"python": "vessim.controller:_ControllerSim"},
        "Grid": {"python": "vessim.microgrid:_GridSim"},
        "Dispatch": {"python": "vessim.dispatchable:_DispatchSim"},
    }

    def __init__(self, sim_start: str | datetime, step_size: int = 1, name: Optional[str] = None):
        self.clock = Clock(sim_start)
        self.step_size = step_size
        self.name = name
        self.microgrids: list[Microgrid] = []
        self.controllers: list[Controller] = []
        self.world = mosaik.World(self.COSIM_CONFIG, skip_greetings=True)

    def add_microgrid(
        self,
        actors: list[Actor],
        dispatch: Optional[Dispatchable | list[Dispatchable]] = None,
        policy: Optional[DispatchPolicy] = None,
        grid_signals: Optional[dict[str, Signal]] = None,
        name: Optional[str] = None,
        coords: Optional[tuple[float, float]] = None,
    ) -> Microgrid:
        """Add a microgrid to the environment.

        Args:
            actors: A list of exogenous actors (consumers/producers) in the microgrid.
            dispatch: Optional dispatchable resource(s) (e.g., batteries, generators).
                Can be a single `Dispatchable` or a list.
            policy: The dispatch policy that controls energy management. If None, a
                `DefaultDispatchPolicy` is used.
            grid_signals: Optional signals from the public grid (e.g., carbon intensity).
            name: An optional name for the microgrid.
            coords: Optional coordinates (latitude, longitude) for the microgrid.

        Returns:
            The created `Microgrid` instance.
        """
        if not actors:
            raise ValueError("There should be at least one actor in the Microgrid.")

        # Normalize dispatch to a list
        if dispatch is None:
            dispatchables = []
        elif isinstance(dispatch, Dispatchable):
            dispatchables = [dispatch]
        else:
            dispatchables = list(dispatch)

        microgrid = Microgrid(
            world=self.world,
            clock=self.clock,
            step_size=self.step_size,
            actors=actors,
            dispatchables=dispatchables,
            policy=policy if policy is not None else DefaultDispatchPolicy(),
            grid_signals=grid_signals,
            name=name,
            coords=coords,
        )
        self.microgrids.append(microgrid)
        return microgrid

    def add_controller(self, controller: Controller):
        """Add a controller to the environment.

        Args:
            controller: The controller instance.
        """
        self.controllers.append(controller)

    def _initialize_controllers(self):
        """Initialize all controllers after all microgrids have been added."""
        if not self.controllers:
            return

        # Execute start() method on all controllers
        for controller in self.controllers:
            controller.start(self)

        # Create one global controller simulator
        controller_sim = self.world.start(
            "Controller",
            clock=self.clock,
            step_size=self.step_size,
        )
        controller_entity = controller_sim.Controller(controllers=self.controllers)

        # Connect global controller to all microgrids
        for microgrid in self.microgrids:
            # Connect to grid for p_delta
            self.world.connect(microgrid.grid_entity, controller_entity, "p_delta")
            self.world.connect(microgrid.grid_entity, controller_entity, "grid_signals")

            # Connect to actors for state
            for actor_entity in microgrid.actor_entities.values():
                self.world.connect(
                    actor_entity,
                    controller_entity,
                    ("state", "actor_states"),
                )

            # Connect to dispatch for state/energy feedback
            self.world.connect(
                microgrid.dispatch_entity,
                controller_entity,
                "p_grid",
                time_shifted=True,
                initial_data={"p_grid": 0.0},
            )
            self.world.connect(
                microgrid.dispatch_entity,
                controller_entity,
                "policy_state",
                time_shifted=True,
                initial_data={"policy_state": microgrid.policy.state()},
            )
            if microgrid.dispatchables:
                self.world.connect(
                    microgrid.dispatch_entity,
                    controller_entity,
                    "dispatch_states",
                    time_shifted=True,
                    initial_data={
                        "dispatch_states": {d.name: d.state() for d in microgrid.dispatchables}
                    },
                )

    def run(
        self,
        until: Optional[int] = None,
        rt_factor: Optional[float] = None,
        print_progress: bool | Literal["individual"] = True,
        behind_threshold: float = float("inf"),
    ):
        """Run the simulation.

        Args:
            until: The end time of the simulation in seconds. If None, the simulation
                runs indefinitely.
            rt_factor: The real-time factor. 1.0 means the simulation runs in real-time.
                0.5 means it runs twice as fast as real-time. If None, the simulation
                runs as fast as possible.
            print_progress: Whether to print a progress bar.
            behind_threshold: The threshold in seconds for issuing warnings when the
                simulation falls behind real-time (only used if `rt_factor` is set).
        """
        if until is None:
            until = float("inf")  # type: ignore
        assert until is not None

        # Initialize controllers before running simulation
        if self.name:
            logger.info(f"Experiment: {self.name}")
        self._initialize_controllers()

        # Check if SiL signals are present and fail if the simulation is not in real-time mode
        if self._contains_sil_signals() and rt_factor is None:
            raise RuntimeError(
                "SiL signals detected but not running in real-time mode. "
                "Use rt_factor > 0 for real-time simulation."
            )

        if rt_factor:
            disable_rt_warnings(behind_threshold)
        try:
            self.world.run(until=until, rt_factor=rt_factor, print_progress=print_progress)
        except Exception:
            for microgrid in self.microgrids:
                microgrid.finalize()
            raise

    def _contains_sil_signals(self) -> bool:
        """Check if any microgrid contains SiL signals."""
        for microgrid in self.microgrids:
            for actor in microgrid.actors:
                if isinstance(actor.signal, SilSignal):
                    return True
        return False
