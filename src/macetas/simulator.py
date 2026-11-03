from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import isfinite

import pandas as pd

from .integrators import METHODS
from .model import LossModel, apply_irrigation, local_timestamp, nonnegative
from .policies import IrrigationPolicy, validate_hours


@dataclass(frozen=True)
class SimulationConfig:
    start: str | pd.Timestamp
    end: str | pd.Timestamp
    initial_deficit_ml: float = 0.0
    method: str = "rk4"
    step_h: float = 0.25
    review_hours: tuple[float, ...] = (7.0, 13.0, 19.0)
    safe_deficit_ml: float | None = None
    max_dose_ml: float | None = None
    max_daily_ml: float | None = None
    close_balance: bool = True

    def __post_init__(self):
        nonnegative(self.initial_deficit_ml, "El déficit inicial")
        if self.method not in METHODS:
            raise ValueError("El método debe ser euler o rk4.")
        if not isfinite(self.step_h) or self.step_h <= 0 or pd.Timedelta(hours=self.step_h).value == 0:
            raise ValueError("El paso debe ser positivo y representable.")
        validate_hours(self.review_hours)
        for name in ("safe_deficit_ml", "max_dose_ml", "max_daily_ml"):
            if (value := getattr(self, name)) is not None:
                nonnegative(value, name)


@dataclass(frozen=True)
class IrrigationEvent:
    timestamp: str | pd.Timestamp
    irrigation_ml: float
    event_id: str = ""


@dataclass(frozen=True)
class LossChange:
    timestamp: str | pd.Timestamp
    multiplier: float


@dataclass
class SimulationResult:
    trajectory: pd.DataFrame
    events: pd.DataFrame
    metrics: dict


def daily_times(start, end, hours) -> list[pd.Timestamp]:
    days = pd.date_range(start.normalize(), end.normalize(), freq="D")
    return sorted({time for day in days for hour in hours
                   if start <= (time := day + pd.Timedelta(hours=hour)) < end})


def simulate(model: LossModel, config: SimulationConfig, policy: IrrigationPolicy | None = None,
             irrigation_events: Sequence[IrrigationEvent] = (), observation_times: Sequence = (),
             loss_changes: Sequence[LossChange] = (), observation_errors_ml: Mapping | None = None,
             record_trajectory: bool = True) -> SimulationResult:
    start = local_timestamp(config.start, model.timezone)
    end = local_timestamp(config.end, model.timezone)
    if end <= start:
        raise ValueError("El final debe ser posterior al inicio.")
    if model.timezone != "America/Guatemala":
        raise ValueError("El calendario local está verificado para America/Guatemala.")
    if policy is not None and irrigation_events:
        raise ValueError("Se debe elegir una política o una secuencia de riegos registrados.")
    reviews = set(daily_times(start, end, config.review_hours)) if policy is not None else set()
    fixed_events = {}
    for event in irrigation_events:
        time = local_timestamp(event.timestamp, model.timezone)
        if not start <= time < end or time in fixed_events:
            raise ValueError("Cada riego debe tener un instante único dentro de [inicio, fin).")
        fixed_events[time] = (nonnegative(event.irrigation_ml, "El riego"), event.event_id)
    observations = {local_timestamp(time, model.timezone) for time in observation_times}
    if any(not start <= time <= end for time in observations):
        raise ValueError("Hay observaciones fuera del horizonte.")
    changes = {}
    for change in loss_changes:
        time = local_timestamp(change.timestamp, model.timezone)
        if not start <= time < end or time in changes:
            raise ValueError("Cada cambio de pérdida debe tener un instante único dentro de [inicio, fin).")
        changes[time] = nonnegative(change.multiplier, "El factor de pérdida")
    errors = {local_timestamp(time, model.timezone): float(value)
              for time, value in (observation_errors_ml or {}).items()}
    if not set(errors) <= reviews or not all(isfinite(value) for value in errors.values()):
        raise ValueError("Los errores de observación deben ser finitos y corresponder a revisiones.")
    block_cuts = daily_times(start, end, [block["start_hour"] for block in model.time_blocks])
    boundaries = sorted({start, end, *reviews, *fixed_events, *observations, *changes, *block_cuts})
    step_ns = pd.Timedelta(hours=config.step_h).value
    solver = METHODS[config.method]
    deficit = float(config.initial_deficit_ml)
    maximum = deficit
    loss = drainage = applied = time_over = 0.0
    multiplier = 1.0
    trajectory, events = [], []
    daily_applied = {}
    dose_ok = True
    steps = 0

    def record(time, stage):
        if record_trajectory:
            trajectory.append({"timestamp": time, "stage": stage, "deficit_ml": deficit,
                               "loss_ml": loss, "irrigation_ml": applied, "drainage_ml": drainage,
                               "data_origin": model.data_origin})

    def irrigate(time, dose, event_id, kind, observed=None):
        nonlocal deficit, drainage, applied, dose_ok
        before = deficit
        balance = apply_irrigation(deficit, dose)
        deficit = balance.deficit_ml
        drainage += balance.drainage_ml
        applied += dose
        daily_applied[time.date()] = daily_applied.get(time.date(), 0.0) + dose
        dose_ok = dose_ok and (config.max_dose_ml is None or dose <= config.max_dose_ml + 1e-9)
        events.append({"timestamp": time, "event_id": event_id, "kind": kind,
                       "observed_deficit_ml": observed, "deficit_before_ml": before,
                       "irrigation_ml": dose, "drainage_ml": balance.drainage_ml,
                       "deficit_after_ml": deficit, "data_origin": model.data_origin})
        record(time, kind)

    record(start, "initial")
    for index, time in enumerate(boundaries[:-1]):
        if time in changes:
            multiplier = changes[time]
        if time in reviews:
            observed = deficit + errors.get(time, 0.0)
            dose = nonnegative(policy.dose(time, observed), "La dosis de la política")
            record(time, "review")
            if dose > 0:
                irrigate(time, dose, f"R{len(events) + 1:05d}", "irrigation", observed)
        elif time in fixed_events:
            dose, event_id = fixed_events[time]
            if dose > 0:
                irrigate(time, dose, event_id, "irrigation")
        factor = model.factor_at(time) * multiplier
        rhs = lambda t, value: model.rate(value, factor)
        stop = boundaries[index + 1]
        duration_ns = (stop - time).value
        elapsed_ns = 0
        while elapsed_ns < duration_ns:
            dt_ns = min(step_ns, duration_ns - elapsed_ns)
            h = dt_ns / 3_600_000_000_000
            next_deficit = solver(rhs, 0.0, deficit, h)
            if not isfinite(next_deficit) or next_deficit < deficit - 1e-9:
                raise ValueError("El paso produjo una trayectoria inválida; reduzca step_h.")
            if model.b_per_h < 0 and factor > 0:
                equilibrium = -model.a_ml_per_h / model.b_per_h
                if deficit < equilibrium and next_deficit > equilibrium + 1e-9:
                    raise ValueError("El paso sobrepasó el equilibrio; reduzca step_h.")
            limit = config.safe_deficit_ml
            if limit is not None:
                if deficit >= limit and next_deficit > limit:
                    time_over += h
                elif deficit < limit < next_deficit:
                    time_over += h * (next_deficit - limit) / (next_deficit - deficit)
            loss += next_deficit - deficit
            deficit = next_deficit
            maximum = max(maximum, deficit)
            elapsed_ns += dt_ns
            steps += 1
            if record_trajectory:
                record(time + pd.Timedelta(elapsed_ns, unit="ns"), "continuous")
    final_before = deficit
    operational_applied = applied
    refill = max(0.0, deficit - config.initial_deficit_ml) if config.close_balance else 0.0
    if refill > 0:
        irrigate(end, refill, "FINAL", "final_refill")
    record(end, "final")
    closure_ok = config.close_balance and abs(deficit - config.initial_deficit_ml) <= 1e-8
    daily_ok = config.max_daily_ml is None or all(value <= config.max_daily_ml + 1e-9
                                                  for value in daily_applied.values())
    safe_ok = config.safe_deficit_ml is None or maximum <= config.safe_deficit_ml + 1e-9
    constraints_checked = all(value is not None for value in
                              (config.safe_deficit_ml, config.max_dose_ml, config.max_daily_ml))
    metrics = {"data_origin": model.data_origin, "method": config.method, "step_h": config.step_h,
               "horizon_h": (end - start).total_seconds() / 3600,
               "initial_deficit_ml": config.initial_deficit_ml,
               "final_deficit_before_refill_ml": final_before, "final_deficit_ml": deficit,
               "operational_irrigation_ml": operational_applied, "final_refill_ml": refill,
               "total_irrigation_ml": applied, "drainage_ml": drainage, "loss_ml": loss,
               "max_deficit_ml": maximum, "time_over_limit_h": time_over if config.safe_deficit_ml is not None else None,
               "n_irrigations": sum(event["kind"] == "irrigation" for event in events),
               "n_final_refills": int(refill > 0), "integration_steps": steps,
               "balance_residual_ml": deficit - config.initial_deficit_ml - loss + applied - drainage,
               "closure_ok": closure_ok, "dose_ok": dose_ok, "daily_budget_ok": daily_ok,
               "safe_deficit_ok": safe_ok, "constraints_checked": constraints_checked,
               "feasible": (closure_ok and dose_ok and daily_ok and safe_ok) if constraints_checked else None}
    trajectory_columns = ["timestamp", "stage", "deficit_ml", "loss_ml", "irrigation_ml", "drainage_ml", "data_origin"]
    event_columns = ["timestamp", "event_id", "kind", "observed_deficit_ml", "deficit_before_ml",
                     "irrigation_ml", "drainage_ml", "deficit_after_ml", "data_origin"]
    return SimulationResult(pd.DataFrame(trajectory, columns=trajectory_columns),
                            pd.DataFrame(events, columns=event_columns), metrics)
