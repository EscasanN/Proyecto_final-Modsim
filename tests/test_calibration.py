import json

import numpy as np
import pandas as pd
import pytest

from src.macetas.__main__ import main
from src.macetas.calibration import (
    IntervalSet, calibrate, drying_intervals, fit_model, irrigation_events, parameter_table,
    parameters_for_model, predict_deficit, write_outputs,
)
from src.macetas.data_io import load_dataset
from src.macetas.synthetic_data import DEFAULT_BLOCKS

from .conftest import obs, pot, scale_rows, write_dataset, write_model_config


def single_segment(hours, block=0):
    return np.array([[hours]]), np.array([[block]])


# --- Solución exacta ------------------------------------------------------------

def test_constant_loss_is_linear():
    h, k = single_segment(5.0)
    assert predict_deficit([10.0], h, k, a=2.0, b=0.0, q=[1.0, 0.5]) == pytest.approx([20.0])
    h, k = single_segment(5.0, block=1)
    assert predict_deficit([10.0], h, k, a=2.0, b=0.0, q=[1.0, 0.5]) == pytest.approx([15.0])


def test_linear_loss_matches_analytic_exponential():
    a, b, d0, t = 3.0, -0.02, 5.0, 7.0
    h, k = single_segment(t)
    expected = (d0 + a / b) * np.exp(b * t) - a / b
    assert predict_deficit([d0], h, k, a, b, [1.0]) == pytest.approx([expected])


def test_split_segments_equal_single_segment():
    a, b = 3.0, -0.02
    one = predict_deficit([5.0], *single_segment(6.0), a, b, [1.0])
    two = predict_deficit([5.0], np.array([[2.5, 3.5]]), np.array([[0, 0]]), a, b, [1.0])
    assert two == pytest.approx(one)


def test_no_loss_keeps_deficit_and_clip_stops_loss():
    h, k = single_segment(10.0)
    assert predict_deficit([12.0], h, k, 0.0, 0.0, [1.0]) == pytest.approx([12.0])
    # a + b*D <= 0: la pérdida está recortada a 0
    assert predict_deficit([200.0], h, k, 1.0, -0.01, [1.0]) == pytest.approx([200.0])


# --- Intervalos y fuga de información ---------------------------------------------

def test_intervals_skip_irrigation_and_other_phases(tmp_path):
    windows = [{"phase": "fit", "start": "2000-01-01T00:00:00-06:00", "end": "2000-01-02T00:00:00-06:00"},
               {"phase": "validation", "start": "2000-01-02T00:00:00-06:00", "end": "2000-01-03T00:00:00-06:00"}]
    rows = [
        obs("07:00:00", mass=990.0),
        obs("13:00:00", stage="pre_irrigation", mass=980.0, event_id="E1"),
        obs("13:30:00", stage="post_drainage", mass=999.0, event_id="E1", irrigation_ml=60, drainage_ml=40,
            irrigation_timestamp="2000-01-01T13:02:00-06:00"),
        obs("19:00:00", mass=992.0),
        obs("2000-01-02T07:00:00-06:00", mass=985.0, phase="validation"),
    ]
    ds = load_dataset(write_dataset(tmp_path, [pot()], rows, scale_rows(), windows))
    assert ds.n_errors == 0, ds.issues
    iv = drying_intervals(ds, DEFAULT_BLOCKS, "fit")
    assert list(zip(iv.frame["row_start"], iv.frame["row_end"])) == [(2, 3), (4, 5)]
    assert iv.frame["loss_ml"].tolist() == pytest.approx([10.0, 7.0])
    assert (iv.frame["split"] == "fit").all()


def test_fit_rejects_validation_intervals():
    frame = pd.DataFrame({"split": ["fit", "validation"], "deficit_start_ml": [0, 0], "deficit_end_ml": [1, 1],
                          "mean_rate_ml_per_h": [1, 1]})
    leaky = IntervalSet(frame, np.ones((2, 1)), np.zeros((2, 1), dtype=int))
    with pytest.raises(ValueError, match="Fuga"):
        fit_model(leaky, "constant", ["day", "night"], {"a_ml_per_h": [0, 50], "b_per_h": [-0.1, 0], "q": [0, 5]})


def test_irrigation_event_ideal_rule(tmp_path):
    """Caso del plan (8.1.5): déficit 40 mL + riego 60 mL -> déficit 0 y drenaje 20 mL."""
    rows = [obs("07:00:00", stage="pre_irrigation", mass=960.0, event_id="E1"),
            obs("07:30:00", stage="post_drainage", mass=1000.0, event_id="E1", irrigation_ml=60, drainage_ml=20,
                irrigation_timestamp="2000-01-01T07:01:00-06:00")]
    windows = [{"phase": "fit", "start": "2000-01-01T00:00:00-06:00", "end": "2000-01-02T00:00:00-06:00"}]
    ds = load_dataset(write_dataset(tmp_path, [pot(mass=1000.0)], rows, scale_rows(), windows))
    ev = irrigation_events(ds, DEFAULT_BLOCKS).iloc[0]
    assert ev["drainage_ideal_ml"] == pytest.approx(20.0)
    assert ev["deficit_post_ideal_ml"] == pytest.approx(0.0)
    assert ev["drainage_residual_ml"] == pytest.approx(0.0)
    assert ev["apparent_loss_ml"] == pytest.approx(0.0)  # balance cerrado
    assert ev["drain_minutes"] == pytest.approx(29.0)


# --- Recuperación de parámetros conocidos -------------------------------------------

def test_exact_data_recovers_true_parameters(exact_synthetic, tmp_path):
    truth = json.loads(exact_synthetic["truth"].read_text(encoding="utf-8"))["params"]
    result = calibrate(write_model_config(tmp_path, exact_synthetic["config"]))
    fit = result.selected["pooled"]
    assert fit.model == "blocks_linear"
    assert fit.a == pytest.approx(truth["a_ml_per_h"], rel=1e-4)
    assert fit.b == pytest.approx(truth["b_per_h"], rel=1e-3)
    assert fit.q == pytest.approx(truth["q"], rel=1e-4)
    assert fit.rmse < 1e-6


def test_simpler_model_selected_when_b_is_zero(tmp_path):
    from src.macetas.synthetic_data import generate_synthetic

    paths = generate_synthetic(tmp_path / "d", seed=3, noise_g=0.3, pot_variation=0.0,
                               params={"a_ml_per_h": 2.0, "b_per_h": 0.0, "q": [1.0, 0.4]})
    result = calibrate(write_model_config(tmp_path, paths["config"]))
    assert result.selected["pooled"].model == "blocks"
    assert result.selected["pooled"].q[1] == pytest.approx(0.4, abs=0.03)


def test_noisy_calibration_end_to_end(noisy_synthetic, tmp_path):
    truth = json.loads(noisy_synthetic["truth"].read_text(encoding="utf-8"))
    result = calibrate(write_model_config(tmp_path, noisy_synthetic["config"], n_boot=40))
    fit = result.selected["pooled"]
    assert fit.q[1] == pytest.approx(truth["params"]["q"][1], abs=0.03)
    # por maceta, a debe acercarse al valor verdadero de cada una
    for pot_id, p in truth["per_pot"].items():
        assert result.selected[pot_id].a == pytest.approx(p["a_ml_per_h"], rel=0.15)

    table = parameter_table(result)
    assert set(table["data_origin"]) == {"synthetic"}
    assert {"a_ml_per_h", "sigma_reading", "deficit_max_fit", "reference_mass"} <= set(table["parameter"])
    a_row = table.query("scope == 'pooled' and parameter == 'a_ml_per_h'").iloc[0]
    assert a_row["ci95_low"] < a_row["value"] < a_row["ci95_high"]

    params = parameters_for_model(result)
    assert params["data_origin"] == ["synthetic"] and params["status"] == "frozen"
    paths = write_outputs(result)
    assert all(p.exists() for p in paths.values())
    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    assert manifest["input_sha256"]["observations"] is not None


def test_reproducible_with_same_seed(exact_synthetic, tmp_path):
    cfg = write_model_config(tmp_path, exact_synthetic["config"], n_boot=10)
    t1, t2 = parameter_table(calibrate(cfg)), parameter_table(calibrate(cfg))
    pd.testing.assert_frame_equal(t1, t2)


def test_cli_validate_and_calibrate(noisy_synthetic, tmp_path):
    assert main(["validate-data", "--config", str(noisy_synthetic["config"])]) == 0
    model_cfg = write_model_config(tmp_path, noisy_synthetic["config"], n_boot=0)
    assert main(["calibrate", "--config", str(model_cfg)]) == 0


def test_calibrate_refuses_without_fit_window(tmp_path):
    cfg = write_dataset(tmp_path, [pot()], [obs("07:00:00")], scale_rows(), windows=[])
    with pytest.raises(ValueError, match="fit"):
        calibrate(write_model_config(tmp_path, cfg))


# --- Criterio de sustrato superficial seco -------------------------------------------

def test_top_dry_threshold_matches_generator(exact_synthetic, tmp_path):
    truth = json.loads(exact_synthetic["truth"].read_text(encoding="utf-8"))
    result = calibrate(write_model_config(tmp_path, exact_synthetic["config"]))
    dry = result.soil_dry.dropna(subset=["deficit_at_first_dry_ml"])
    assert len(dry) > 0
    # la primera lectura seca es la primera revisión con déficit >= umbral
    assert (dry["deficit_at_first_dry_ml"] >= truth["top_dry_deficit_ml"] - 1e-9).all()
    table = parameter_table(result)
    assert "deficit_top_dry_median" in set(table["parameter"])
    assert parameters_for_model(result)["top_soil_dry_deficit_ml"]["median"] is not None


def test_cycle_without_dry_reading_is_reported_as_missing(tmp_path):
    windows = [{"phase": "fit", "start": "2000-01-01T00:00:00-06:00", "end": "2000-01-02T00:00:00-06:00"}]
    rows = [obs("07:00:00", stage="pre_irrigation", mass=950.0, event_id="E1", top_soil_dry="yes"),
            obs("07:30:00", stage="post_drainage", mass=1000.0, event_id="E1", irrigation_ml=80, drainage_ml=30,
                irrigation_timestamp="2000-01-01T07:01:00-06:00"),
            obs("13:00:00", mass=990.0, top_soil_dry="no"),
            obs("19:00:00", mass=980.0, top_soil_dry="yes")]
    ds = load_dataset(write_dataset(tmp_path, [pot(mass=1000.0)], rows, scale_rows(), windows))
    assert ds.n_errors == 0, ds.issues
    from src.macetas.calibration import top_dry_thresholds

    out = top_dry_thresholds(ds)
    assert len(out) == 1  # el ciclo previo al primer riego no cuenta
    assert out["deficit_at_first_dry_ml"].iloc[0] == pytest.approx(20.0)
    assert out["hours_since_irrigation"].iloc[0] == pytest.approx(11.5)


def test_calibration_without_irrigation_events(tmp_path):
    """Un secado continuo (sin riegos) es válido: la tabla de eventos queda vacía."""
    windows = [{"phase": "fit", "start": "2000-01-01T00:00:00-06:00", "end": "2000-01-04T00:00:00-06:00"}]
    rows = [obs(f"2000-01-0{1 + i // 3}T{h:02d}:00:00-06:00", mass=1000.0 - 6.0 * i)
            for i, h in enumerate([7, 13, 19] * 3)]
    cfg = write_dataset(tmp_path, [pot(mass=1000.0)], rows, scale_rows(), windows)
    result = calibrate(write_model_config(tmp_path, cfg, candidates=("constant",)))
    assert len(result.events) == 0
    assert result.selected["pooled"].a > 0
    assert all(p.exists() for p in write_outputs(result).values())
