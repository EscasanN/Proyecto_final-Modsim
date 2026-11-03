import json
from dataclasses import replace
from math import exp

import pandas as pd
import pytest

from src.macetas.__main__ import main
from src.macetas.calibration import calibrate, parameters_for_model
from src.macetas.model import LossModel, apply_irrigation, load_calibrated_model
from src.macetas.policies import FixedPolicy
from src.macetas.simulation_io import run_from_files
from src.macetas.simulator import IrrigationEvent, LossChange, SimulationConfig, simulate
from src.macetas.verification import verify_numerics

from .conftest import write_model_config


BLOCKS = [{"name": "day", "start_hour": 6, "end_hour": 18},
          {"name": "night", "start_hour": 18, "end_hour": 6}]


def model(a=2.0, b=0.0, night=0.5):
    return LossModel(a, b, {"day": 1.0, "night": night}, BLOCKS)


def config(**values):
    return SimulationConfig(**{"start": "2000-01-01T17:00:00-06:00",
                               "end": "2000-01-02T07:00:00-06:00",
                               "initial_deficit_ml": 5.0, "step_h": 7.0,
                               "close_balance": False, **values})


@pytest.mark.parametrize("method", ["euler", "rk4"])
def test_block_boundaries_and_observations_split_large_steps(method):
    observation = pd.Timestamp("2000-01-01T17:23:00-06:00")
    result = simulate(model(), config(method=method), observation_times=[observation])
    assert result.metrics["final_deficit_ml"] == pytest.approx(21.0)
    timestamps = result.trajectory["timestamp"]
    for time in (observation, pd.Timestamp("2000-01-01T18:00:00-06:00"),
                 pd.Timestamp("2000-01-02T06:00:00-06:00")):
        assert time in set(timestamps)
    assert result.metrics["balance_residual_ml"] == pytest.approx(0.0, abs=1e-10)


@pytest.mark.parametrize("deficit,dose,after,drain", [(40, 60, 0, 20), (40, 10, 30, 0),
                                                    (40, 0, 40, 0), (0, 60, 0, 60)])
def test_event_conserves_water(deficit, dose, after, drain):
    balance = apply_irrigation(deficit, dose)
    assert balance.deficit_ml == after
    assert balance.drainage_ml == drain
    assert deficit - dose + drain == after
    assert balance.retained_ml + balance.drainage_ml == dose


@pytest.mark.parametrize("method", ["euler", "rk4"])
def test_irregular_irrigation_is_processed_once_at_exact_instant(method):
    time = "2000-01-01T17:17:00-06:00"
    result = simulate(model(a=0), config(method=method, initial_deficit_ml=40),
                      irrigation_events=[IrrigationEvent(time, 60.0, "E1")])
    assert len(result.events) == 1
    event = result.events.iloc[0]
    assert event["timestamp"] == pd.Timestamp(time)
    assert event["deficit_before_ml"] == 40
    assert event["deficit_after_ml"] == 0
    assert result.metrics["drainage_ml"] == 20


def test_events_share_block_boundaries_without_integrating_jump():
    result = simulate(model(), config(), irrigation_events=[IrrigationEvent("2000-01-01T18:00:00-06:00", 10)])
    assert result.events.iloc[0]["deficit_before_ml"] == pytest.approx(7)
    assert result.events.iloc[0]["drainage_ml"] == pytest.approx(3)
    assert result.metrics["final_deficit_ml"] == pytest.approx(14)


def test_fixed_policy_uses_review_times_and_excludes_horizon_end():
    cfg = config(start="2000-01-01T07:00:00-06:00", end="2000-01-02T07:00:00-06:00")
    result = simulate(model(a=0), cfg, FixedPolicy(10))
    assert len(result.events) == 1
    assert result.events.iloc[0]["timestamp"] == pd.Timestamp(cfg.start)
    assert result.metrics["total_irrigation_ml"] == 10


def test_final_refill_is_counted_and_cannot_bypass_dose_limit():
    cfg = config(initial_deficit_ml=0, close_balance=True, safe_deficit_ml=100,
                 max_dose_ml=10, max_daily_ml=100)
    result = simulate(model(), cfg)
    assert result.metrics["final_refill_ml"] == pytest.approx(16)
    assert result.metrics["total_irrigation_ml"] == pytest.approx(16)
    assert result.metrics["final_deficit_ml"] == 0
    assert result.metrics["closure_ok"]
    assert not result.metrics["dose_ok"]
    assert not result.metrics["feasible"]


def test_daily_budget_includes_final_refill():
    cfg = config(start="2000-01-01T07:00:00-06:00", end="2000-01-01T17:00:00-06:00",
                 initial_deficit_ml=0, close_balance=True, safe_deficit_ml=100,
                 max_dose_ml=100, max_daily_ml=20)
    result = simulate(model(), cfg, FixedPolicy(10))
    assert result.metrics["total_irrigation_ml"] == pytest.approx(30)
    assert not result.metrics["daily_budget_ok"]


def test_wetter_final_state_is_reported_as_incomparable():
    cfg = config(initial_deficit_ml=40, close_balance=True, safe_deficit_ml=100,
                 max_dose_ml=100, max_daily_ml=100)
    result = simulate(model(a=0), cfg, irrigation_events=[IrrigationEvent(cfg.start, 60)])
    assert result.metrics["final_deficit_ml"] == 0
    assert not result.metrics["closure_ok"]
    assert not result.metrics["feasible"]


def test_maximum_and_time_over_limit_include_state_before_irrigation():
    cfg = config(start="2000-01-01T06:00:00-06:00", end="2000-01-01T18:00:00-06:00",
                 initial_deficit_ml=0, safe_deficit_ml=10, step_h=20)
    result = simulate(model(), cfg, irrigation_events=[IrrigationEvent("2000-01-01T17:00:00-06:00", 30)])
    assert result.metrics["max_deficit_ml"] == pytest.approx(22)
    assert result.metrics["time_over_limit_h"] == pytest.approx(6)
    assert not result.metrics["safe_deficit_ok"]


def test_loss_changes_are_exogenous_and_split_steps():
    cfg = config(start="2000-01-01T06:00:00-06:00", end="2000-01-01T18:00:00-06:00")
    result = simulate(model(), cfg, loss_changes=[LossChange("2000-01-01T10:15:00-06:00", 1.2)])
    assert result.metrics["final_deficit_ml"] == pytest.approx(5 + 2 * 4.25 + 2.4 * 7.75)


def test_observation_errors_are_only_passed_to_policy_and_are_reproducible():
    class RecordingPolicy:
        def __init__(self):
            self.readings = []

        def dose(self, timestamp, observed_deficit_ml):
            self.readings.append(observed_deficit_ml)
            return 0

    cfg = config(start="2000-01-01T07:00:00-06:00", end="2000-01-01T08:00:00-06:00")
    policy = RecordingPolicy()
    result = simulate(model(a=0), cfg, policy, observation_errors_ml={cfg.start: -2.0})
    assert policy.readings == [3]
    assert result.metrics["final_deficit_ml"] == 5
    compact = simulate(model(a=0), cfg, FixedPolicy(0), record_trajectory=False)
    assert result.metrics == compact.metrics
    assert compact.trajectory.empty


@pytest.mark.parametrize("method", ["euler", "rk4"])
def test_zero_loss_and_dry_clipping(method):
    result = simulate(model(a=0), config(method=method))
    assert result.metrics["final_deficit_ml"] == 5
    result = simulate(model(a=1, b=-0.01), config(method=method, initial_deficit_ml=200))
    assert result.metrics["final_deficit_ml"] == 200


def test_unstable_step_is_rejected_instead_of_clipping_state():
    with pytest.raises(ValueError, match="equilibrio"):
        simulate(model(a=1, b=-1), config(start="2000-01-01T07:00:00-06:00", end="2000-01-01T12:00:00-06:00",
                                        initial_deficit_ml=0, method="euler", step_h=10))


@pytest.mark.parametrize("changes", [{"step_h": 0}, {"step_h": float("nan")}, {"method": "bad"},
                                     {"initial_deficit_ml": -1}, {"safe_deficit_ml": -1},
                                     {"review_hours": (7, 7)}])
def test_invalid_configuration_is_rejected(changes):
    with pytest.raises(ValueError):
        config(**changes)


def test_invalid_event_times_and_missing_timezone_are_rejected():
    cfg = config()
    with pytest.raises(ValueError, match="zona horaria"):
        simulate(model(), replace(cfg, start="2000-01-01T17:00:00"))
    with pytest.raises(ValueError, match="único"):
        simulate(model(), cfg, irrigation_events=[IrrigationEvent(cfg.end, 10)])
    with pytest.raises(ValueError, match="único"):
        simulate(model(), cfg, irrigation_events=[IrrigationEvent(cfg.start, 10), IrrigationEvent(cfg.start, 20)])
    with pytest.raises(ValueError, match="política"):
        simulate(model(), cfg, FixedPolicy(10), irrigation_events=[IrrigationEvent(cfg.start, 10)])


def test_calibration_export_connects_to_simulator(exact_synthetic, tmp_path):
    result = calibrate(write_model_config(tmp_path, exact_synthetic["config"]))
    path = tmp_path / "parameters.json"
    path.write_text(json.dumps(parameters_for_model(result)), encoding="utf-8")
    with pytest.raises(ValueError, match="sintéticos"):
        load_calibrated_model(path)
    loaded = load_calibrated_model(path, allow_synthetic=True)
    cfg = config(start="2000-01-01T06:00:00-06:00", end="2000-01-01T18:00:00-06:00", step_h=0.25)
    prediction = simulate(loaded, cfg)
    a, b = loaded.a_ml_per_h, loaded.b_per_h
    expected = (5 + a / b) * exp(b * 12) - a / b
    assert prediction.metrics["final_deficit_ml"] == pytest.approx(expected, abs=1e-8)
    payload = json.loads(path.read_text())
    payload["selected_scope"] = "per_pot"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="pot_id"):
        load_calibrated_model(path, allow_synthetic=True)
    assert load_calibrated_model(path, pot_id="M01", allow_synthetic=True).data_origin == "synthetic"


def test_cli_demo_is_reproducible_and_pending_real_base_is_refused(tmp_path):
    args = ["simulate", "--parameters", "configs/demo_parameters.json", "--base", "configs/demo_base.json",
            "--allow-synthetic", "--out", str(tmp_path)]
    assert main(args) == 0
    first = (tmp_path / "metricas.json").read_bytes()
    assert main(args) == 0
    assert first == (tmp_path / "metricas.json").read_bytes()
    assert json.loads(first)["real_validation"] is False
    assert main(["simulate", "--parameters", "configs/demo_parameters.json"]) == 1
    with pytest.raises(ValueError, match="pendiente"):
        run_from_files("configs/model.json", "configs/base.json", "configs/demo_parameters.json",
                       tmp_path, allow_synthetic=True)


def test_verification_exports_expected_orders(tmp_path):
    paths = verify_numerics(tmp_path)
    assert json.loads(paths["summary"].read_text())["passed"]
    table = pd.read_csv(paths["convergence"])
    assert table["data_origin"].eq("analytical").all()
    assert table.loc[table["method"].eq("rk4"), "absolute_error_ml"].iloc[-1] < 1e-8
