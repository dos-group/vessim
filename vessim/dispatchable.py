from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional

import mosaik_api_v3
import numpy as np
from loguru import logger

if TYPE_CHECKING:
    from vessim.dispatch_policy import DispatchPolicy


class Dispatchable(ABC):
    """Abstract base class for dispatchable energy resources.

    Dispatchables are energy resources whose power output can be controlled by a
    dispatch policy (e.g., batteries, diesel generators, gas turbines).

    Args:
        name: The name of the dispatchable.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self.current_power: float = 0.0

    def set_power(self, power: float, duration: int) -> None:
        """Set the power setpoint for the given duration.

        Raises:
            ValueError: If power is outside the feasible range.
        """
        lo, hi = self.feasible_range(duration)
        if power < lo or power > hi:
            raise ValueError(
                f"Power {power} W is outside feasible range [{lo}, {hi}] W "
                f"for '{self.name}' with duration {duration}s."
            )
        self.current_power = power

    @abstractmethod
    def feasible_range(self, duration: int) -> tuple[float, float]:
        """Returns the (min, max) power achievable for the given timestep duration.

        Args:
            duration: Duration of the timestep in seconds.

        Returns:
            (min_power, max_power) tuple. Negative values indicate discharging/generation,
            positive values indicate charging/consumption.
        """

    @abstractmethod
    def step(self, duration: int) -> None:
        """Update internal state after a timestep has elapsed.

        Args:
            duration: Duration of the timestep in seconds.
        """

    @abstractmethod
    def config(self) -> dict:
        """Returns the static configuration parameters of the dispatchable.

        These are parameters that are fixed at construction time and do not change
        during the simulation (e.g. capacity, C-rate). Used for experiment metadata.
        """

    @abstractmethod
    def state(self) -> dict:
        """Returns the dynamic state of the dispatchable at the current timestep.

        These are values that change during the simulation (e.g. SoC, charge level).
        Used for time-series logging.
        """


# TODO: Document units consistently across the API (Wh for capacity, W for power).


class Storage(Dispatchable):
    """Abstract base class for energy storage devices.

    Storage is a `Dispatchable` that can both absorb and release energy, and
    tracks its state-of-charge (SoC).

    Args:
        name: The name of the storage device.
    """

    @abstractmethod
    def soc(self) -> float:
        """Returns the state-of-charge (SoC) of the storage (0 to 1)."""


class SimpleBattery(Storage):
    """Simple battery model.

    Args:
        name: The name of the battery.
        capacity: Battery's energy capacity in Wh.
        initial_soc: Initial battery state-of-charge (SoC). Has to be between 0 and 1.
            Defaults to 0.
        min_soc: Minimum allowed SoC for the battery. Has to be between 0 and 1.
            If current SoC is below or equal to the minimum SoC, battery is not discharged
            further. Defaults to 0. Can be altered during simulation.
        c_rate: Optional C-rate, which defines the charge and discharge rate of the battery.
            For more information on C-rate, see
            `C-rate explanation <https://www.batterydesign.net/electrical/c-rate/>`_.
            Defaults to None.
    """

    def __init__(
        self,
        name: str,
        capacity: float,
        initial_soc: float = 0,
        min_soc: float = 0,
        c_rate: Optional[float] = None,
    ):
        super().__init__(name)
        self.capacity = capacity
        assert 0 <= initial_soc <= 1, "Invalid initial state-of-charge. Has to be between 0 and 1."
        self.charge_level = capacity * initial_soc
        self._soc = initial_soc
        assert 0 <= min_soc <= 1, "Invalid minimum state-of-charge. Has to be between 0 and 1."
        self.min_soc = min_soc
        self.c_rate = c_rate

    def feasible_range(self, duration: int) -> tuple[float, float]:
        """Returns (min_power, max_power) achievable for the given duration.

        Accounts for both c_rate limits and energy capacity limits.

        Args:
            duration: Duration of the timestep in seconds.
        """
        # Discharge limit (negative power)
        if self._soc <= self.min_soc:
            min_power = 0.0
        else:
            # Energy-limited: can only discharge down to min_soc
            energy_available = (self.charge_level - self.min_soc * self.capacity) * 3600  # Ws
            energy_limited = -energy_available / duration if duration > 0 else 0.0
            if self.c_rate is not None:
                min_power = max(energy_limited, -(self.c_rate * self.capacity))
            else:
                min_power = energy_limited

        # Charge limit (positive power)
        if self._soc >= 1.0:
            max_power = 0.0
        else:
            # Energy-limited: can only charge up to capacity
            energy_headroom = (self.capacity - self.charge_level) * 3600  # Ws
            energy_limited = energy_headroom / duration if duration > 0 else 0.0
            if self.c_rate is not None:
                max_power = min(energy_limited, self.c_rate * self.capacity)
            else:
                max_power = energy_limited

        return (min_power, max_power)

    def step(self, duration: int) -> None:
        """Update battery state based on current_power setpoint and duration."""
        if duration <= 0:
            raise ValueError("Duration needs to be a positive value")

        power = self.current_power
        if power == 0.0:
            return

        if self._soc <= self.min_soc and power <= 0.0:
            return

        if self.c_rate is not None:
            max_power = self.c_rate * self.capacity
            if power >= max_power:
                logger.info(
                    f"Trying to charge '{self.name}' with "
                    f"{power} W but only {max_power} W are supported."
                )
                power = max_power
            if power <= -max_power:
                logger.info(
                    f"Trying to discharge '{self.name}' "
                    f"with {power} W but only {max_power} W are supported."
                )
                power = -max_power

        charged_energy = power * duration
        new_charge_level = self.charge_level + charged_energy / 3600

        abs_min_soc = self.min_soc * self.capacity
        if new_charge_level < abs_min_soc:
            self.charge_level = abs_min_soc
            self._soc = self.min_soc
        elif new_charge_level > self.capacity:
            self.charge_level = self.capacity
            self._soc = 1.0
        else:
            self.charge_level = new_charge_level
            self._soc = self.charge_level / self.capacity

    def soc(self) -> float:
        """Returns the state-of-charge (SoC) of the battery (0 to 1)."""
        return self._soc

    def config(self) -> dict:
        return {
            "capacity": self.capacity,
            "min_soc": self.min_soc,
            "c_rate": self.c_rate,
        }

    def state(self) -> dict:
        return {
            "soc": self._soc,
            "charge_level": self.charge_level,
        }


# TODO: Add convenience constructor for ClcBattery (e.g., from_capacity_wh) to avoid
# requiring expert-level parameterization for common use cases.


class ClcBattery(Storage):
    """Implementation of the C-L-C Battery model for lithium-ion batteries.

    This class implements the C-L-C model as described in:
        Kazhamiaka, F., Rosenberg, C. & Keshav, S.
        Tractable lithium-ion storage models for optimizing energy systems.
        Energy Inform 2, 4 (2019).
        `doi:10.1186/s42162-019-0070-6 <https://doi.org/10.1186/s42162-019-0070-6>`_

    The default parameterization models a pack of LGM50 21700 rechargable lithium-ion cells.
    This model should not be used in combination with large step sizes.

    Args:
        name: The name of the battery.
        number_of_cells: Number of cells in the battery pack. Defaults to 1.
        initial_soc: Initial battery state-of-charge (SoC). Has to be between 0 and 1.
            Defaults to 0.
        min_soc: Minimum allowed SoC for the battery. Has to be between 0 and 1.
            Defaults to 0. Can be altered during simulation.
        nom_voltage: Single cell nominal voltage in V. Defaults to 3.63V.
        u_1: Linear factor for lower energy limit of cell depending on applied discharge current.
            Defaults to -0.087Wh/A.
        v_1: Offset for lower energy limit of cell depending on the applied discharge current.
            Defaults to 0.0Wh.
        u_2: Linear factor for upper energy limit of cell depending on the applied charge current.
            Defaults to -1.326Wh/A.
        v_2: Offset for upper energy limit of cell depending on the applied charge current. This
            parameter can be viewed as the capacity of a single cell. Defaults to 19.14Wh.
        alpha_d: Maximum discharging C-rate. Defaults to -1.5C.
        alpha_c: Maximum charging C-rate. Defaults to 0.7C.
        eta_d: Average fraction of power that has to be discharged from cell to obtain said
            power. Is equivalent to the discharging inefficiency. Should be >= 1. Defaults to 1.014.
        eta_c: Average fraction of power that is stored in cell when charged at said power.
            Is equivalent to the charging inefficiency. Should be between 0 and 1. Defaults to 0.978.
        discharging_current_cutoff: If the maximum allowed discharging current is higher than this
            value, discharging is stopped. Defaults to -0.05A.
        charging_current_cutoff: If the maximum allowed charging current is lower than this value,
            charging is stopped. Defaults to 0.05A.
    """

    def __init__(
        self,
        name: str,
        number_of_cells: int = 1,
        initial_soc: float = 0,
        min_soc: float = 0,
        nom_voltage: float = 3.63,
        u_1: float = -0.087,
        v_1: float = 0.0,
        u_2: float = -1.326,
        v_2: float = 19.14,
        alpha_d: float = -1.5,
        alpha_c: float = 0.7,
        eta_d: float = 1.014,
        eta_c: float = 0.978,
        discharging_current_cutoff: float = -0.05,
        charging_current_cutoff: float = 0.05,
    ) -> None:
        super().__init__(name)
        assert number_of_cells > 0, "There has to be a positive number of cells."
        self.number_of_cells = number_of_cells
        self.u_1 = u_1
        self.v_1 = v_1
        self.u_2 = u_2
        self.v_2 = v_2
        assert 0 <= initial_soc <= 1, "Invalid initial state-of-charge. Has to be between 0 and 1."
        self._soc = initial_soc
        self.charge_level = self.v_2 * initial_soc  # Charge level of one cell
        assert 0 <= min_soc <= 1, "Invalid minimum state-of-charge. Has to be between 0 and 1."
        self.min_soc = min_soc
        self.nom_voltage = nom_voltage
        self.alpha_d = alpha_d * self.v_2
        self.alpha_c = alpha_c * self.v_2
        assert eta_d >= 1, "Invalid discharging inefficiency. Has to be greater or equal to 1."
        self.eta_d = eta_d
        assert 0 <= eta_c <= 1, "Invalid charging inefficiency. Has to be between 0 and 1."
        self.eta_c = eta_c
        self.discharging_power_cutoff = discharging_current_cutoff * self.nom_voltage
        self.charging_power_cutoff = charging_current_cutoff * self.nom_voltage

    def feasible_range(self, duration: int) -> tuple[float, float]:
        """Returns (min_power, max_power) based on CLC model constraints.

        Args:
            duration: Duration of the timestep in seconds.
        """
        # Discharge limit
        if self._soc <= self.min_soc:
            min_power = 0.0
        else:
            min_power = self.alpha_d * self.number_of_cells
        # Charge limit
        if self._soc >= 1.0:
            max_power = 0.0
        else:
            max_power = self.alpha_c * self.number_of_cells
        return (min_power, max_power)

    def soc(self) -> float:
        """Returns the state-of-charge (SoC) of the battery (0 to 1)."""
        return self._soc

    def step(self, duration: int) -> None:
        """Update battery state based on current_power setpoint and duration."""
        if duration <= 0:
            raise ValueError("Duration needs to be a positive value")

        power = self.current_power
        if power > 0:
            self._charge(power, duration)
        elif power < 0 and self.soc() > self.min_soc:
            self._discharge(power, duration)

    def _charge(self, power: float, duration: int) -> None:
        max_power = (
            np.minimum(
                (self.charge_level - self.v_2)
                / (self.u_2 / self.nom_voltage - duration * self.eta_c / 3600),
                self.alpha_c,
            )
            * self.number_of_cells
        )
        if power > max_power:
            power = max_power if max_power >= self.charging_power_cutoff else 0.0

        self.charge_level += self.eta_c * (power / self.number_of_cells) * (duration / 3600)
        self._soc = self.charge_level / self.v_2

    def _discharge(self, power: float, duration: int) -> None:
        min_power = (
            np.maximum(
                (self.charge_level - self.v_1)
                / (self.u_1 / self.nom_voltage - duration * self.eta_d / 3600),
                self.alpha_d,
            )
            * self.number_of_cells
        )
        if power < min_power:
            power = min_power if min_power <= self.charging_power_cutoff else 0.0

        discharge_energy = self.eta_d * (power / self.number_of_cells) * (duration / 3600)

        if (self.charge_level + discharge_energy) < self.min_soc * self.v_2:
            self.charge_level = self.v_2 * self.min_soc
            self._soc = self.min_soc
            return

        self.charge_level += discharge_energy
        self._soc = self.charge_level / self.v_2

    def config(self) -> dict:
        return {
            "capacity": self.v_2 * self.number_of_cells,
            "min_soc": self.min_soc,
        }

    def state(self) -> dict:
        return {
            "soc": self._soc,
            "charge_level": self.charge_level * self.number_of_cells,
        }


class _DispatchSim(mosaik_api_v3.Simulator):
    """Mosaik simulator for dispatchables and dispatch policy."""

    META = {
        "type": "time-based",
        "models": {
            "Dispatch": {
                "public": True,
                "params": ["dispatchables", "policy"],
                "attrs": ["p_delta", "grid_signals", "p_grid", "dispatch_states", "policy_state"],
            },
        },
    }

    def __init__(self) -> None:
        super().__init__(self.META)
        self.eid: str = "Dispatch"

    def init(self, sid: str, time_resolution: float = 1.0, **sim_params):
        self.step_size: int = sim_params["step_size"]
        self.p_grid: float = 0.0
        self.dispatch_states: dict = {}
        self.policy_state: dict = {}
        return self.meta

    def create(self, num: int, model, **model_params):
        assert num == 1, "Only one instance per simulation is supported"
        self.dispatchables: list[Dispatchable] = model_params["dispatchables"]
        self.policy: DispatchPolicy = model_params["policy"]
        return [{"eid": self.eid, "type": model}]

    def step(self, time, inputs, max_advance):
        p_delta = list(inputs[self.eid]["p_delta"].values())[0]
        grid_signals = list(inputs[self.eid].get("grid_signals", {None: None}).values())[0]

        # Phase 1: Dispatch policy allocates power across dispatchables
        self.p_grid = self.policy.apply(
            p_delta,
            duration=self.step_size,
            dispatchables=self.dispatchables,
            grid_signals=grid_signals,
        )

        # Phase 2: Advance dispatchable state
        for d in self.dispatchables:
            d.step(self.step_size)

        self.policy_state = self.policy.state()
        self.dispatch_states = {d.name: d.state() for d in self.dispatchables}
        return time + self.step_size

    def get_data(self, outputs):
        return {
            self.eid: {
                "p_grid": self.p_grid,
                "dispatch_states": self.dispatch_states,
                "policy_state": self.policy_state,
            }
        }
