from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional, Literal

import mosaik  # type: ignore
import pandas as pd
from loguru import logger

from vessim._util import disable_rt_warnings
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

    Two modes are supported:

    - **Simulated** — `Environment(sim_start=..., step_size=...)`. The simulation
      clock advances as fast as possible, anchored at the explicit `sim_start`.
    - **Live** — `Environment.live(step_size=...)`. The simulation clock tracks
      wall-clock time and `sim_start` is captured when `run()` is called (i.e.
      defaults to "now at the moment of running"). Use this when mixing in
      `SilSignal`s.

    Args:
        sim_start: The start time of the simulation. Can be a `datetime` object or a
            string in the format "YYYY-MM-DD HH:MM:SS".
        step_size: The step size of the simulation in seconds. Defaults to 1.
    """

    COSIM_CONFIG: mosaik.SimConfig = {
        "Actor": {"python": "vessim.actor:_ActorSim"},
        "Controller": {"python": "vessim.controller:_ControllerSim"},
        "Microgrid": {"python": "vessim.microgrid:_MicrogridSim"},
    }

    def __init__(
        self,
        sim_start: Optional[str | datetime] = None,
        step_size: int = 1,
        name: Optional[str] = None,
        _live: bool = False,
        _behind_threshold: float = 5.0,
    ):
        if not _live and sim_start is None:
            raise ValueError(
                "sim_start is required for simulated mode. "
                "Use Environment.live(...) for real-time experiments."
            )
        self.sim_start: pd.Timestamp | None = (
            pd.to_datetime(sim_start) if sim_start is not None else None
        )
        self.step_size = step_size
        self.name = name
        self.microgrids: dict[str, Microgrid] = {}
        self.controllers: list[Controller] = []
        self.world = mosaik.World(self.COSIM_CONFIG, skip_greetings=True)
        self._live = _live
        self._behind_threshold = _behind_threshold
        self._started = False

    @classmethod
    def live(
        cls,
        step_size: int = 1,
        behind_threshold: float = 5.0,
        name: Optional[str] = None,
    ) -> "Environment":
        """Create an environment that advances in real-time (1× wall-clock).

        The simulation clock is anchored at `datetime.now()` the moment `run()`
        is called, so traces start replaying from "now" and SiL signals stay in
        sync with wall-clock time.

        Args:
            step_size: Step size in seconds. Defaults to 1.
            behind_threshold: Seconds the simulation may fall behind real-time before
                a warning is logged. Defaults to 5.
            name: Optional name for the environment.
        """
        return cls(
            sim_start=None,
            step_size=step_size,
            name=name,
            _live=True,
            _behind_threshold=behind_threshold,
        )

    def add_microgrid(
        self,
        actors: list[Actor],
        dispatchables: Optional[list[Dispatchable]] = None,
        policy: Optional[DispatchPolicy] = None,
        grid_signals: Optional[dict[str, Signal]] = None,
        name: Optional[str] = None,
        coords: Optional[tuple[float, float]] = None,
    ) -> Microgrid:
        """Add a microgrid to the environment.

        Args:
            actors: A list of exogenous actors (consumers/producers) in the microgrid.
            dispatchables: Optional list of dispatchable resources (e.g., batteries,
                generators).
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

        microgrid = Microgrid(
            world=self.world,
            step_size=self.step_size,
            actors=actors,
            dispatchables=dispatchables or [],
            policy=policy if policy is not None else DefaultDispatchPolicy(),
            grid_signals=grid_signals,
            name=name,
            coords=coords,
        )
        if microgrid.name in self.microgrids:
            raise ValueError(
                f"A microgrid named '{microgrid.name}' already exists in this environment."
            )
        self.microgrids[microgrid.name] = microgrid
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
            sim_start=self.sim_start,
            step_size=self.step_size,
        )
        controller_entity = controller_sim.Controller(controllers=self.controllers)

        # Connect global controller to all microgrids
        for microgrid in self.microgrids.values():
            self.world.connect(microgrid.entity, controller_entity, "p_delta")
            self.world.connect(microgrid.entity, controller_entity, "grid_signals")
            self.world.connect(microgrid.entity, controller_entity, "p_grid")
            self.world.connect(microgrid.entity, controller_entity, "policy_state")
            if microgrid.dispatchables:
                self.world.connect(
                    microgrid.entity, controller_entity, "dispatch_states"
                )

            # Connect actors for state
            for actor_entity in microgrid.actor_entities.values():
                self.world.connect(
                    actor_entity,
                    controller_entity,
                    ("state", "actor_states"),
                )

    def start(self) -> None:
        """Build the simulation without advancing time.

        Wires up controllers, validates SiL signals, and anchors `sim_start`
        in live mode. Call this before `advance()` when driving the simulation
        stepwise from an external loop. The one-shot `run()` calls it for you.
        """
        if self._started:
            raise RuntimeError("Environment.start() has already been called.")

        # Live mode: anchor sim_start to "now" if the user didn't pin one explicitly.
        if self._live and self.sim_start is None:
            self.sim_start = pd.to_datetime(datetime.now())

        if self.name:
            logger.info(f"Experiment: {self.name}")
        self._initialize_controllers()

        # SiL signals require live mode (otherwise they'd be polled out of sync
        # with simulated time).
        if self._contains_sil_signals() and not self._live:
            raise RuntimeError(
                "SiL signals detected but not running in live mode. "
                "Use Environment.live(...) instead of Environment(...)."
            )

        if self._live:
            disable_rt_warnings(self._behind_threshold)

        self._started = True

    def advance(
        self,
        until: timedelta | datetime | int | float,
        print_progress: bool | Literal["individual"] = True,
    ) -> None:
        """Advance the simulation up to elapsed time `until`.

        Can be called repeatedly with monotonically increasing values to drive
        the simulation stepwise from an external loop (e.g. an FL training
        round). Requires `start()` to have been called first.

        Args:
            until: When to advance to. Accepts:

                - `int` or `float` — elapsed seconds since `sim_start`.
                - `timedelta` — elapsed time since `sim_start`.
                - `datetime` — absolute wall-clock end (resolved against `sim_start`).
            print_progress: Whether to print a progress bar.
        """
        if not self._started:
            raise RuntimeError(
                "Call Environment.start() before advance(), or use run() instead."
            )

        if isinstance(until, timedelta):
            until = until.total_seconds()
        elif isinstance(until, datetime):
            assert self.sim_start is not None
            until = (pd.to_datetime(until) - self.sim_start).total_seconds()
            if until < 0:
                raise ValueError("`until` must be after `sim_start`.")

        rt_factor = 1.0 if self._live else None
        try:
            self.world.run(until=until, rt_factor=rt_factor, print_progress=print_progress)
        except Exception:
            for microgrid in self.microgrids.values():
                microgrid.finalize()
            raise

    def run(
        self,
        until: Optional[timedelta | datetime | int | float] = None,
        print_progress: bool | Literal["individual"] = True,
    ):
        """Run the simulation in one shot.

        Convenience wrapper for `start()` followed by `advance(until)`. For
        stepwise control (e.g. driving Vessim from an external simulator),
        call `start()` and `advance()` directly.

        Args:
            until: When the simulation should end. Accepts:

                - `int` or `float` — elapsed seconds since `sim_start`.
                - `timedelta` — elapsed time since `sim_start`.
                - `datetime` — absolute wall-clock end (resolved against `sim_start`).
                - `None` — run indefinitely.
            print_progress: Whether to print a progress bar.
        """
        self.start()
        self.advance(
            until if until is not None else float("inf"),
            print_progress=print_progress,
        )

    def _contains_sil_signals(self) -> bool:
        """Check if any microgrid contains SiL signals."""
        for microgrid in self.microgrids.values():
            for actor in microgrid.actors:
                if isinstance(actor.signal, SilSignal):
                    return True
        return False
