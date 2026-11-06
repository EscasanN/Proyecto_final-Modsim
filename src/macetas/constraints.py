"""Auditoría independiente: usa trayectoria/eventos, nunca result.metrics."""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd

from .model import local_timestamp, nonnegative
from .simulator import SimulationConfig


@dataclass(frozen=True)
class ConstraintConfig:
    simulation: SimulationConfig
    resolution_ml: float = 1.0
    max_irrigations_per_day: int = 3
    tolerance_ml: float = 1e-7
    allowed_time_over_h: float = 0.0

    def __post_init__(self):
        for name in ("resolution_ml", "tolerance_ml", "allowed_time_over_h"):
            nonnegative(getattr(self, name), name)
        if self.resolution_ml <= 0 or self.tolerance_ml <= 0:
            raise ValueError("Resolución y tolerancia deben ser positivas.")
        if type(self.max_irrigations_per_day) is not int or self.max_irrigations_per_day < 1:
            raise ValueError("La frecuencia debe ser un entero positivo.")
        s = self.simulation
        if any(getattr(s, k) is None or getattr(s, k) <= 0
               for k in ("safe_deficit_ml", "max_dose_ml", "max_daily_ml")):
            raise ValueError("Se requieren límites operacionales positivos.")
        if not s.close_balance:
            raise ValueError("La comparación exige cierre del balance.")


def check_constraints(trajectory: pd.DataFrame, events: pd.DataFrame,
                      config: ConstraintConfig) -> dict:
    s, tol = config.simulation, config.tolerance_ml
    violations = {}

    def check(name, excess, scale=1.0):
        if excess > 0:
            violations[name] = float(excess / scale)

    tc = ["deficit_ml", "loss_ml", "irrigation_ml", "drainage_ml"]
    ec = ["deficit_before_ml", "irrigation_ml", "drainage_ml", "deficit_after_ml"]
    if trajectory.empty or not set(tc + ["timestamp", "stage"]) <= set(trajectory.columns):
        raise ValueError("La auditoría requiere trayectoria completa.")
    if not set(ec + ["timestamp", "kind"]) <= set(events.columns):
        raise ValueError("Falta el esquema de eventos.")
    if not np.isfinite(trajectory[tc].to_numpy(dtype=float)).all() or not np.isfinite(events[ec].to_numpy(dtype=float)).all():
        return {"feasible": False, "violation": 1.0, "violations": {"nonfinite": 1.0}}
    times = pd.DatetimeIndex(trajectory.timestamp)
    start, end = (local_timestamp(t, "America/Guatemala") for t in (s.start, s.end))
    check("horizon", float(times[0] != start or times[-1] != end or not times.is_monotonic_increasing))
    check("stages", float(trajectory.stage.iloc[0] != "initial" or trajectory.stage.iloc[-1] != "final"))
    values = trajectory[tc].to_numpy(dtype=float)
    check("negative", -float(values.min()) - tol)
    d = values[:, 0]
    check("initial", abs(d[0] - s.initial_deficit_ml) - tol)
    check("closure", abs(d[-1] - s.initial_deficit_ml) - tol)
    residual = d - s.initial_deficit_ml - values[:, 1] + values[:, 2] - values[:, 3]
    check("balance", float(np.max(np.abs(residual))) - tol)
    for index, name in ((1, "loss"), (2, "water"), (3, "drainage")):
        check(f"monotonic_{name}", -float(np.min(np.diff(values[:, index]), initial=0)) - tol)
    time_over = 0.0
    for i in range(1, len(d)):
        h = (times[i] - times[i - 1]).total_seconds() / 3600
        if h > 0:
            # El modelo B tiene pérdidas no negativas entre eventos.
            check("continuous_decrease", d[i - 1] - d[i] - tol)
            limit = s.safe_deficit_ml + tol
            if d[i - 1] > limit:
                time_over += h
            elif d[i] > limit:
                time_over += h * (d[i] - limit) / (d[i] - d[i - 1])
    if config.allowed_time_over_h == 0:
        check("safe_deficit", float(d.max()) - s.safe_deficit_ml - tol, s.safe_deficit_ml)
    check("time_over", time_over - config.allowed_time_over_h, max(1.0, (end-start).total_seconds()/3600))
    daily, counts, seen = {}, {}, set()
    final_count = 0
    for row in events.itertuples():
        t = local_timestamp(row.timestamp, "America/Guatemala")
        dose = float(row.irrigation_ml)
        check("negative_event", -min(getattr(row, c) for c in ec) - tol)
        check("event_balance", abs(row.deficit_after_ml-row.deficit_before_ml+dose-row.drainage_ml)-tol)
        check("event_drainage", abs(row.drainage_ml-max(0, dose-row.deficit_before_ml))-tol)
        check("dose", dose-s.max_dose_ml-tol, s.max_dose_ml)
        daily[t.date()] = daily.get(t.date(), 0.0) + dose
        check("duplicate_event", float(t in seen))
        seen.add(t)
        if row.kind == "final_refill":
            final_count += 1
            check("refill_time", float(t != end))
            check("refill_amount", abs(dose-max(0, row.deficit_before_ml-s.initial_deficit_ml))-tol)
        elif row.kind == "irrigation":
            hour = (t-t.normalize()).total_seconds()/3600
            check("schedule", float(not start <= t < end or not any(abs(hour-h)<1e-9 for h in s.review_hours)))
            check("resolution", abs(dose/config.resolution_ml-round(dose/config.resolution_ml))*config.resolution_ml-tol)
            counts[t.date()] = counts.get(t.date(), 0) + 1
        else:
            check("event_kind", 1.0)
        matching = trajectory[(trajectory.timestamp == row.timestamp) & (trajectory.stage == row.kind)]
        check("event_trace", float(len(matching) != 1))
        if len(matching) == 1:
            check("event_state", abs(float(matching.deficit_ml.iloc[0])-row.deficit_after_ml)-tol)
    check("refill_count", final_count-1)
    check("frequency", max(counts.values(), default=0)-config.max_irrigations_per_day,
          config.max_irrigations_per_day)
    check("daily", max(daily.values(), default=0)-s.max_daily_ml-tol, s.max_daily_ml)
    check("event_water_total", abs(float(events.irrigation_ml.sum())-values[-1, 2])-tol)
    check("event_drainage_total", abs(float(events.drainage_ml.sum())-values[-1, 3])-tol)
    return {"feasible": not violations, "violation": sum(violations.values()),
            "violations": violations, "time_over_limit_h": time_over,
            "max_deficit_ml": float(d.max()), "total_irrigation_ml": float(events.irrigation_ml.sum()),
            "tolerance_ml": tol}
