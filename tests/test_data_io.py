import json

import numpy as np
import pytest

from src.macetas.data_io import load_data_config, load_dataset, parse_windows, scale_statistics

from .conftest import obs, pot, scale_rows, write_dataset

FIT_WINDOW = [{"phase": "fit", "start": "2000-01-01T00:00:00-06:00", "end": "2000-01-02T00:00:00-06:00"}]


def checks(ds, severity):
    return set(ds.issues.loc[ds.issues["severity"] == severity, "check"])


def test_repository_templates_load_without_errors():
    ds = load_dataset("configs/data.json")
    assert ds.n_errors == 0
    assert len(ds.observations) == 0


def test_clean_dataset_and_deficit(tmp_path):
    cfg = write_dataset(tmp_path, [pot(mass=1000.0)],
                        [obs("07:00:00", mass=990.0), obs("13:00:00", mass=975.5)], scale_rows(), FIT_WINDOW)
    ds = load_dataset(cfg)
    assert ds.n_errors == 0, ds.issues
    assert ds.observations["deficit_ml"].tolist() == pytest.approx([10.0, 24.5])
    assert ds.observations["split"].tolist() == ["fit", "fit"]


def test_missing_values_stay_missing(tmp_path):
    rows = [obs("07:00:00", stage="pre_irrigation", event_id="E1"),
            obs("07:30:00", stage="post_drainage", event_id="E1", irrigation_ml=100,
                irrigation_timestamp="2000-01-01T07:02:00-06:00"),
            obs("13:00:00", mass=None)]
    ds = load_dataset(write_dataset(tmp_path, [pot()], rows, scale_rows(), FIT_WINDOW))
    o = ds.observations
    assert np.isnan(o.loc[1, "drainage_ml"])  # drenaje no medido: no se asume 0
    assert np.isnan(o.loc[2, "mass_g"]) and not o.loc[2, "usable"]
    assert "evento" in checks(ds, "warning") and "faltante" in checks(ds, "warning")


@pytest.mark.parametrize("bad_row, expected_check", [
    (obs("07:00:00").__or__({"timestamp": "2000-01-01T07:00:00"}), "zona_horaria"),
    (obs("07:00:00", pot_id="M99"), "maceta"),
    (obs("07:00:00", stage="no_irrigation", irrigation_ml=50), "evento"),
    (obs("07:00:00", stage="post_drainage", event_id="E1", irrigation_ml=-5), "negativo"),
    (obs("07:00:00", mass="abc"), "numerico"),
    (obs("07:00:00", reading_stage=None).__or__({"reading_stage": "regado"}), "categoria"),
    (obs("07:00:00", origin="observed"), "origen"),
    (obs("07:00:00", phase="validation"), "particion"),
    (obs("07:00:00", top_soil_dry="seco"), "categoria"),
])
def test_errors_are_detected(tmp_path, bad_row, expected_check):
    ds = load_dataset(write_dataset(tmp_path, [pot()], [obs("06:00:00"), bad_row], scale_rows(), FIT_WINDOW))
    assert expected_check in checks(ds, "error")


def test_duplicate_reading_is_error(tmp_path):
    ds = load_dataset(write_dataset(tmp_path, [pot()], [obs("07:00:00"), obs("07:00:00")], scale_rows(), FIT_WINDOW))
    assert "duplicado" in checks(ds, "error")


def test_real_config_rejects_synthetic_rows(tmp_path):
    cfg = write_dataset(tmp_path, [pot(origin="synthetic")], [obs("07:00:00")], origins=("observed",))
    ds = load_dataset(cfg)
    assert "origen" in checks(ds, "error")


def test_mass_gain_without_irrigation_and_negative_deficit_warned(tmp_path):
    rows = [obs("07:00:00", mass=990.0), obs("13:00:00", mass=1010.0)]
    ds = load_dataset(write_dataset(tmp_path, [pot(mass=1000.0)], rows, scale_rows(), FIT_WINDOW))
    assert {"aumento_masa", "deficit_negativo"} <= checks(ds, "warning")
    assert ds.observations["deficit_ml"].iloc[1] == pytest.approx(-10.0)  # se conserva


def test_scale_statistics():
    import pandas as pd

    frame = pd.DataFrame(scale_rows((500.0, 500.2, 499.8, 500.0)))
    stats = scale_statistics(frame)
    sd = np.std([500.0, 500.2, 499.8, 500.0], ddof=1)
    assert stats["repeatability_sd_g"] == pytest.approx(sd)
    assert stats["sigma_reading_g"] == pytest.approx(np.sqrt(sd ** 2 + 0.1 ** 2 / 12))
    assert stats["max_abs_bias_g"] == pytest.approx(0.0, abs=1e-9)


def test_windows_validation(tmp_path):
    split = {"windows": [{"phase": "fit", "start": "2000-01-01T00:00:00-06:00", "end": "2000-01-03T00:00:00-06:00"},
                         {"phase": "validation", "start": "2000-01-02T00:00:00-06:00",
                          "end": "2000-01-04T00:00:00-06:00"}]}
    with pytest.raises(ValueError, match="solapan"):
        parse_windows(split, "America/Guatemala")
    with pytest.raises(ValueError, match="zona horaria"):
        parse_windows({"windows": [{"phase": "fit", "start": "2000-01-01T00:00:00", "end": "2000-01-02T00:00:00"}]},
                      "America/Guatemala")


def test_config_paths_are_relative_to_config_file():
    cfg = load_data_config("configs/data.json")
    assert cfg["_data_dir"].replace("\\", "/").endswith("data/raw")
    assert json.loads(open("configs/data.json", encoding="utf-8").read())["allowed_data_origins"] == ["observed"]
