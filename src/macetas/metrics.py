"""Métricas de D; la factibilidad pertenece al auditor de C."""
import numpy as np
import pandas as pd

from .constraints import check_constraints


def validation_errors(observed, predicted):
    observed, predicted = np.asarray(observed, dtype=float), np.asarray(predicted, dtype=float)
    if (observed.ndim != 1 or observed.shape != predicted.shape or not observed.size
            or not np.isfinite(observed).all() or not np.isfinite(predicted).all()):
        raise ValueError("Se requieren pares finitos, no vacíos y de igual longitud.")
    error = predicted - observed
    return {"n_observations": len(error), "mae_ml": float(np.abs(error).mean()),
            "rmse_ml": float(np.sqrt(np.mean(error**2))), "bias_ml": float(error.mean())}


def compute_metrics(result, constraints, duration_s):
    if not np.isfinite(duration_s) or duration_s < 0:
        raise ValueError("La duración debe ser finita y no negativa.")
    audit = check_constraints(result.trajectory, result.events, constraints)
    if "time_over_limit_h" not in audit:
        raise ValueError("La trayectoria contiene valores no finitos.")
    events = result.events
    refill = events.kind.eq("final_refill")
    return {"total_irrigation_ml": float(events.irrigation_ml.sum()),
            "final_refill_ml": float(events.loc[refill, "irrigation_ml"].sum()),
            "drainage_ml": float(events.drainage_ml.sum()),
            "max_deficit_ml": audit["max_deficit_ml"],
            "time_over_limit_h": audit["time_over_limit_h"],
            "n_irrigations": int((~refill & events.irrigation_ml.gt(0)).sum()),
            "n_final_refills": int(refill.sum()), "duration_s": float(duration_s),
            "feasible": audit["feasible"], "violation": audit["violation"]}


MEASURES = ["total_irrigation_ml", "final_refill_ml", "drainage_ml", "max_deficit_ml",
            "time_over_limit_h", "n_irrigations", "duration_s"]


def summarize_runs(runs):
    rows = []
    for condition, group in runs.groupby("condition", sort=True):
        row = {"condition": condition, "n_runs": len(group),
               "feasible_fraction": float(group.feasible.mean())}
        for name in MEASURES:
            row[name + "_mean"] = float(group[name].mean())
            row[name + "_sd"] = float(group[name].std(ddof=1)) if len(group) > 1 else None
        rows.append(row)
    return pd.DataFrame(rows)


def paired_differences(runs):
    rows = []
    for sensitivity in (0, 1):
        base = runs[runs.condition.eq(f"B{sensitivity}")].set_index("seed", verify_integrity=True)
        optimized = runs[runs.condition.eq(f"O{sensitivity}")].set_index("seed", verify_integrity=True)
        if base.empty or set(base.index) != set(optimized.index):
            raise ValueError("Las políticas deben compartir exactamente las semillas.")
        for seed, b in base.iterrows():
            o = optimized.loc[seed]
            saving = float(b.total_irrigation_ml - o.total_irrigation_ml)
            row = {"sensitivity": sensitivity, "seed": seed,
                   "saving_ml": saving,
                   "saving_pct": 100 * saving / b.total_irrigation_ml if b.total_irrigation_ml > 0 else None,
                   "both_feasible": bool(b.feasible and o.feasible),
                   "optimized_better": bool(b.feasible and o.feasible and saving > 0)}
            row.update({name + "_difference": float(o[name] - b[name]) for name in MEASURES})
            rows.append(row)
    return pd.DataFrame(rows)
