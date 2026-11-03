from __future__ import annotations

from dataclasses import dataclass
from datetime import date
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
        hour = timestamp.hour + timestamp.minute / 60 + timestamp.second / 3600
        scheduled = any(abs(hour - target) < 1e-9 for target in self.irrigation_hours)
        active_day = (timestamp.date() - self.anchor_date).days % self.every_n_days == 0
        return self.dose_ml if scheduled and active_day else 0.0
