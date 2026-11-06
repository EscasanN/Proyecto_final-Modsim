from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from math import floor, isfinite
from typing import Protocol

import pandas as pd

from .model import nonnegative


class IrrigationPolicy(Protocol):
    def dose(self, timestamp: pd.Timestamp, observed_deficit_ml: float) -> float: ...


def validate_hours(hours) -> tuple[float, ...]:
    values = tuple(float(hour) for hour in hours)
    if len(values) != len(set(values)) or any(not 0 <= hour < 24 for hour in values):
        raise ValueError("Las horas deben ser únicas y pertenecer a [0, 24).")
    return tuple(sorted(values))


@dataclass(frozen=True)
class FixedPolicy:
    dose_ml: float
    irrigation_hours: tuple[float, ...] = (7.0,)
    every_n_days: int = 1
    anchor_date: date = date(2000, 1, 1)

    def __post_init__(self):
        nonnegative(self.dose_ml, "La dosis")
        validate_hours(self.irrigation_hours)
        if isinstance(self.every_n_days, bool) or not isinstance(self.every_n_days, int) or self.every_n_days < 1:
            raise ValueError("every_n_days debe ser un entero positivo.")

    def dose(self, timestamp: pd.Timestamp, observed_deficit_ml: float) -> float:
        hour = (timestamp - timestamp.normalize()).value / 3_600_000_000_000
        scheduled = any(abs(hour - target) < 1e-9 for target in self.irrigation_hours)
        active_day = (timestamp.date() - self.anchor_date).days % self.every_n_days == 0
        return self.dose_ml if scheduled and active_day else 0.0


@dataclass
class ThresholdPolicy:
    """Política C. Crear una instancia nueva por simulación (presupuesto por día)."""

    activation_ml: float
    target_ml: float
    dose_max_ml: float
    safe_deficit_ml: float
    max_daily_ml: float
    resolution_ml: float = 1.0
    max_irrigations_per_day: int = 3
    review_hours: tuple[float, ...] = (7.0, 13.0, 19.0)
    _daily: dict = field(default_factory=dict, init=False, repr=False)
    _last_timestamp: pd.Timestamp | None = field(default=None, init=False, repr=False)

    def __post_init__(self):
        for name in ("activation_ml", "target_ml", "dose_max_ml", "safe_deficit_ml",
                     "max_daily_ml", "resolution_ml"):
            nonnegative(getattr(self, name), name)
        if not 0 <= self.target_ml < self.activation_ml <= self.safe_deficit_ml:
            raise ValueError("Se requiere 0 <= objetivo < activación <= límite operacional.")
        if self.resolution_ml <= 0 or self.dose_max_ml < self.resolution_ml:
            raise ValueError("La dosis máxima debe admitir al menos una unidad de resolución positiva.")
        if (type(self.max_irrigations_per_day) is not int or self.max_irrigations_per_day < 1):
            raise ValueError("La frecuencia diaria debe ser un entero positivo.")
        self.review_hours = validate_hours(self.review_hours)

    def dose(self, timestamp: pd.Timestamp, observed_deficit_ml: float) -> float:
        if not isfinite(observed_deficit_ml):
            raise ValueError("El déficit observado debe ser finito.")
        if self._last_timestamp is not None and timestamp <= self._last_timestamp:
            raise ValueError("Usar una política nueva por simulación e instantes crecientes.")
        self._last_timestamp = timestamp
        hour = (timestamp - timestamp.normalize()).total_seconds() / 3600
        used, count = self._daily.get(timestamp.date(), (0.0, 0))
        if (not any(abs(hour - h) < 1e-9 for h in self.review_hours)
                or observed_deficit_ml < self.activation_ml or count >= self.max_irrigations_per_day):
            return 0.0
        raw = min(self.dose_max_ml, max(0.0, observed_deficit_ml - self.target_ml),
                  max(0.0, self.max_daily_ml - used))
        # Redondeo hacia abajo: nunca aumenta la dosis ni el presupuesto disponible.
        dose = floor(raw / self.resolution_ml + 1e-12) * self.resolution_ml
        if dose > 0:
            self._daily[timestamp.date()] = (used + dose, count + 1)
        return dose
