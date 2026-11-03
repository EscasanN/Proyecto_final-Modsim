from __future__ import annotations

import json
from dataclasses import replace
from math import exp, log2
from pathlib import Path

import pandas as pd

from .model import LossModel, apply_irrigation
from .simulator import IrrigationEvent, SimulationConfig, simulate


def verify_numerics(output_dir) -> dict[str, Path]:
    blocks = [{"name": "all", "start_hour": 0, "end_hour": 24}]
    nonlinear = LossModel(3.0, -0.02, {"all": 1.0}, blocks)
    config = SimulationConfig("2000-01-01T06:00:00-06:00", "2000-01-01T18:00:00-06:00",
                              initial_deficit_ml=5.0, close_balance=False)
    exact = (5.0 - 150.0) * exp(-0.02 * 12) + 150.0
    convergence = []
    for method in ("euler", "rk4"):
        previous = None
        for step in (1.0, 0.5, 0.25):
            result = simulate(nonlinear, replace(config, method=method, step_h=step), record_trajectory=False)
            numerical = result.metrics["final_deficit_ml"]
            error = abs(numerical - exact)
            convergence.append({"method": method, "step_h": step, "exact_deficit_ml": exact,
                                "numerical_deficit_ml": numerical, "absolute_error_ml": error,
                                "observed_order": log2(previous / error) if previous and error else None,
                                "balance_residual_ml": result.metrics["balance_residual_ml"],
                                "data_origin": "analytical"})
            previous = error
    checks = []
    for method in ("euler", "rk4"):
        constant = LossModel(2.0, 0.0, {"all": 1.0}, blocks)
        flat = simulate(constant, replace(config, method=method, step_h=5.0), record_trajectory=False)
        checks.append({"case": "constant_loss", "method": method,
                       "error_ml": abs(flat.metrics["final_deficit_ml"] - 29.0)})
        zero = LossModel(0.0, 0.0, {"all": 1.0}, blocks)
        unchanged = simulate(zero, replace(config, method=method), record_trajectory=False)
        checks.append({"case": "zero_loss", "method": method,
                       "error_ml": abs(unchanged.metrics["final_deficit_ml"] - 5.0)})
        wet = simulate(zero, replace(config, method=method, initial_deficit_ml=40.0),
                       irrigation_events=[IrrigationEvent("2000-01-01T09:17:00-06:00", 60.0)],
                       record_trajectory=False)
        checks.append({"case": "irrigation_40_60", "method": method,
                       "error_ml": max(abs(wet.metrics["final_deficit_ml"]),
                                       abs(wet.metrics["drainage_ml"] - 20.0),
                                       abs(wet.metrics["balance_residual_ml"]))})
    balance = apply_irrigation(40.0, 60.0)
    checks.append({"case": "event_balance", "method": "algebraic",
                   "error_ml": abs(balance.deficit_ml - 40.0 + 60.0 - balance.drainage_ml)})
    frame = pd.DataFrame(convergence)
    passed = all(row["error_ml"] < 1e-9 for row in checks)
    passed = passed and frame.loc[(frame["method"] == "euler") & frame["observed_order"].notna(),
                                 "observed_order"].between(0.9, 1.2).all()
    passed = passed and frame.loc[(frame["method"] == "rk4") & frame["observed_order"].notna(),
                                 "observed_order"].between(3.8, 4.2).all()
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = {"convergence": out / "convergencia.csv", "checks": out / "casos_conocidos.csv",
             "summary": out / "verificacion.json"}
    frame.to_csv(paths["convergence"], index=False, encoding="utf-8-sig")
    pd.DataFrame(checks).to_csv(paths["checks"], index=False, encoding="utf-8-sig")
    paths["summary"].write_text(json.dumps({"passed": bool(passed), "data_origin": "analytical",
                                          "real_validation": False, "n_cases": len(checks)}, indent=2), encoding="utf-8")
    if not passed:
        raise ValueError("La verificación numérica no alcanzó los criterios esperados.")
    return paths
