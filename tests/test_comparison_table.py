import pandas as pd
import pytest

from src.macetas.comparison_table import build_table, lieth_summary, to_markdown


def test_lieth_summary_excludes_lower_bounds():
    s = lieth_summary("data/reference/lieth_ucdavis/agua_aplicada.csv")
    assert s["n"] == 6 and s["excluded"] == 2
    assert s["grower_median"] == pytest.approx((247 + 345) / 2)
    savings = sorted(100 * (g - t) / g for g, t in [(345, 265), (109, 105), (247, 165), (420, 238), (544, 422), (239, 83)])
    assert s["saving_median"] == pytest.approx((savings[2] + savings[3]) / 2)


def test_table_uses_committed_outputs_and_labels_origins():
    table, info = build_table("data/reference/lieth_ucdavis/agua_aplicada.csv",
                              "results/experiments/synthetic", "results/validation/public_enset")
    water = table.iloc[0]
    assert water["cambio_absoluto"] == pytest.approx(water["simulacion_mejorada"] - water["simulacion_base"])
    runs = pd.read_csv("results/experiments/synthetic/runs.csv")
    assert water["simulacion_base"] == pytest.approx(runs.query("condition == 'B0'").total_irrigation_ml.mean() / 7)
    assert info["simulation"]["origin"] == "synthetic" and info["validation"]["origin"] == "public"
    text = to_markdown(table, info)
    assert "no se afirma una reducción observada" in text


def test_table_with_same_system_control_reference():
    table, info = build_table("data/reference/lieth_ucdavis/agua_aplicada.csv", "results/experiments/public_enset",
                              "results/validation/public_enset",
                              "data/reference/chase2026_enset/converted/data_config.json")
    water = table.iloc[0]
    assert water["referencia_real"] == pytest.approx(info["control"]["irrigation_mean_ml_per_day"])
    assert info["simulation"]["origin"] == "public" and info["simulation"]["pot_id"] == "E12"
    paired = pd.read_csv("results/experiments/public_enset/paired.csv")
    feasible = paired[(paired.sensitivity == 0) & paired.both_feasible]
    assert info["simulation"]["saving_pct"] == pytest.approx(feasible.saving_pct.mean())
