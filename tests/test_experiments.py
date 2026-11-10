"""Pruebas de D: datos analíticos o sintéticos, nunca observaciones reales."""
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from src.macetas.constraints import ConstraintConfig
from src.macetas.experiments import read_json, run_experiments
from src.macetas.metrics import compute_metrics, paired_differences, summarize_runs, validation_errors
from src.macetas.model import LossModel
from src.macetas.optimization import development_bank, validate_seed_banks
from src.macetas.plots import generate_plots
from src.macetas.policies import FixedPolicy
from src.macetas.simulator import SimulationConfig, simulate


@pytest.mark.parametrize("method", ["euler", "rk4"])
def test_metrics_balance_refill_and_infeasibility(method):
    model = LossModel(2, 0, {"all": 1}, [{"name": "all", "start_hour": 0, "end_hour": 24}])
    config = SimulationConfig("2000-01-01T00:00:00-06:00", "2000-01-02T00:00:00-06:00",
                              method=method, safe_deficit_ml=100, max_dose_ml=100, max_daily_ml=200)
    result = simulate(model, config)
    metrics = compute_metrics(result, ConstraintConfig(config), 0.5)
    assert metrics == {"total_irrigation_ml": 48, "final_refill_ml": 48, "drainage_ml": 0,
                       "max_deficit_ml": 48, "time_over_limit_h": 0, "n_irrigations": 0,
                       "n_final_refills": 1, "duration_s": .5, "feasible": True, "violation": 0}
    assert abs(result.metrics["balance_residual_ml"]) < 1e-9
    result = simulate(model, config, FixedPolicy(60, (7,)))
    metrics = compute_metrics(result, ConstraintConfig(config), 0)
    assert metrics["n_irrigations"] == 1
    assert metrics["drainage_ml"] == 46
    assert metrics["total_irrigation_ml"] == 94
    unsafe = replace(config, safe_deficit_ml=10)
    result = simulate(model, unsafe)
    metrics = compute_metrics(result, ConstraintConfig(unsafe), 0)
    assert not metrics["feasible"]
    assert metrics["time_over_limit_h"] == pytest.approx(19, abs=1e-6)
    with pytest.raises(ValueError):
        compute_metrics(result, ConstraintConfig(unsafe), np.nan)


def test_errors():
    metrics = validation_errors([1, 2, 3], [2, 0, 6])
    assert metrics["mae_ml"] == 2
    assert metrics["rmse_ml"] == pytest.approx(np.sqrt(14/3))
    assert metrics["bias_ml"] == pytest.approx(2/3)


@pytest.mark.parametrize("observed,predicted", [([], []), ([1], [1, 2]), ([None], [1]), ([1], [np.inf])])
def test_errors_reject_invalid(observed, predicted):
    with pytest.raises(ValueError):
        validation_errors(observed, predicted)


@pytest.fixture(scope="module")
def experiment_output(tmp_path_factory):
    output = tmp_path_factory.mktemp("experiments")
    runs, _ = run_experiments("configs/demo_experiments.json", allow_synthetic=True, output_dir=output)
    return runs, output


def test_final_evaluation_and_csv(experiment_output):
    runs, output = experiment_output
    assert runs.groupby("condition").size().to_dict() == {"B0": 30, "B1": 30, "O0": 30, "O1": 30}
    assert runs.data_origin.eq("synthetic").all()
    manifest = read_json(output / "manifest.json")
    assert not manifest["real_validation"]
    assert set(runs.seed) == set(manifest["seeds"]["evaluation"])
    assert set(runs.seed).isdisjoint(manifest["seeds"]["search"] + manifest["seeds"]["selection"])
    assert pd.read_csv(output / "balance.csv").balance_residual_ml.abs().max() < 1e-7
    assert len(pd.read_csv(output / "paired.csv")) == 60
    assert len(pd.read_csv(output / "summary.csv")) == 4
    assert runs.groupby("condition").total_irrigation_ml.std().gt(0).all()


def test_reproducibility(experiment_output, tmp_path):
    first, output = experiment_output
    second, _ = run_experiments("configs/demo_experiments.json", allow_synthetic=True, output_dir=tmp_path)
    pd.testing.assert_frame_equal(first.drop(columns="duration_s"), second.drop(columns="duration_s"))
    assert (output / "evaluation_scenarios.json").read_bytes() == (tmp_path / "evaluation_scenarios.json").read_bytes()
    pd.testing.assert_frame_equal(pd.read_csv(output / "trajectory.csv"), pd.read_csv(tmp_path / "trajectory.csv"))


def test_figures(experiment_output, tmp_path):
    _, output = experiment_output
    generate_plots(output, output_dir=tmp_path)
    assert len(list(tmp_path.glob("*.png"))) == 3
    assert len(list(tmp_path.glob("*.pdf"))) == 3
    assert all(p.stat().st_size > 1000 for p in tmp_path.iterdir())


def test_paired_savings_and_zero_reference(experiment_output):
    runs, _ = experiment_output
    runs = runs.copy()
    runs.loc[runs.condition.str.startswith("B"), "total_irrigation_ml"] = 0
    paired = paired_differences(runs)
    assert paired.saving_pct.isna().all()
    assert not paired.optimized_better.any()
    runs.loc[runs.condition.str.startswith("O"), "feasible"] = False
    assert not paired_differences(runs).optimized_better.any()
    with pytest.raises(ValueError):
        paired_differences(runs.iloc[1:])
    summary = summarize_runs(runs)
    assert summary.loc[summary.condition.str.startswith("O"), "feasible_fraction"].eq(0).all()


def test_seed_banks_and_environment():
    cfg = read_json("configs/demo_pso.json")
    validate_seed_banks(cfg["seeds"])
    cfg["seeds"]["selection"] = cfg["seeds"]["search"]
    with pytest.raises(ValueError):
        validate_seed_banks(cfg["seeds"])
    from src.macetas.model import load_calibrated_model
    model = load_calibrated_model("results/synthetic_calibration/parametros_modelo.json", allow_synthetic=True)
    simulation = SimulationConfig(**read_json("results/optimization/synthetic/frozen_policy.json")["simulation"])
    a = development_bank([1, 2], model, simulation, {"daily_cv": .1, "multiplier": 1}, .3)
    b = development_bank([1, 2], model, simulation, {"daily_cv": .1, "multiplier": 1}, .3)
    assert a == b
    assert a[0]["loss_changes"] != a[1]["loss_changes"]


def test_pending_and_synthetic_are_guarded(tmp_path):
    with pytest.raises(ValueError, match="pendiente"):
        run_experiments("configs/experiments.json", output_dir=tmp_path)
    with pytest.raises(ValueError, match="sintéticos"):
        run_experiments("configs/demo_experiments.json", output_dir=tmp_path)


@pytest.mark.parametrize("change,match", [("status", "factible"), ("seeds", "reserva"),
                                        ("simulation", "horizonte"), ("provenance", "cambiaron")])
def test_frozen_contract_guards(monkeypatch, tmp_path, change, match):
    from src.macetas import experiments
    original = experiments.read_json

    def modified(path):
        payload = original(path)
        if str(path).endswith("frozen_policy.json"):
            if change == "status":
                payload["status"] = "no_feasible_candidate"
            elif change == "seeds":
                payload["reserved_evaluation_seeds"] = [1]
            elif change == "simulation":
                payload["simulation"]["initial_deficit_ml"] = 1
        if str(path).endswith("optimization_manifest.json") and change == "provenance":
            payload["input_sha256"]["parameters"] = "different"
        return payload

    monkeypatch.setattr(experiments, "read_json", modified)
    with pytest.raises(ValueError, match=match):
        run_experiments("configs/demo_experiments.json", allow_synthetic=True, output_dir=tmp_path)
