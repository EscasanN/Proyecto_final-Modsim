"""Utilidades de prueba. Todos los datos que se crean aquí son SINTÉTICOS."""

import json

import pandas as pd
import pytest

from src.macetas.data_io import OBSERVATION_COLUMNS, POT_COLUMNS, SCALE_COLUMNS
from src.macetas.synthetic_data import DEFAULT_BLOCKS

TZ = "-06:00"


def write_dataset(path, pots, observations, scale=None, windows=None, origins=("synthetic",), quality=None):
    """Escribe un conjunto mínimo con su configuración y devuelve la ruta de la configuración."""
    path.mkdir(parents=True, exist_ok=True)
    for name, rows, cols in (("macetas.csv", pots, POT_COLUMNS),
                             ("observaciones.csv", observations, OBSERVATION_COLUMNS),
                             ("balanza.csv", scale or [], SCALE_COLUMNS)):
        pd.DataFrame(rows, columns=list(cols)).to_csv(path / name, index=False)
    config = {
        "data_dir": ".",
        "files": {"pots": "macetas.csv", "observations": "observaciones.csv", "scale_checks": "balanza.csv"},
        "timezone": "America/Guatemala",
        "water_density_g_per_ml": 1.0,
        "allowed_data_origins": list(origins),
        "split": {"frozen": True, "windows": windows or []},
        "quality": {"exclude_flags": ["bad"], "tolerance_sigmas": 3.0, "mass_tolerance_g": None,
                    "drainage_excess_tolerance_ml": 2.0, **(quality or {})},
        "outputs": {"processed_dir": "out/processed", "tables_dir": "out/tables"},
    }
    cfg_path = path / "data_config.json"
    cfg_path.write_text(json.dumps(config), encoding="utf-8")
    return cfg_path


def pot(pot_id="M01", mass=1000.0, origin="synthetic"):
    return {"pot_id": pot_id, "species": "x", "substrate": "x", "location": "x", "treatment": "base",
            "reference_mass_g": mass, "reference_timestamp": f"2000-01-01T06:00:00{TZ}", "data_origin": origin}


def obs(ts, stage="no_irrigation", mass=990.0, pot_id="M01", phase="fit", origin="synthetic", **extra):
    row = {"timestamp": f"2000-01-01T{ts}{TZ}" if "T" not in ts else ts, "pot_id": pot_id, "observer": "A",
           "phase": phase, "treatment": "base", "reading_stage": stage, "mass_g": mass,
           "quality_flag": "ok", "data_origin": origin}
    row.update(extra)
    return row


def scale_rows(sd_values=(500.0, 500.2, 499.8, 500.0), resolution=0.1):
    return [{"timestamp": f"2000-01-01T05:0{i}:00{TZ}", "observer": "A", "scale_id": "S", "object_id": "pesa",
             "known_mass_g": 500.0, "reading_g": v, "resolution_g": resolution, "data_origin": "synthetic"}
            for i, v in enumerate(sd_values)]


def write_model_config(path, data_config, n_boot=0, candidates=("constant", "blocks", "blocks_linear")):
    config = {
        "data_config": str(data_config),
        "time_blocks": DEFAULT_BLOCKS,
        "calibration": {
            "candidate_models": list(candidates),
            "selection": {"criterion": "aicc", "tolerance": 2.0},
            "scope": "pooled", "min_interval_h": 1.0, "max_interval_h": 36.0,
            "bounds": {"a_ml_per_h": [0.0, 50.0], "b_per_h": [-0.1, 0.0], "q": [0.0, 5.0]},
            "bootstrap": {"n": n_boot, "seed": 1, "unit": "day"},
        },
    }
    out = path / "model.json"
    out.write_text(json.dumps(config), encoding="utf-8")
    return out


@pytest.fixture(scope="session")
def exact_synthetic(tmp_path_factory):
    """Datos sintéticos sin ruido ni variación entre macetas y con drenaje instantáneo."""
    from src.macetas.synthetic_data import generate_synthetic

    out = tmp_path_factory.mktemp("exact")
    return generate_synthetic(out, seed=7, noise_g=0.0, resolution_g=0.0, pot_variation=0.0, drain_tau_minutes=0.0)


@pytest.fixture(scope="session")
def noisy_synthetic(tmp_path_factory):
    from src.macetas.synthetic_data import generate_synthetic

    out = tmp_path_factory.mktemp("noisy")
    return generate_synthetic(out, seed=11)
