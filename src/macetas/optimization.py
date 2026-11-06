"""Integración de C: búsqueda y selección en desarrollo; no ejecuta evaluación final."""
from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json
import platform
from pathlib import Path
import subprocess
from time import perf_counter

import numpy as np
import pandas as pd

from .constraints import ConstraintConfig, check_constraints
from .model import load_calibrated_model, local_timestamp, nonnegative
from .policies import FixedPolicy, ThresholdPolicy
from .pso import Score, search
from .simulator import LossChange, SimulationConfig, daily_times, simulate


def validate_seed_banks(banks):
    seen = set()
    for name in ("search", "selection", "evaluation", "optimizer"):
        seeds = banks[name]
        if not seeds or any(type(s) is not int or s < 0 for s in seeds):
            raise ValueError(f"Banco {name}: semillas enteras no negativas requeridas.")
        if len(set(seeds)) != len(seeds) or seen.intersection(seeds):
            raise ValueError("Los bancos de semillas deben ser únicos y disjuntos.")
        seen.update(seeds)


def decode_candidate(z, constraints: ConstraintConfig):
    """Reparación estructural en una rejilla definida antes de buscar.

    z0 = activación, z1 = fracción objetivo/activación, z2 = dosis máxima.
    Los extremos 0 y 1 son válidos. Todos los parámetros efectivos son guardados.
    """
    z = np.asarray(z, dtype=float)
    if z.shape != (3,) or not np.isfinite(z).all() or np.any((z < 0) | (z > 1)):
        raise ValueError("Se requieren tres coordenadas finitas en [0,1].")
    unit = constraints.resolution_ml
    activation_steps = int(np.floor(constraints.simulation.safe_deficit_ml/unit))
    dose_steps = int(np.floor(constraints.simulation.max_dose_ml/unit))
    if min(activation_steps, dose_steps) < 1:
        raise ValueError("La resolución no permite representar los límites.")
    activation = 1 + int(np.floor(z[0]*(activation_steps-1)+1e-12))
    target = int(np.floor(z[1]*(activation-1)+1e-12))
    dose = 1 + int(np.floor(z[2]*(dose_steps-1)+1e-12))
    return {"activation_ml": activation*unit, "target_ml": target*unit, "dose_max_ml": dose*unit}


def make_policy(candidate, constraints):
    s = constraints.simulation
    return ThresholdPolicy(**candidate, safe_deficit_ml=s.safe_deficit_ml,
                           max_daily_ml=s.max_daily_ml, resolution_ml=constraints.resolution_ml,
                           max_irrigations_per_day=constraints.max_irrigations_per_day,
                           review_hours=s.review_hours)


def development_bank(seeds, model, simulation, forcing, sigma_ml):
    """Realizaciones exógenas pregeneradas, independientes del número de riegos."""
    cv = nonnegative(forcing["daily_cv"], "CV diario")
    multiplier = nonnegative(forcing["multiplier"], "Multiplicador")
    sigma_ml = nonnegative(sigma_ml, "Error de observación")
    start, end = (local_timestamp(t, model.timezone) for t in (simulation.start, simulation.end))
    days = pd.date_range(start.normalize(), end.normalize(), freq="D")
    days = [max(start, d) for d in days if d < end]
    reviews = daily_times(start, end, simulation.review_hours)
    bank = []
    for seed in seeds:
        env_seed, obs_seed = np.random.SeedSequence(seed).spawn(2)
        rng, measurement_rng = np.random.default_rng(env_seed), np.random.default_rng(obs_seed)
        log_sd = np.sqrt(np.log1p(cv*cv))
        factors = multiplier*rng.lognormal(-0.5*log_sd**2, log_sd, len(days))
        errors = measurement_rng.normal(0, sigma_ml, len(reviews))
        bank.append({"seed": seed, "loss_changes": [LossChange(t, float(f)) for t, f in zip(days, factors)],
                     "observation_errors_ml": dict(zip(reviews, errors.tolist()))})
    return bank


def evaluate_policy(candidate, development_scenarios, model, constraints, *, fixed_factory=None):
    if not development_scenarios:
        raise ValueError("El banco de desarrollo no puede estar vacío.")
    audits = []
    for scenario in development_scenarios:
        policy = fixed_factory() if fixed_factory else make_policy(candidate, constraints)
        result = simulate(model, constraints.simulation, policy,
                          loss_changes=scenario["loss_changes"],
                          observation_errors_ml=scenario["observation_errors_ml"])
        audit = check_constraints(result.trajectory, result.events, constraints)
        audits.append({"seed": scenario["seed"], **audit})
    return Score(float(np.mean([a["total_irrigation_ml"] for a in audits])),
                 float(sum(a["violation"] for a in audits))), audits


def _write_json(path, payload):
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")


def run_optimization(config_path, *, allow_synthetic=False, output_dir=None):
    path = Path(config_path).resolve()
    config = json.loads(path.read_text(encoding="utf-8-sig"))
    if config["status"] not in ("frozen", "synthetic_example"):
        raise ValueError("Configuración de optimización pendiente: completar y congelar después del piloto.")
    if config["status"] == "synthetic_example" and not allow_synthetic:
        raise ValueError("Esta búsqueda es sintética; use --allow-synthetic.")
    validate_seed_banks(config["seeds"])
    if len(config["seeds"]["optimizer"]) < 30:
        raise ValueError("Se requieren al menos 30 corridas por variante del optimizador.")
    inputs = {name: (path.parent/config[name]).resolve() for name in ("model", "parameters", "base")}
    model = load_calibrated_model(inputs["parameters"], config.get("pot_id"), allow_synthetic)
    if config["status"] == "synthetic_example" and model.data_origin != "synthetic":
        raise ValueError("No mezclar restricciones hipotéticas con una calibración real.")
    model_cfg, base, params = [json.loads(inputs[k].read_text(encoding="utf-8-sig"))
                               for k in ("model", "base", "parameters")]
    if model.time_blocks != model_cfg["time_blocks"]:
        raise ValueError("Bloques del modelo y calibración distintos.")
    if base["status"] != "frozen" and not (base["status"] == "synthetic_example" and model.data_origin == "synthetic" and allow_synthetic):
        raise ValueError("La política base debe estar congelada.")
    if not base.get("justification") or not config.get("justification"):
        raise ValueError("Documentar la justificación de base, restricciones y aleatoriedad.")
    simulation = SimulationConfig(**{**model_cfg["simulation"], **base["simulation"]})
    constraints = ConstraintConfig(simulation, **config["constraints"])
    decode_candidate([0, 0, 0], constraints)
    sigma = params.get("measurement", {}).get("sigma_deficit_ml")
    if sigma is None:
        raise ValueError("Se requiere sigma_deficit_ml de la calibración de A.")
    if not set(base["policy"]["irrigation_hours"]) <= set(simulation.review_hours):
        raise ValueError("El horario base debe estar dentro de las revisiones comunes.")
    forcing = {**config["forcing"], "multiplier": base.get("loss_multiplier", 1.0)}
    banks = {name: development_bank(config["seeds"][name], model, simulation, forcing, sigma)
             for name in ("search", "selection")}
    # Nunca se generan ni se consultan realizaciones del banco final reservado a D.
    caches = {name: {} for name in banks}

    def evaluate(candidate, bank):
        key = tuple(candidate.values())
        if key not in caches[bank]:
            caches[bank][key] = evaluate_policy(candidate, banks[bank], model, constraints)
        return caches[bank][key]

    variants = config["variants"]
    if not variants or len({v["name"] for v in variants}) != len(variants):
        raise ValueError("Variantes no vacías y nombres únicos requeridos.")
    rows, histories, candidates = [], [], []
    for variant in variants:
        for seed in config["seeds"]["optimizer"]:
            started = perf_counter()
            result = search(lambda z: evaluate(decode_candidate(z, constraints), "search")[0],
                            seed=seed, **config["budget"], **{k:v for k,v in variant.items() if k != "name"})
            elapsed = perf_counter()-started
            candidate = decode_candidate(result.position, constraints)
            selection, audits = evaluate(candidate, "selection")
            # Una política congelada debe ser factible en búsqueda Y selección.
            combined = Score(selection.water_ml, selection.violation + result.score.violation)
            row = {"variant": variant["name"], "seed": seed, "data_origin": model.data_origin,
                   "evaluations": result.evaluations, "duration_s": elapsed,
                   "search_water_ml": result.score.water_ml, "search_violation": result.score.violation,
                   "selection_water_ml": selection.water_ml, "selection_violation": selection.violation,
                   "feasible": combined.violation == 0, **candidate}
            rows.append(row)
            candidates.append((combined.key, len(rows)-1, candidate, audits))
            histories.extend({"variant": variant["name"], "seed": seed, **h} for h in result.history)
            print(f"{variant['name']} semilla {seed}: búsqueda {result.score.water_ml:.3f} mL; "
                  f"factible búsqueda/selección={row['feasible']}", flush=True)
    winner = min(candidates, key=lambda item: (item[0], item[1]))
    score_key, row_index, chosen, audits = winner
    base_factory = lambda: FixedPolicy(**base["policy"], anchor_date=local_timestamp(simulation.start, model.timezone).date())
    base_score, base_audits = evaluate_policy(None, banks["selection"], model, constraints, fixed_factory=base_factory)
    output = Path(output_dir).resolve() if output_dir else (path.parent/config["output_dir"]).resolve()
    output.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows)
    frame.to_csv(output/"pso_runs.csv", index=False)
    pd.DataFrame(histories).to_csv(output/"search_history.csv", index=False)
    summary = frame.groupby("variant").agg(runs=("seed", "count"), feasible_fraction=("feasible", "mean"),
                                          water_mean_ml=("selection_water_ml", "mean"),
                                          water_sd_ml=("selection_water_ml", "std"),
                                          duration_mean_s=("duration_s", "mean"))
    summary.to_csv(output/"search_summary.csv")
    policy_payload = {"status": "frozen" if not score_key[0] else "no_feasible_candidate",
                      "scope": "development_only", "data_origin": model.data_origin, "real_validation": False,
                      "policy": chosen if not score_key[0] else None, "best_candidate": chosen,
                      "selected_run": rows[row_index], "simulation": asdict(simulation),
                      "constraints": config["constraints"], "selection_audits": audits,
                      "search_audits": evaluate(chosen, "search")[1],
                      "base_selection": {"water_ml": base_score.water_ml, "audits": base_audits},
                      "reserved_evaluation_seeds": config["seeds"]["evaluation"]}
    _write_json(output/"frozen_policy.json", policy_payload)
    serialized_banks = {name: [{"seed": s["seed"],
                        "loss_changes": [{"timestamp": str(c.timestamp), "multiplier": c.multiplier} for c in s["loss_changes"]],
                        "observation_errors_ml": {str(t): v for t, v in s["observation_errors_ml"].items()}}
                       for s in bank] for name, bank in banks.items()}
    _write_json(output/"development_scenarios.json", serialized_banks)
    try:
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        revision = None
    source_files = list(Path(__file__).parent.glob("*.py"))
    manifest = {"config": config, "parameters": params, "python": platform.python_version(),
                "numpy": np.__version__, "pandas": pd.__version__, "git_head": revision,
                "working_tree_changes_included": True, "data_origin": model.data_origin,
                "real_validation": False, "evaluation_bank_generated": False,
                "input_sha256": {k: sha256(p.read_bytes()).hexdigest() for k, p in {"config":path, **inputs}.items()},
                "source_sha256": {p.name: sha256(p.read_bytes()).hexdigest() for p in source_files},
                "unique_candidates": {k:len(v) for k,v in caches.items()},
                "cache_note": "Presupuesto cuenta llamadas lógicas; caché compartida para políticas efectivas idénticas. Duración incluye caché caliente.",
                "selection_rule": "Factibilidad en búsqueda y selección; menor agua de selección; empate por orden de corrida."}
    _write_json(output/"optimization_manifest.json", manifest)
    return policy_payload, output
