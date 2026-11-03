from __future__ import annotations

import hashlib
import json
import platform
from dataclasses import asdict
from pathlib import Path

from .model import load_calibrated_model, local_timestamp, nonnegative
from .policies import FixedPolicy
from .simulator import LossChange, SimulationConfig, simulate


def run_from_files(model_path, base_path, parameters_path, output_dir, pot_id=None,
                   allow_synthetic=False, method=None, step_h=None):
    model_path, base_path, parameters_path = map(Path, (model_path, base_path, parameters_path))
    model_config = json.loads(model_path.read_text(encoding="utf-8-sig"))
    base = json.loads(base_path.read_text(encoding="utf-8-sig"))
    model = load_calibrated_model(parameters_path, pot_id, allow_synthetic)
    if model.time_blocks != model_config["time_blocks"]:
        raise ValueError("Los bloques de calibración y del modelo no coinciden.")
    example = base.get("status") == "synthetic_example"
    if base.get("status") != "frozen" and not (example and allow_synthetic and model.data_origin == "synthetic"):
        raise ValueError("La política base está pendiente; se debe definir y congelar después del piloto.")
    if not base.get("justification"):
        raise ValueError("La política base necesita una justificación.")
    simulation = {**model_config.get("simulation", {}), **base["simulation"]}
    if method is not None:
        simulation["method"] = method
    if step_h is not None:
        simulation["step_h"] = step_h
    required = ("start", "end", "initial_deficit_ml", "safe_deficit_ml", "max_dose_ml", "max_daily_ml")
    if any(simulation.get(name) is None for name in required):
        raise ValueError("Faltan horizonte, estado inicial o restricciones de la simulación.")
    config = SimulationConfig(**simulation)
    policy_config = base["policy"]
    policy = FixedPolicy(nonnegative(policy_config["dose_ml"], "La dosis base"),
                         tuple(policy_config["irrigation_hours"]), policy_config.get("every_n_days", 1),
                         local_timestamp(config.start, model.timezone).date())
    if not set(policy.irrigation_hours) <= set(config.review_hours):
        raise ValueError("Los riegos deben coincidir con las horas de revisión.")
    multiplier = nonnegative(base.get("loss_multiplier", 1.0), "El factor de pérdida")
    result = simulate(model, config, policy, loss_changes=[LossChange(config.start, multiplier)])
    if model.data_origin == "synthetic":
        result.metrics["real_validation"] = False
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    paths = {"trajectory": output / "trayectoria.csv", "events": output / "riegos.csv",
             "metrics": output / "metricas.json", "manifest": output / "simulacion_manifest.json"}
    result.trajectory.to_csv(paths["trajectory"], index=False, encoding="utf-8-sig")
    result.events.to_csv(paths["events"], index=False, encoding="utf-8-sig")
    paths["metrics"].write_text(json.dumps(result.metrics, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    manifest = {"python": platform.python_version(), "data_origin": model.data_origin,
                "pot_id": pot_id, "simulation": asdict(config), "policy": base,
                "parameters": json.loads(parameters_path.read_text(encoding="utf-8-sig")),
                "input_sha256": {name: hashlib.sha256(path.read_bytes()).hexdigest()
                                 for name, path in (("model_config", model_path), ("base_config", base_path),
                                                    ("parameters", parameters_path))},
                "randomness": "none", "real_validation": False}
    paths["manifest"].write_text(json.dumps(manifest, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    return result, paths
