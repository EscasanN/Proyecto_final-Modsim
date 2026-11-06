"""Pruebas C con casos analíticos/sintéticos, nunca observaciones reales."""
from dataclasses import replace
import json

import numpy as np
import pandas as pd
import pytest

from src.macetas.constraints import ConstraintConfig, check_constraints
from src.macetas.model import LossModel
from src.macetas.optimization import (decode_candidate, development_bank, evaluate_policy,
                                      make_policy, run_optimization, validate_seed_banks)
from src.macetas.policies import ThresholdPolicy, FixedPolicy
from src.macetas.pso import Score, search
from src.macetas.simulator import SimulationConfig, simulate


@pytest.fixture
def setup():
    model = LossModel(2, 0, {"all":1}, [{"name":"all", "start_hour":0, "end_hour":24}])
    sim = SimulationConfig("2000-01-01T00:00:00-06:00", "2000-01-02T00:00:00-06:00",
                           safe_deficit_ml=40, max_dose_ml=50, max_daily_ml=100)
    return model, ConstraintConfig(sim)


def test_threshold_quantization_schedule_and_daily_budget():
    p = ThresholdPolicy(10, 2, 20, 40, 25, resolution_ml=3, max_irrigations_per_day=2)
    assert p.dose(pd.Timestamp("2000-01-01T06:00:00-06:00"), 50) == 0
    assert p.dose(pd.Timestamp("2000-01-01T07:00:00-06:00"), 10) == 6
    assert p.dose(pd.Timestamp("2000-01-01T13:00:00-06:00"), 50) == 18
    assert p.dose(pd.Timestamp("2000-01-01T19:00:00-06:00"), 50) == 0
    assert p.dose(pd.Timestamp("2000-01-02T07:00:00-06:00"), 50) == 18
    with pytest.raises(ValueError):
        p.dose(pd.Timestamp("2000-01-02T07:00:00-06:00"), 50)


@pytest.mark.parametrize("z", ([0,0,0],[1,1,1],[.5,.9,.3]))
def test_repair(z, setup):
    _, constraints = setup
    p = make_policy(decode_candidate(z, constraints), constraints)
    assert 0 <= p.target_ml < p.activation_ml <= 40
    assert 1 <= p.dose_max_ml <= 50


def test_pso_reproducibility_budget_and_known_minimum():
    objective = lambda z: Score(float(np.sum((z-.37)**2)))
    a = search(objective, seed=7, particles=12, iterations=60)
    b = search(objective, seed=7, particles=12, iterations=60)
    np.testing.assert_array_equal(a.position, b.position)
    assert a.history == b.history
    assert a.evaluations == 720
    assert a.score.water_ml < 1e-6
    assert all(a.history[i+1]["water_ml"] <= a.history[i]["water_ml"] for i in range(59))
    calls = []
    search(lambda x: (calls.append(x) or objective(x)), seed=1, particles=7, iterations=3, algorithm="random")
    assert len(calls) == 21


def test_feasibility_precedes_water():
    assert Score(1000, 0).key < Score(0, .001).key < Score(0, 1).key
    with pytest.raises(ValueError):
        Score(float("nan"))


def test_independent_audit_and_closure(setup):
    model, constraints = setup
    result = simulate(model, constraints.simulation, FixedPolicy(20, (7,13,19)))
    result.metrics.clear()  # la auditoría no depende de lo que reporta el motor
    audit = check_constraints(result.trajectory, result.events, constraints)
    assert audit["feasible"]
    assert audit["total_irrigation_ml"] == pytest.approx(70)  # 22 de drenaje + 48 de pérdida
    bad = result.events.copy()
    bad.loc[0, "timestamp"] += pd.Timedelta(hours=1)
    assert "schedule" in check_constraints(result.trajectory, bad, constraints)["violations"]
    bad = result.events.copy()
    bad.loc[0, "irrigation_ml"] = 1000
    assert "dose" in check_constraints(result.trajectory, bad, constraints)["violations"]
    bad = result.trajectory.copy()
    bad.loc[2, "deficit_ml"] = np.nan
    assert not check_constraints(bad, result.events, constraints)["feasible"]


def test_no_irrigation_violates_safety_and_refill_is_charged(setup):
    model, constraints = setup
    result = simulate(model, constraints.simulation, FixedPolicy(0))
    audit = check_constraints(result.trajectory, result.events, constraints)
    assert "safe_deficit" in audit["violations"]
    assert audit["total_irrigation_ml"] == 48
    strict = replace(constraints, simulation=replace(constraints.simulation, max_dose_ml=20))
    assert "dose" in check_constraints(result.trajectory, result.events, strict)["violations"]


def test_frequency_resolution_and_daily_audit(setup):
    model, constraints = setup
    result = simulate(model, constraints.simulation, FixedPolicy(15, (7,13,19)))
    strict = replace(constraints, max_irrigations_per_day=1, resolution_ml=2,
                     simulation=replace(constraints.simulation, max_daily_ml=30))
    errors = check_constraints(result.trajectory, result.events, strict)["violations"]
    assert {"frequency", "resolution", "daily"} <= errors.keys()


def test_forcing_and_repeated_evaluation(setup):
    model, constraints = setup
    bank = development_bank([4,5], model, constraints.simulation, {"daily_cv":.1,"multiplier":1}, .3)
    assert bank == development_bank([4,5], model, constraints.simulation, {"daily_cv":.1,"multiplier":1}, .3)
    candidate = {"activation_ml":20, "target_ml":0, "dose_max_ml":40}
    assert evaluate_policy(candidate, bank, model, constraints) == evaluate_policy(candidate, bank, model, constraints)


def test_seed_leakage_and_pending_config():
    with pytest.raises(ValueError, match="disjuntos"):
        validate_seed_banks({"search":[1],"selection":[2],"evaluation":[1],"optimizer":[3]})
    with pytest.raises(ValueError, match="pendiente"):
        run_optimization("configs/pso.json")
    with pytest.raises(ValueError, match="synthetic"):
        run_optimization("configs/demo_pso.json")


def test_rounding_does_not_create_constant_loss_saving(setup):
    model, constraints = setup
    bank = development_bank([1], model, constraints.simulation, {"daily_cv":0,"multiplier":1}, 0)
    a, _ = evaluate_policy({"activation_ml":10,"target_ml":0,"dose_max_ml":40}, bank, model, constraints)
    b, _ = evaluate_policy({"activation_ml":30,"target_ml":10,"dose_max_ml":40}, bank, model, constraints)
    assert a.water_ml == b.water_ml == 48


@pytest.mark.parametrize("impossible", [False, True])
def test_export_contract_and_no_feasible_candidate(tmp_path, impossible):
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    config = json.loads((root/"configs/demo_pso.json").read_text(encoding="utf-8"))
    for name in ("model", "parameters"):
        config[name] = str((root/"configs"/config[name]).resolve())
    base = json.loads((root/"configs/demo_base.json").read_text(encoding="utf-8"))
    base["simulation"]["end"] = "2000-01-04T00:00:00-06:00"
    if impossible:
        base["simulation"]["safe_deficit_ml"] = 1
    base_path = tmp_path/"base.json"
    base_path.write_text(json.dumps(base), encoding="utf-8")
    config["base"] = str(base_path)
    config["budget"] = {"particles":1, "iterations":1}
    config["variants"] = [{"name":"random", "algorithm":"random"}]
    config["seeds"]["search"] = [11001]
    config["seeds"]["selection"] = [12001]
    config_path = tmp_path/"pso.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    payload, output = run_optimization(config_path, allow_synthetic=True, output_dir=tmp_path/"out")
    rows = pd.read_csv(output/"pso_runs.csv")
    assert len(rows) == 30 and rows.evaluations.eq(1).all()
    manifest = json.loads((output/"optimization_manifest.json").read_text(encoding="utf-8"))
    assert manifest["evaluation_bank_generated"] is False
    assert set(json.loads((output/"development_scenarios.json").read_text())) == {"search", "selection"}
    assert payload["real_validation"] is False
    assert payload["data_origin"] == "synthetic"
    if impossible:
        assert payload["status"] == "no_feasible_candidate" and payload["policy"] is None
    else:
        assert payload["status"] == "frozen"
        assert all(a["feasible"] for a in payload["selection_audits"] + payload["search_audits"])
