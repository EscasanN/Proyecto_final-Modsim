"""Tabla de la Parte 6: referencia real, simulación base y simulación mejorada.

Combina tres fuentes, cada una identificada en la tabla:

- Referencia real documentada: Lieth (UC Davis), agua aplicada por maceta con el
  riego del productor y con riego por tensiómetro (data/reference/lieth_ucdavis).
- Referencia real medida: Chase (2026), pérdida de agua observada en la ventana de
  validación (results/validation/public_enset).
- Simulación: experimentos B0 (base) y O0 (política congelada) de experiments.py.

La tabla no ajusta nada: solo resume salidas ya generadas. Los valores reales y
simulados provienen de especies y montajes distintos; la correspondencia se discute
en la nota que acompaña a la tabla.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def lieth_summary(path) -> dict:
    """Mediana y rango del agua aplicada y del ahorro, sin los experimentos con cota inferior."""
    df = pd.read_csv(path)
    valid = df[~df["grower_is_lower_bound"].astype(str).str.lower().eq("true")]
    savings = 100 * (valid["grower_ml_per_day"] - valid["tension_ml_per_day"]) / valid["grower_ml_per_day"]
    return {
        "n": len(valid), "excluded": int(len(df) - len(valid)),
        "grower_median": float(valid["grower_ml_per_day"].median()),
        "grower_range": (float(valid["grower_ml_per_day"].min()), float(valid["grower_ml_per_day"].max())),
        "tension_median": float(valid["tension_ml_per_day"].median()),
        "tension_range": (float(valid["tension_ml_per_day"].min()), float(valid["tension_ml_per_day"].max())),
        "saving_median": float(savings.median()),
        "saving_range": (float(savings.min()), float(savings.max())),
    }


def simulation_summary(experiment_dir) -> dict:
    root = Path(experiment_dir)
    runs = pd.read_csv(root / "runs.csv")
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    sim = manifest["simulation"]
    days = (pd.Timestamp(sim["end"]) - pd.Timestamp(sim["start"])).total_seconds() / 86400
    out = {"days": days, "origin": ", ".join(sorted(runs["data_origin"].unique()))}
    for cond in ("B0", "O0"):
        g = runs[runs["condition"] == cond]
        out[cond] = {"n": len(g), "water_per_day": float(g["total_irrigation_ml"].mean() / days),
                     "water_per_day_sd": float(g["total_irrigation_ml"].std(ddof=1) / days),
                     "feasible_pct": float(100 * g["feasible"].mean())}
    paired = pd.read_csv(root / "paired.csv")
    p0 = paired[paired["sensitivity"] == 0]
    out["saving_pct"] = float(p0["saving_pct"].mean())
    out["saving_pct_sd"] = float(p0["saving_pct"].std(ddof=1))
    out["both_feasible_pct"] = float(100 * p0["both_feasible"].mean())
    return out


def validation_summary(validation_dir) -> dict:
    """Pérdida diaria media por maceta (primera a última lectura comparada) y error del modelo."""
    comp = pd.read_csv(Path(validation_dir) / "comparisons.csv", parse_dates=["timestamp"])
    errors = pd.read_csv(Path(validation_dir) / "errors.csv").set_index("pot_id")
    rates = []
    for _, g in comp.sort_values("timestamp").groupby("pot_id"):
        days = (g["timestamp"].iloc[-1] - g["timestamp"].iloc[0]).total_seconds() / 86400
        rates.append({"observed": (g["observed_deficit_ml"].iloc[-1] - g["observed_deficit_ml"].iloc[0]) / days,
                      "predicted": (g["predicted_deficit_ml"].iloc[-1] - g["predicted_deficit_ml"].iloc[0]) / days})
    rates = pd.DataFrame(rates)
    return {"n_pots": len(rates), "observed": float(rates["observed"].mean()),
            "observed_sd": float(rates["observed"].std(ddof=1)),
            "predicted": float(rates["predicted"].mean()), "predicted_sd": float(rates["predicted"].std(ddof=1)),
            "mae": float(errors.loc["ALL", "mae_ml"]), "bias": float(errors.loc["ALL", "bias_ml"]),
            "origin": ", ".join(sorted(comp["data_origin"].unique()))}


def build_table(lieth_csv, experiment_dir, validation_dir) -> tuple[pd.DataFrame, dict]:
    ref, sim, val = lieth_summary(lieth_csv), simulation_summary(experiment_dir), validation_summary(validation_dir)
    b, o = sim["B0"], sim["O0"]
    rows = [
        {"metrica": "Agua aplicada por maceta", "unidad": "mL/maceta/día",
         "referencia_real": ref["grower_median"], "simulacion_base": b["water_per_day"],
         "simulacion_mejorada": o["water_per_day"],
         "cambio_absoluto": o["water_per_day"] - b["water_per_day"],
         "cambio_porcentual": 100 * (o["water_per_day"] - b["water_per_day"]) / b["water_per_day"],
         "fuente_referencia": f"Lieth: riego del productor, mediana de {ref['n']} experimentos "
                              f"(rango {ref['grower_range'][0]:.0f}–{ref['grower_range'][1]:.0f})",
         "fuente_simulacion": f"B0/O0, {b['n']} réplicas, {sim['days']:.0f} días, origen {sim['origin']}"},
        {"metrica": "Agua aplicada con la alternativa guiada por el déficit", "unidad": "mL/maceta/día",
         "referencia_real": ref["tension_median"], "simulacion_base": np.nan,
         "simulacion_mejorada": o["water_per_day"], "cambio_absoluto": np.nan, "cambio_porcentual": np.nan,
         "fuente_referencia": f"Lieth: riego por tensiómetro, mediana (rango "
                              f"{ref['tension_range'][0]:.0f}–{ref['tension_range'][1]:.0f})",
         "fuente_simulacion": "O0"},
        {"metrica": "Reducción del agua aplicada respecto de la base", "unidad": "%",
         "referencia_real": ref["saving_median"], "simulacion_base": 0.0,
         "simulacion_mejorada": sim["saving_pct"], "cambio_absoluto": sim["saving_pct"], "cambio_porcentual": np.nan,
         "fuente_referencia": f"Lieth: tensiómetro frente a productor, mediana (rango "
                              f"{ref['saving_range'][0]:.1f}–{ref['saving_range'][1]:.1f} %)",
         "fuente_simulacion": f"Media de ahorros pareados O0 frente a B0 (DE {sim['saving_pct_sd']:.1f} %)"},
        {"metrica": "Ejecuciones que cumplen las restricciones", "unidad": "%",
         "referencia_real": np.nan, "simulacion_base": b["feasible_pct"], "simulacion_mejorada": o["feasible_pct"],
         "cambio_absoluto": o["feasible_pct"] - b["feasible_pct"], "cambio_porcentual": np.nan,
         "fuente_referencia": "No reportado por la fuente",
         "fuente_simulacion": "Auditor independiente de restricciones"},
        {"metrica": "Pérdida de agua en secado sin riego", "unidad": "mL/maceta/día",
         "referencia_real": val["observed"], "simulacion_base": val["predicted"], "simulacion_mejorada": np.nan,
         "cambio_absoluto": val["predicted"] - val["observed"],
         "cambio_porcentual": 100 * (val["predicted"] - val["observed"]) / val["observed"],
         "fuente_referencia": f"Chase (2026): ventana de validación, {val['n_pots']} macetas, origen {val['origin']}",
         "fuente_simulacion": f"Modelo calibrado en la ventana de ajuste; MAE {val['mae']:.0f} mL, "
                              f"sesgo {val['bias']:+.0f} mL. La política no actúa sin riegos"},
    ]
    return pd.DataFrame(rows), {"lieth": ref, "simulation": sim, "validation": val}


def _fmt(x, digits=1):
    return "—" if pd.isna(x) else f"{x:,.{digits}f}"


def to_markdown(table: pd.DataFrame, info: dict) -> str:
    sim, val, ref = info["simulation"], info["validation"], info["lieth"]
    lines = ["**Comparación con escenarios reales (Parte 6)**", "",
             "Tabla generada por `python -m src.macetas.comparison_table`. No contiene valores ajustados a mano.", "",
             "| Métrica | Unidad | Referencia real | Simulación base | Simulación mejorada | Cambio absoluto (mejorada − base) | Cambio porcentual |",
             "| --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    for r in table.itertuples():
        lines.append(f"| {r.metrica} | {r.unidad} | {_fmt(r.referencia_real)} | {_fmt(r.simulacion_base)} | "
                     f"{_fmt(r.simulacion_mejorada)} | {_fmt(r.cambio_absoluto)} | {_fmt(r.cambio_porcentual)} |")
    lines += ["", "**Fuentes por fila**", ""]
    for i, r in enumerate(table.itertuples(), 1):
        lines.append(f"{i}. {r.metrica}. Referencia: {r.fuente_referencia}. Simulación: {r.fuente_simulacion}.")
    lines += ["", "**Correspondencia y alcance**", "",
              f"- La simulación base y la mejorada usan la calibración de origen `{sim['origin']}`; no corresponden "
              f"a las especies ni a las macetas de Lieth. La magnitud del agua aplicada no es comparable: las macetas "
              f"de Lieth aplican {ref['grower_range'][0]:.0f}–{ref['grower_range'][1]:.0f} mL/día y la simulación "
              f"{sim['B0']['water_per_day']:.1f} mL/día. La comparación pertinente es la reducción relativa.",
              f"- La reducción simulada ({sim['saving_pct']:.1f} %) queda dentro del rango que Lieth observó al "
              f"pasar de un riego del productor a uno guiado por mediciones ({ref['saving_range'][0]:.1f}–"
              f"{ref['saving_range'][1]:.1f} %, mediana {ref['saving_median']:.1f} %). Es una coincidencia de orden "
              f"de magnitud, no una validación de la mejora.",
              f"- La mejora simulada no es plenamente factible: O0 cumple las restricciones en "
              f"{sim['O0']['feasible_pct']:.1f} % de las réplicas y ambas políticas a la vez en "
              f"{sim['both_feasible_pct']:.1f} % de los pares. No se presenta como ahorro equivalente.",
              f"- La correspondencia del modelo base con mediciones reales se evaluó con Chase (2026): en secado sin "
              f"riego predice {val['predicted']:.1f} mL/maceta/día frente a {val['observed']:.1f} observados "
              f"(MAE {val['mae']:.0f} mL, sesgo {val['bias']:+.0f} mL), con mayor error donde la validación "
              f"extrapola a déficits más altos que los del ajuste.",
              "- Toda la mejora es simulada. No se implementó ni midió la política optimizada en plantas reales, "
              "por lo que no se afirma una reducción observada."]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--lieth", default="data/reference/lieth_ucdavis/agua_aplicada.csv")
    parser.add_argument("--experiments", default="results/experiments/synthetic")
    parser.add_argument("--validation", default="results/validation/public_enset")
    parser.add_argument("--out", default="results/tables")
    args = parser.parse_args(argv)
    table, info = build_table(args.lieth, args.experiments, args.validation)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    table.to_csv(out / "comparacion_real.csv", index=False, encoding="utf-8-sig")
    (out / "comparacion_real.md").write_text(to_markdown(table, info), encoding="utf-8")
    print(to_markdown(table, info))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
