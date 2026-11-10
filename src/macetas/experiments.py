"""Evaluación final de una política congelada; nunca invoca PSO."""
import argparse
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import platform
from time import perf_counter

import numpy as np
import pandas as pd

from .constraints import ConstraintConfig
from .metrics import compute_metrics, paired_differences, summarize_runs
from .model import load_calibrated_model, local_timestamp
from .optimization import development_bank, make_policy, validate_seed_banks
from .policies import FixedPolicy
from .simulator import LossChange, SimulationConfig, simulate


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, payload):
    Path(path).write_text(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")


def run_experiments(config_path, *, allow_synthetic=False, output_dir=None):
    path = Path(config_path).resolve()
    config = read_json(path)
    source = (path.parent / config["optimization_config"]).resolve()
    search = read_json(source)
    validate_seed_banks(search["seeds"])
    if search["status"] not in ("frozen", "synthetic_example"):
        raise ValueError("La configuración de desarrollo está pendiente.")
    paths = {k: (source.parent / search[k]).resolve() for k in ("model", "parameters", "base")}
    paths.update(config=path, optimization_config=source,
                 frozen_policy=(path.parent / config["frozen_policy"]).resolve())
    frozen = read_json(paths["frozen_policy"])
    if frozen["status"] != "frozen" or frozen.get("scope") != "development_only" or not frozen.get("policy"):
        raise ValueError("Se requiere una política factible congelada en desarrollo.")
    seeds = search["seeds"]["evaluation"]
    if seeds != frozen["reserved_evaluation_seeds"]:
        raise ValueError("Las semillas no coinciden con la reserva de la política.")
    paths["optimization_manifest"] = paths["frozen_policy"].parent / "optimization_manifest.json"
    provenance = read_json(paths["optimization_manifest"])
    for key, input_path in {"config": source, **{k: paths[k] for k in ("model", "parameters", "base")}}.items():
        if sha256(input_path.read_bytes()).hexdigest() != provenance["input_sha256"][key]:
            raise ValueError("Las entradas cambiaron desde la selección de la política congelada.")
    model = load_calibrated_model(paths["parameters"], search.get("pot_id"), allow_synthetic)
    base, model_cfg, parameters = [read_json(paths[k]) for k in ("base", "model", "parameters")]
    if model.data_origin != frozen["data_origin"] or model.time_blocks != model_cfg["time_blocks"]:
        raise ValueError("Origen o bloques incompatibles con la política congelada.")
    if base["status"] != "frozen" and not (allow_synthetic and model.data_origin == "synthetic"
                                                   and base["status"] == "synthetic_example"):
        raise ValueError("La base debe estar congelada o ser un ejemplo sintético explícito.")
    if search["status"] == "synthetic_example" and model.data_origin != "synthetic":
        raise ValueError("No usar restricciones hipotéticas con datos reales.")
    simulation = SimulationConfig(**{**model_cfg["simulation"], **base["simulation"]})
    if asdict(simulation) != frozen["simulation"] or search["constraints"] != frozen["constraints"]:
        raise ValueError("No cambiar horizonte, integrador, estado ni restricciones tras seleccionar.")
    if not set(base["policy"]["irrigation_hours"]) <= set(simulation.review_hours):
        raise ValueError("El calendario base no coincide con las revisiones comunes.")
    constraints = ConstraintConfig(simulation, **frozen["constraints"])
    sigma = parameters["measurement"]["sigma_deficit_ml"]
    forcing = {**search["forcing"], "multiplier": base.get("loss_multiplier", 1.0)}
    stochastic = forcing["daily_cv"] > 0 or sigma > 0
    if stochastic and len(seeds) < 30:
        raise ValueError("Se requieren al menos 30 repeticiones independientes.")
    if not stochastic:
        seeds = seeds[:1]
    bank = development_bank(seeds, model, simulation, forcing, sigma)
    output = Path(output_dir) if output_dir else path.parent / config["output_dir"]
    output.mkdir(parents=True, exist_ok=True)
    rows, traces, events, audits, scenarios = [], [], [], [], []
    for scenario in bank:
        scenarios.append({"seed": scenario["seed"], "loss_changes": [
            {"timestamp": str(c.timestamp), "multiplier": c.multiplier} for c in scenario["loss_changes"]],
            "observation_errors_ml": {str(t): v for t, v in scenario["observation_errors_ml"].items()}})
        for sensitivity, multiplier in ((0, 1.0), (1, 1.2)):
            changes = [LossChange(c.timestamp, c.multiplier * multiplier) for c in scenario["loss_changes"]]
            for label in ("B", "O"):
                condition = f"{label}{sensitivity}"
                policy = (FixedPolicy(**base["policy"], anchor_date=local_timestamp(simulation.start, model.timezone).date())
                          if label == "B" else make_policy(frozen["policy"], constraints))
                started = perf_counter()
                result = simulate(model, simulation, policy, loss_changes=changes,
                                  observation_errors_ml=scenario["observation_errors_ml"])
                metrics = compute_metrics(result, constraints, perf_counter() - started)
                metadata = {"condition": condition, "seed": scenario["seed"],
                            "data_origin": model.data_origin, "loss_multiplier": multiplier,
                            "safe_deficit_ml": simulation.safe_deficit_ml}
                rows.append({**metadata, **metrics})
                traces.append(result.trajectory.assign(**metadata))
                events.append(result.events.assign(**metadata))
                audits.append({**metadata, "balance_residual_ml": result.metrics["balance_residual_ml"]})
    runs = pd.DataFrame(rows)
    paired = paired_differences(runs)
    paired_summary = paired.groupby("sensitivity").agg(
        n_pairs=("seed", "count"), saving_mean_ml=("saving_ml", "mean"),
        saving_sd_ml=("saving_ml", "std"), saving_mean_pct=("saving_pct", "mean"),
        saving_sd_pct=("saving_pct", "std"), both_feasible_fraction=("both_feasible", "mean"))
    for name, frame in {"runs": runs, "summary": summarize_runs(runs),
                        "paired": paired, "paired_summary": paired_summary.reset_index(), "trajectory": pd.concat(traces),
                        "events": pd.concat(events), "balance": pd.DataFrame(audits)}.items():
        frame.to_csv(output / f"{name}.csv", index=False)
    write_json(output / "evaluation_scenarios.json", scenarios)
    write_json(output / "manifest.json", {"data_origin": model.data_origin, "real_validation": False,
               "stochastic": stochastic, "seeds": search["seeds"], "evaluation_seeds_used": seeds,
               "simulation": asdict(simulation), "frozen_policy": frozen, "config": config,
               "development_config": search, "parameters": parameters, "base": base,
               "python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__,
               "input_sha256": {k: sha256(p.read_bytes()).hexdigest() for k, p in paths.items()},
               "source_sha256": {p.name: sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob("*.py")},
               "reproducibility": "Resultados numéricos reproducibles; duration_s es tiempo de pared variable."})
    return runs, output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/experiments.json")
    parser.add_argument("--allow-synthetic", action="store_true")
    parser.add_argument("--out")
    args = parser.parse_args()
    _, output = run_experiments(args.config, allow_synthetic=args.allow_synthetic, output_dir=args.out)
    print(output)


if __name__ == "__main__":
    main()
