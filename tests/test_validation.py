"""Validación contra fixtures sintéticos etiquetados del generador de A."""
import json

import pandas as pd
import pytest

from src.macetas.calibration import calibrate, write_outputs
from src.macetas.data_io import load_dataset
from src.macetas.synthetic_data import generate_synthetic
from src.macetas.validation import run_validation
from .conftest import write_model_config


@pytest.fixture(scope="module")
def validation_inputs(tmp_path_factory):
    root = tmp_path_factory.mktemp("validation")
    generated = generate_synthetic(root / "data", seed=7, noise_g=0, resolution_g=0,
                                   pot_variation=0, drain_tau_minutes=0)
    config = generated["config"]
    model_config = write_model_config(root, config, n_boot=0)
    outputs = write_outputs(calibrate(model_config))
    return config, outputs["parametros_modelo"], root


@pytest.mark.parametrize("method,tolerance", [("rk4", .001), ("euler", .15)])
def test_validation_full_trajectory(validation_inputs, tmp_path, method, tolerance):
    config, parameters, _ = validation_inputs
    comparison, errors = run_validation(config, parameters, tmp_path, allow_synthetic=True, method=method)
    assert comparison.data_origin.eq("synthetic").all()
    assert errors.loc[errors.pot_id.eq("ALL"), "mae_ml"].iloc[0] < tolerance
    assert set(errors.pot_id) == {"ALL", "M01", "M02", "M03", "M04", "M05", "M06"}
    ds = load_dataset(config)
    reserved = ds.observations[ds.observations.split.eq("validation")
                               & ds.observations.reading_stage.ne("drainage_check")]
    assert len(comparison) == len(reserved) - 6
    assert set(comparison.row).isdisjoint(ds.observations.loc[ds.observations.split.eq("fit"), "row"])
    assert not json.loads((tmp_path / "validation_manifest.json").read_text())["real_validation"]
    assert pd.read_csv(tmp_path / "events.csv").kind.eq("irrigation").all()


def test_validation_rejects_changed_split(validation_inputs, tmp_path):
    config, parameters, _ = validation_inputs
    payload = json.loads(config.read_text())
    payload["data_dir"] = str(config.parent)
    payload["split"]["frozen"] = False
    changed = tmp_path / "data.json"
    changed.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="congelada"):
        run_validation(changed, parameters, tmp_path / "out", allow_synthetic=True)


def test_validation_requires_explicit_synthetic(validation_inputs, tmp_path):
    config, parameters, _ = validation_inputs
    with pytest.raises(ValueError, match="sintéticos"):
        run_validation(config, parameters, tmp_path)
