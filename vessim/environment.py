from __future__ import annotations

from typing import Optional, Literal

import mosaik  # type: ignore

from vessim.microgrid import Microgrid
from vessim.actor import Actor
from vessim.controller import Controller
from vessim.storage import Storage
from vessim.policy import MicrogridPolicy, DefaultMicrogridPolicy
from vessim._util import Clock, disable_rt_warnings
from vessim.signal import Signal, SilSignal


class Environment:
    COSIM_CONFIG: mosaik.SimConfig = {
        "Actor": {"python": "vessim.actor:_ActorSim"},
        "Controller": {"python": "vessim.controller:_ControllerSim"},
        "Grid": {"python": "vessim.microgrid:_GridSim"},
        "Storage": {"python": "vessim.storage:_StorageSim"},
    }

    def __init__(self, sim_start, step_size: int = 1):
        self.clock = Clock(sim_start)
        self.step_size = step_size
        self.microgrids: list[Microgrid] = []
        self.controllers: list[Controller] = []  # Track controllers at environment level
        self.world = mosaik.World(self.COSIM_CONFIG, skip_greetings=True)

    def add_microgrid(
        self,
        actors: list[Actor],
        policy: Optional[MicrogridPolicy] = None,
        storage: Optional[Storage] = None,
        grid_signals: Optional[dict[str, Signal]] = None,
        name: Optional[str] = None,
    ):
        if not actors:
            raise ValueError("There should be at least one actor in the Microgrid.")

        microgrid = Microgrid(
            world=self.world,
            clock=self.clock,
            step_size=self.step_size,
            actors=actors,
            policy=policy if policy is not None else DefaultMicrogridPolicy(),
            storage=storage,
            grid_signals=grid_signals,
            name=name,
        )
        self.microgrids.append(microgrid)
        return microgrid

    def add_controller(self, controller: Controller):
        """Add a controller to the environment.

        Args:
            controller: The controller instance (already initialized with microgrids)
        """
        if controller not in self.controllers:
            self.controllers.append(controller)

        # Validate that all microgrids are part of this environment
        for microgrid in controller.microgrids.values():
            if microgrid not in self.microgrids:
                raise ValueError(f"Microgrid '{microgrid.name}' is not part of this environment")

    def _initialize_controllers(self):
        """Initialize all controllers after all microgrids have been added."""
        for controller in self.controllers:

            # Create controller simulator
            controller_sim = self.world.start(
                "Controller",
                sim_id=controller.name,
                clock=self.clock,
                step_size=self.step_size,
            )
            controller_entity = controller_sim.Controller(
                controller=controller, microgrid_names=list(controller.microgrids.keys())
            )

            # Connect controller to all managed microgrids
            for microgrid in controller.microgrids.values():
                # Connect to grid for p_delta
                self.world.connect(microgrid.grid_entity, controller_entity, "p_delta")
                self.world.connect(microgrid.grid_entity, controller_entity, "grid_signals")

                # Connect to actors for state
                for actor_name, actor_entity in microgrid.actor_entities.items():
                    self.world.connect(
                        actor_entity,
                        controller_entity,
                        ("state", "actor_states"),
                    )

                # Connect to storage for set_parameters and state/energy feedback
                self.world.connect(controller_entity, microgrid.storage_entity, "set_parameters")
                self.world.connect(
                    microgrid.storage_entity,
                    controller_entity,
                    "p_grid",
                    time_shifted=True,
                    initial_data={"p_grid": 0.0},
                )
                self.world.connect(
                    microgrid.storage_entity,
                    controller_entity,
                    "policy_state",
                    time_shifted=True,
                    initial_data={"policy_state": microgrid.policy.state()},
                )
                if microgrid.storage:
                    self.world.connect(
                        microgrid.storage_entity,
                        controller_entity,
                        "storage_state",
                        time_shifted=True,
                        initial_data={"storage_state": microgrid.storage.state()},
                    )

    def run(
        self,
        until: Optional[int] = None,
        rt_factor: Optional[float] = None,
        print_progress: bool | Literal["individual"] = True,
        behind_threshold: float = float("inf"),
    ):
        if until is None:
            # there is no integer representing infinity in python
            until = float("inf")  # type: ignore
        assert until is not None

        # Initialize controllers before running simulation
        self._initialize_controllers()

        # Check if SiL actors are present and fail if the simulation is not in real-time mode
        if self._contains_sil_signals() and rt_factor is None:
            raise RuntimeError(
                "SiL actors detected but not running in real-time mode. "
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
        """Check if any microgrid contains SiL actors."""
        for microgrid in self.microgrids:
            for actor in microgrid.actors:
                if isinstance(actor.signal, SilSignal):
                    return True
        return False
