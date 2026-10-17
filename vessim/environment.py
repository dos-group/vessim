from __future__ import annotations

import math
import time
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any, Literal, Optional, TypeVar

import pandas as pd
from loguru import logger

from vessim._runtime import RunResult, Runtime
from vessim.actor import Actor
from vessim.controller import Controller
from vessim.dispatch_policy import DispatchPolicy, DefaultDispatchPolicy
from vessim.dispatchable import Dispatchable
from vessim.microgrid import Microgrid
from vessim.signal import Signal, SilSignal

ControllerT = TypeVar("ControllerT", bound=Controller)


class Environment:
    """Run a simulation study or a live experiment using shared component models.

    An environment runs once. Construct a fresh environment and mutable models
    for each scenario; immutable traces can be reused. Use as a context manager
    when setup may acquire live resources or start external simulators.

    Args:
        sim_start: Timestamp labeling tick zero; required for studies.
        step_size: Positive integer tick interval in seconds.
        name: Optional experiment name.
        backend: ``native`` (default) or ``mosaik`` for external coupling.
        sim_config: Additional mosaik simulator configurations. Only accepted
            with backend="mosaik"; the name "Vessim" is reserved.
    """

    def __init__(
        self,
        sim_start: Optional[str | datetime] = None,
        step_size: int = 1,
        name: Optional[str] = None,
        *,
        backend: Literal["native", "mosaik"] = "native",
        sim_config: Optional[dict] = None,
        _live: bool = False,
        _behind_threshold: float = 5.0,
    ):
        if not _live and sim_start is None:
            raise ValueError(
                "sim_start is required for studies. Use Environment.live() for live runs."
            )
        if isinstance(step_size, bool) or not isinstance(step_size, int) or step_size <= 0:
            raise ValueError("step_size must be a positive integer number of seconds.")
        if backend not in ("native", "mosaik"):
            raise ValueError("backend must be 'native' or 'mosaik'.")
        if sim_config is not None and backend != "mosaik":
            raise ValueError("sim_config requires backend='mosaik'.")
        if sim_config and "Vessim" in sim_config:
            raise ValueError("The simulator name 'Vessim' is reserved.")
        if not math.isfinite(_behind_threshold) or _behind_threshold < 0:
            raise ValueError("behind_threshold must be finite and nonnegative.")
        self.sim_start = pd.Timestamp(sim_start) if sim_start is not None else None
        if self.sim_start is not None and pd.isna(self.sim_start):
            raise ValueError("sim_start must be a valid timestamp.")
        self.step_size = step_size
        self.name = name
        self.backend = backend
        self.is_live = _live
        self.behind_threshold = _behind_threshold
        self.microgrids: dict[str, Microgrid] = {}
        self.controllers: list[Controller] = []
        self.status = "created"
        self.until = 0.0
        self.result: Optional[RunResult] = None
        self._sim_config = dict(sim_config or {})
        self._mosaik: Any = None
        self._runtime: Optional[Runtime] = None
        self._started_controllers: list[Controller] = []
        self._closed = False

    @classmethod
    def live(
        cls,
        sim_start: Optional[str | datetime] = None,
        step_size: int = 1,
        behind_threshold: float = 5.0,
        name: Optional[str] = None,
        *,
        backend: Literal["native", "mosaik"] = "native",
        sim_config: Optional[dict] = None,
    ) -> Environment:
        """Create a wall-clock-paced experiment with either backend.

        ``sim_start`` labels output; signals receive elapsed seconds from tick
        zero. When omitted, the label is captured when run() starts. Lateness
        is reported after ``behind_threshold`` seconds, without skipping ticks.
        """
        return cls(
            sim_start,
            step_size,
            name,
            backend=backend,
            sim_config=sim_config,
            _live=True,
            _behind_threshold=behind_threshold,
        )

    def _require_setup(self) -> None:
        if self._closed or self.status != "created":
            raise RuntimeError(
                "The scenario is frozen after prepare() or run(); create a new one."
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
        """Add models without creating any backend entities.

        An empty actor list is supported only with mosaik, for microgrids fed
        entirely by external power measurements. Names default to microgrid_0,
        microgrid_1, etc. and must be unique within this environment.
        """
        self._require_setup()
        if not actors and self.backend != "mosaik":
            raise ValueError("There should be at least one actor in a native Microgrid.")
        name = name if name is not None else f"microgrid_{len(self.microgrids)}"
        if not isinstance(name, str) or not name:
            raise ValueError("Microgrid names must be nonempty strings.")
        if name in self.microgrids:
            raise ValueError(f"A microgrid named '{name}' already exists in this environment.")
        grid = Microgrid(
            self.step_size,
            actors,
            dispatchables or [],
            policy if policy is not None else DefaultDispatchPolicy(),
            grid_signals,
            name,
            coords,
        )
        self.microgrids[name] = grid
        return grid

    def add_controller(self, controller: ControllerT) -> ControllerT:
        """Register a controller in execution order and return it for result access."""
        self._require_setup()
        if any(c is controller for c in self.controllers):
            raise ValueError("A controller instance can only be registered once.")
        self.controllers.append(controller)
        return controller

    def _mosaik_backend(self):
        if self.backend != "mosaik":
            raise RuntimeError("External simulator coupling requires backend='mosaik'.")
        if self._closed:
            raise RuntimeError("This environment is closed.")
        if self._mosaik is None:
            from vessim._mosaik import MosaikBackend

            self._mosaik = MosaikBackend(self._sim_config)
        return self._mosaik

    @property
    def world(self) -> Any:
        """The mosaik World for starting and connecting external simulators.

        Only available with backend="mosaik". Call environment.run(), not
        world.run(), so Vessim initialization, pacing and cleanup are applied.
        """
        return self._mosaik_backend().world

    @property
    def entities(self) -> dict[str, Any]:
        """Microgrid name to mosaik entity, available after prepare()."""
        backend = self._mosaik_backend()
        if self._runtime is None:
            raise RuntimeError("Call prepare() before accessing mosaik entities.")
        return dict(backend.entities)

    def prepare(self) -> None:
        """Validate and freeze the scenario, registering mosaik entities if needed.

        run() calls this automatically. Call it explicitly to connect external
        simulators to ``entities`` before running. Controllers start at run(),
        after all connections have been established.
        """
        if self.status == "prepared" and not self._closed:
            return
        self._require_setup()
        if not self.microgrids:
            raise ValueError("Add at least one microgrid before running.")
        seen: set[int] = set()
        for grid in self.microgrids.values():
            grid._validate()
            for component in [*grid.actors, *grid.dispatchables, grid.policy]:
                if id(component) in seen:
                    raise ValueError(
                        "Mutable actors, dispatchables and policies cannot be shared "
                        "between microgrids; only signals may be shared."
                    )
                seen.add(id(component))
        if self._contains_sil_signals() and not self.is_live:
            raise RuntimeError("SiL signals detected. Use Environment.live() for live inputs.")
        self._runtime = Runtime(self)
        if self.backend == "mosaik":
            self._mosaik_backend().prepare(self._runtime)
        self.status = "prepared"

    def _end_time(self, until: Optional[timedelta | datetime | int | float]) -> float:
        if until is None:
            if not self.is_live:
                raise ValueError("Simulation studies require a finite until horizon.")
            return math.inf
        if isinstance(until, timedelta):
            end = until.total_seconds()
        elif isinstance(until, datetime):
            assert self.sim_start is not None
            end = (pd.Timestamp(until) - self.sim_start).total_seconds()
        else:
            if isinstance(until, bool) or not isinstance(until, (int, float)):
                raise TypeError("until must be elapsed seconds, timedelta, datetime, or None.")
            end = float(until)
        if not math.isfinite(end) or end < 0:
            raise ValueError("until must be finite and nonnegative (at or after sim_start).")
        return end

    def run(
        self,
        until: Optional[timedelta | datetime | int | float] = None,
        print_progress: bool | Literal["individual"] = False,
    ) -> RunResult:
        """Run once up to a horizon and return the state at that horizon.

        ``until`` accepts elapsed seconds, a timedelta, or an absolute datetime.
        Ticks are exclusive of ``until``. Dispatch and integration cover the
        entire duration, including a partial final interval. No additional
        controller call or signal sample occurs at the horizon.
        Only live runs may omit it. No trajectory is retained unless a logger
        is added. All owned resources are finalized on success or failure.
        Native progress supports True/False; 'individual' requires mosaik.
        """
        if self._closed or self.status not in ("created", "prepared"):
            raise RuntimeError("An Environment can only run once; create a fresh scenario.")
        started = time.perf_counter()
        failure = None
        try:
            if self.sim_start is None:
                self.sim_start = pd.Timestamp(datetime.now())
            self.until = self._end_time(until)
            if print_progress not in (False, True, "individual"):
                raise ValueError("print_progress must be True, False or 'individual'.")
            if self.backend == "native" and print_progress == "individual":
                raise ValueError("Individual simulator progress requires backend='mosaik'.")
            self.prepare()
            assert self._runtime is not None
            self.status = "running"
            for controller in self.controllers:
                self._started_controllers.append(controller)
                controller.start(self)
            self._runtime.started = time.monotonic()
            if self.backend == "mosaik":
                self._mosaik.run(self.until, self.is_live, print_progress)
            else:
                from vessim._native import run

                run(self._runtime, self.until, bool(print_progress))
            if math.isfinite(self.until):
                self._runtime.pace(self.until)
                self._runtime.finish(self.until)
            self.result = self._runtime.result(time.perf_counter() - started)
            self.status = "completed"
        except BaseException as exc:
            failure = exc
            self.status = "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"
            raise
        finally:
            try:
                self.close()
            except BaseException:
                if failure is None:
                    self.status = "failed"
                    raise
                logger.exception("Cleanup also failed; preserving the original simulation error")
        assert self.result is not None
        self.result = replace(self.result, wall_time=time.perf_counter() - started)
        return self.result

    def _contains_sil_signals(self) -> bool:
        return any(
            isinstance(signal, SilSignal)
            for grid in self.microgrids.values()
            for signal in [*(a.signal for a in grid.actors), *(grid.grid_signals or {}).values()]
        )

    def close(self) -> None:
        """Release owned resources once, including when setup never reached run().

        Every cleanup is attempted even if another fails. The first cleanup
        error is raised; an existing run error takes precedence in run().
        """
        if self._closed:
            return
        self._closed = True
        errors: list[BaseException] = []
        callbacks = [c.finalize for c in self._started_controllers]
        seen: set[int] = set()
        actor_signals: set[int] = set()
        for grid in self.microgrids.values():
            for actor in grid.actors:
                actor_signals.add(id(actor.signal))
                if id(actor) not in seen:
                    callbacks.append(actor.finalize)
                    seen.add(id(actor))
        for grid in self.microgrids.values():
            for signal in (grid.grid_signals or {}).values():
                if id(signal) not in actor_signals:
                    callbacks.append(signal.finalize)
                    actor_signals.add(id(signal))
        if self._mosaik is not None:
            callbacks.append(self._mosaik.close)
        for callback in callbacks:
            try:
                callback()
            except BaseException as exc:
                errors.append(exc)
        if self.status in ("created", "prepared"):
            self.status = "closed"
        if errors and self.status not in ("failed", "interrupted"):
            self.status = "failed"
        # Recorders collect metrics during finalize(), but must publish only after
        # every controller, signal, and backend has had its cleanup attempted.
        from vessim.recorder import Recorder

        recorders = [c for c in self._started_controllers if isinstance(c, Recorder)]
        publication_failed = False
        for recorder in recorders:
            try:
                recorder._complete()
            except BaseException as exc:
                errors.append(exc)
                publication_failed = True
        if publication_failed:
            if self.status != "interrupted":
                self.status = "failed"
            # A later writer can fail after another has published. Synchronize
            # every result and retry publication of the final failure status.
            for recorder in recorders:
                try:
                    recorder._complete()
                except BaseException:
                    pass  # Preserve the first error; all writers were attempted.
        if errors:
            raise errors[0]

    def __enter__(self) -> Environment:
        """Own resources acquired during scenario setup and execution."""
        if self._closed:
            raise RuntimeError("This environment is closed.")
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        """Close even if setup or execution was interrupted."""
        try:
            self.close()
        except BaseException:
            if exc is None:
                raise
            logger.exception("Cleanup failed while leaving an environment with an active error")
