from __future__ import annotations

from copy import copy
from typing import Optional, Literal

import mosaik  # type: ignore
import mosaik_api_v3  # type: ignore

from vessim.actor import Actor, SilActor
from vessim.controller import Controller
from vessim.storage import Storage
from vessim.policy import MicrogridPolicy, DefaultMicrogridPolicy
from vessim._util import Clock, disable_rt_warnings


class Microgrid:
    def __init__(
        self,
        world: mosaik.World,
        clock: Clock,
        actors: list[Actor],
        policy: MicrogridPolicy,
        storage: Optional[Storage] = None,
        step_size: int = 1,  # global default
        name: Optional[str] = None,
    ):
        self.name = name or f"microgrid_{id(self)}"
        self.actors = actors
        self.policy = policy
        self.storage = storage
        self.step_size = step_size

        self.actor_entities = {}
        for actor in actors:
            actor_step_size = actor.step_size if actor.step_size else step_size
            if actor_step_size % step_size != 0:
                raise ValueError("Actor step size has to be a multiple of grids step size.")
            actor_sim = world.start(
                "Actor",
                sim_id=f"{self.name}.actor.{actor.name}",
                clock=clock,
                step_size=actor_step_size,
            )
            # We initialize all actors before the grid simulation to make sure that
            # there is already a valid p_delta at step 0
            self.actor_entities[actor.name] = actor_sim.Actor(actor=actor)

        grid_sim = world.start("Grid", sim_id=f"{self.name}.grid", step_size=step_size)
        self.grid_entity = grid_sim.Grid()
        for actor_name, actor_entity in self.actor_entities.items():
            world.connect(actor_entity, self.grid_entity, "p")

        storage_sim = world.start("Storage", sim_id=f"{self.name}.storage", step_size=step_size)
        self.storage_entity = storage_sim.Storage(storage=storage, policy=policy)
        world.connect(self.grid_entity, self.storage_entity, "p_delta")

    def finalize(self):
        """Clean up in case the simulation was interrupted.

        Mosaik already has a cleanup functionality but this is an additional safety net
        in case the user interrupts the simulation before entering the mosiak event loop.
        """
        for actor in self.actors:
            actor.finalize()


class Environment:
    COSIM_CONFIG: mosaik.SimConfig = {
        "Actor": {"python": "vessim.actor:_ActorSim"},
        "Controller": {"python": "vessim.controller:_ControllerSim"},
        "Grid": {"python": "vessim.cosim:_GridSim"},
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
        storage: Optional[Storage] = None,
        policy: Optional[MicrogridPolicy] = None,
        name: Optional[str] = None,
    ):
        if not actors:
            raise ValueError("There should be at least one actor in the Microgrid.")

        microgrid = Microgrid(
            self.world,
            self.clock,
            actors,
            policy if policy is not None else DefaultMicrogridPolicy(),
            storage,
            self.step_size,
            name,
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
                controller=controller,
                microgrid_names=list(controller.microgrids.keys())
            )

            # Connect controller to all managed microgrids
            for microgrid in controller.microgrids.values():
                # Connect to grid for p_delta
                self.world.connect(microgrid.grid_entity, controller_entity, "p_delta")

                # Connect to actors for state
                for actor_name, actor_entity in microgrid.actor_entities.items():
                    self.world.connect(
                        actor_entity,
                        controller_entity,
                        ("state", "actor_state"),
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
        if self._has_sil_actors() and rt_factor is None:
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

    def _has_sil_actors(self) -> bool:
        """Check if any microgrid contains SiL actors."""
        for microgrid in self.microgrids:
            for actor in microgrid.actors:
                if isinstance(actor, SilActor):
                    return True
        return False


class _GridSim(mosaik_api_v3.Simulator):
    META = {
        "type": "time-based",
        "models": {
            "Grid": {
                "public": True,
                "params": [],
                "attrs": ["p", "p_delta"],
            },
        },
    }

    def __init__(self):
        super().__init__(self.META)
        self.eid = "Grid"
        self.step_size = None
        self.p_delta = 0.0

    def init(self, sid, time_resolution=1.0, **sim_params):
        self.step_size = sim_params["step_size"]
        return self.meta

    def create(self, num, model, **model_params):
        assert num == 1, "Only one instance per simulation is supported"
        return [{"eid": self.eid, "type": model}]

    def step(self, time, inputs, max_advance):
        self.p_delta = sum(inputs[self.eid]["p"].values())
        assert self.step_size is not None
        return time + self.step_size

    def get_data(self, outputs):
        return {self.eid: {"p_delta": self.p_delta}}
