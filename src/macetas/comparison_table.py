"""Tabla de la Parte 6: referencia real, simulación base y simulación mejorada.

Fuentes, cada una identificada en la tabla:

- Riego real del mismo sistema (opcional, `--control`): plantas control de Chase
  (2026), riego diario estimado a partir de la masa (data_origin estimated).
- Referencia real documentada: Lieth (UC Davis), ahorro al pasar del riego del
  productor a un riego por tensiómetro (data/reference/lieth_ucdavis).
- Referencia real medida: Chase (2026), pérdida de agua observada en la ventana de
  validación (results/validation/public_enset).
- Simulación: experimentos B0 (base) y O0 (política congelada) de experiments.py.

La tabla no ajusta nada: solo resume salidas ya generadas. La correspondencia entre
fuentes se discute en la nota que acompaña a la tabla.
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
    out = {"days": days, "origin": ", ".join(sorted(runs["data_origin"].unique())),
           "pot_id": manifest.get("development_config", {}).get("pot_id"), "safe_deficit_ml": sim["safe_deficit_ml"]}
    for cond in ("B0", "O0"):
        g = runs[runs["condition"] == cond]
        out[cond] = {"n": len(g), "water_per_day": float(g["total_irrigation_ml"].mean() / days),
                     "water_per_day_sd": float(g["total_irrigation_ml"].std(ddof=1) / days),
                     "max_deficit": float(g["max_deficit_ml"].mean()),
                     "feasible_pct": float(100 * g["feasible"].mean())}
    paired = pd.read_csv(root / "paired.csv")
    p0 = paired[paired["sensitivity"] == 0]
    feasible = p0[p0["both_feasible"]]
    out["saving_pct"] = float(feasible["saving_pct"].mean()) if len(feasible) else float("nan")
    out["saving_pct_sd"] = float(feasible["saving_pct"].std(ddof=1)) if len(feasible) > 1 else float("nan")
    out["saving_pct_all"] = float(p0["saving_pct"].mean())
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


def control_summary(data_config) -> dict:
    return json.loads(Path(data_config).read_text(encoding="utf-8"))["control_reference"]


def _row(metric, unit, real, base, improved, src_ref, src_sim, pct=True):
    change = improved - base if not (pd.isna(improved) or pd.isna(base)) else np.nan
    return {"metrica": metric, "unidad": unit, "referencia_real": real, "simulacion_base": base,
            "simulacion_mejorada": improved, "cambio_absoluto": change,
            "cambio_porcentual": 100 * change / base if pct and not pd.isna(change) and base else np.nan,
            "fuente_referencia": src_ref, "fuente_simulacion": src_sim}


def build_table(lieth_csv, experiment_dir, validation_dir, control_config=None) -> tuple[pd.DataFrame, dict]:
    ref, sim, val = lieth_summary(lieth_csv), simulation_summary(experiment_dir), validation_summary(validation_dir)
    ctrl = control_summary(control_config) if control_config else None
    b, o = sim["B0"], sim["O0"]
    sim_src = f"B0/O0, {b['n']} réplicas, {sim['days']:.0f} días, origen {sim['origin']}" + (
        f", maceta {sim['pot_id']}" if sim["pot_id"] else "")
    rows = []
    if ctrl:
        rows.append(_row("Agua aplicada por maceta", "mL/maceta/día", ctrl["irrigation_mean_ml_per_day"],
                         b["water_per_day"], o["water_per_day"],
                         f"Chase (2026): plantas control {ctrl['plant_ids']}, {ctrl['days'][0]} a {ctrl['days'][1]}; "
                         f"riego estimado por la masa (cota inferior), medias por planta "
                         f"{list(ctrl['irrigation_mean_by_plant_ml_per_day'].values())}", sim_src))
        rows.append(_row("Déficit máximo", "mL", ctrl["max_deficit_ml"], b["max_deficit"], o["max_deficit"],
                         "Chase (2026): plantas control, respecto de la masa al inicio del periodo; define el límite "
                         f"operacional ({sim['safe_deficit_ml']:.0f} mL)", "Media de las réplicas"))
    else:
        rows.append(_row("Agua aplicada por maceta", "mL/maceta/día", ref["grower_median"], b["water_per_day"],
                         o["water_per_day"], f"Lieth: riego del productor, mediana de {ref['n']} experimentos "
                         f"(rango {ref['grower_range'][0]:.0f}–{ref['grower_range'][1]:.0f})", sim_src))
    rows.append(_row("Reducción del agua aplicada respecto de la base", "%", ref["saving_median"], 0.0,
                     sim["saving_pct"], f"Lieth (otras especies): tensiómetro frente a productor, mediana "
                     f"(rango {ref['saving_range'][0]:.1f}–{ref['saving_range'][1]:.1f} %)",
                     f"Media de ahorros pareados O0 frente a B0 en pares factibles (DE {sim['saving_pct_sd']:.1f} %)",
                     pct=False))
    rows.append(_row("Ejecuciones que cumplen las restricciones", "%", np.nan, b["feasible_pct"], o["feasible_pct"],
                     "No reportado por las fuentes", "Auditor independiente de restricciones", pct=False))
    rows.append(_row("Pérdida de agua en secado sin riego", "mL/maceta/día", val["observed"], val["predicted"], np.nan,
                     f"Chase (2026): ventana de validación, {val['n_pots']} macetas, origen {val['origin']}",
                     f"Modelo por maceta calibrado en la ventana de ajuste; MAE {val['mae']:.0f} mL, sesgo "
                     f"{val['bias']:+.0f} mL. La política no actúa sin riegos"))
    table = pd.DataFrame(rows)
    # En la fila de validación el "cambio" es el error del modelo base frente a la referencia real.
    last = table.index[-1]
    table.loc[last, "cambio_absoluto"] = val["predicted"] - val["observed"]
    table.loc[last, "cambio_porcentual"] = 100 * (val["predicted"] - val["observed"]) / val["observed"]
    return table, {"lieth": ref, "simulation": sim, "validation": val, "control": ctrl}


def _fmt(x, digits=1):
    return "—" if pd.isna(x) else f"{x:,.{digits}f}"


def to_markdown(table: pd.DataFrame, info: dict) -> str:
    sim, val, ref, ctrl = info["simulation"], info["validation"], info["lieth"], info["control"]
    lines = ["**Comparación con escenarios reales (Parte 6)**", "",
             "Tabla generada por `python -m src.macetas.comparison_table`. No contiene valores ajustados a mano.", "",
             "| Métrica | Unidad | Referencia real | Simulación base | Simulación mejorada | Cambio absoluto (mejorada − base) | Cambio porcentual |",
             "| --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    for r in table.itertuples():
        lines.append(f"| {r.metrica} | {r.unidad} | {_fmt(r.referencia_real)} | {_fmt(r.simulacion_base)} | "
                     f"{_fmt(r.simulacion_mejorada)} | {_fmt(r.cambio_absoluto)} | {_fmt(r.cambio_porcentual)} |")
    lines += ["", "En la última fila el cambio es el error del modelo base frente a la referencia real "
              "(predicho − observado).", "", "**Fuentes por fila**", ""]
    for i, r in enumerate(table.itertuples(), 1):
        lines.append(f"{i}. {r.metrica}. Referencia: {r.fuente_referencia}. Simulación: {r.fuente_simulacion}.")
    lines += ["", "**Correspondencia y alcance**", ""]
    if ctrl:
        lines.append(f"- Las simulaciones usan la calibración `{sim['origin']}` de Chase (2026), maceta representativa "
                     f"{sim['pot_id']}, el mismo sistema que la referencia real. La base aplica "
                     f"{sim['B0']['water_per_day']:.1f} mL/maceta/día frente a {ctrl['irrigation_mean_ml_per_day']:.1f} "
                     f"estimados en las plantas control (medias por planta "
                     f"{', '.join(f'{v:.0f}' for v in ctrl['irrigation_mean_by_plant_ml_per_day'].values())}). "
                     f"El riego real es una cota inferior y corresponde a otras dos plantas, con otros genotipos.")
    else:
        lines.append(f"- Las simulaciones usan la calibración `{sim['origin']}`; no corresponden a las especies de Lieth. "
                     f"La magnitud del agua aplicada no es comparable; la comparación pertinente es la reducción relativa.")
    lines += [f"- La reducción simulada en pares factibles ({_fmt(sim['saving_pct'])} %) se contrasta con el ahorro que "
              f"Lieth documentó al pasar de un riego fijo a uno guiado por mediciones ({ref['saving_range'][0]:.1f}–"
              f"{ref['saving_range'][1]:.1f} %, mediana {ref['saving_median']:.1f} %), en otras especies. Es un "
              f"contraste de orden de magnitud, no una validación de la mejora.",
              f"- Factibilidad: O0 cumple las restricciones en {sim['O0']['feasible_pct']:.1f} % de las réplicas y ambas "
              f"políticas a la vez en {sim['both_feasible_pct']:.1f} % de los pares; el ahorro solo se reporta en pares "
              f"factibles (con todos los pares sería {sim['saving_pct_all']:.1f} %).",
              f"- Correspondencia del modelo base con mediciones reales (Chase, 2026): en secado sin riego predice "
              f"{val['predicted']:.1f} mL/maceta/día frente a {val['observed']:.1f} observados (MAE {val['mae']:.0f} mL, "
              f"sesgo {val['bias']:+.0f} mL), con mayor error donde la validación extrapola a déficits mayores que los "
              f"del ajuste.",
              "- Toda la mejora es simulada. No se implementó ni midió la política optimizada en plantas reales, "
              "por lo que no se afirma una reducción observada."]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--lieth", default="data/reference/lieth_ucdavis/agua_aplicada.csv")
    parser.add_argument("--experiments", default="results/experiments/public_enset")
    parser.add_argument("--validation", default="results/validation/public_enset")
    parser.add_argument("--control", default="data/reference/chase2026_enset/converted/data_config.json",
                        help="data_config.json con control_reference (Chase 2026); '' para omitirlo")
    parser.add_argument("--out", default="results/tables")
    parser.add_argument("--name", default="comparacion_real_enset")
    args = parser.parse_args(argv)
    table, info = build_table(args.lieth, args.experiments, args.validation, args.control or None)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    table.to_csv(out / f"{args.name}.csv", index=False, encoding="utf-8-sig")
    (out / f"{args.name}.md").write_text(to_markdown(table, info), encoding="utf-8")
    print(to_markdown(table, info))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
