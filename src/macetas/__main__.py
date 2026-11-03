"""Interfaz de línea de comandos: `python -m src.macetas <comando>` desde la raíz del repositorio.

Comandos de Nelson Escalante: validate-data, calibrate y make-synthetic. B, C y D añaden aquí los
suyos (validate-model, optimize, experiments, report-results).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd


def _validate_data(args) -> int:
    from .data_io import load_dataset

    ds = load_dataset(args.config)
    tables = Path(ds.config["_outputs"]["tables_dir"])
    tables.mkdir(parents=True, exist_ok=True)
    ds.issues.to_csv(tables / "calidad_datos.csv", index=False, encoding="utf-8-sig")
    print(f"Macetas: {len(ds.pots)} | Observaciones: {len(ds.observations)} | "
          f"Verificaciones de balanza: {len(ds.scale_checks)}")
    print(f"Lecturas utilizables: {int(ds.observations['usable'].sum())}")
    print(f"Errores: {ds.n_errors} | Advertencias: {ds.n_warnings}")
    for _, r in ds.issues.head(args.show).iterrows():
        where = f"{r['file']}:{int(r['row'])}" if pd.notna(r["row"]) else r["file"]
        print(f"  [{r['severity']}] {where} {r['check']}: {r['message']}")
    if len(ds.issues) > args.show:
        print(f"  ... ver {tables / 'calidad_datos.csv'}")
    return 1 if ds.n_errors else 0


def _calibrate(args) -> int:
    from .calibration import calibrate, model_selection_table, write_outputs

    result = calibrate(args.config, args.data_config)
    paths = write_outputs(result)
    sel = model_selection_table(result)
    print(f"Estado de la partición: {result.status}")
    print(f"Intervalos de secado (fit): {len(result.intervals)}")
    print(sel.loc[sel["scope"] == "pooled", ["model", "k", "rmse_ml", "delta_aicc", "selected"]].to_string(index=False))
    fit = result.selected["pooled"]
    if fit is not None:
        q = ", ".join(f"{b['name']}={v:.3f}" for b, v in zip(result.model_config["time_blocks"], fit.q))
        print(f"Seleccionado: {fit.model} | a={fit.a:.4f} mL/h | b={fit.b:.5f} 1/h | q: {q}")
    for name, path in paths.items():
        print(f"  {name}: {path}")
    return 0


def _make_synthetic(args) -> int:
    from .synthetic_data import generate_synthetic

    paths = generate_synthetic(args.out, seed=args.seed)
    print("Datos SINTÉTICOS generados (no son mediciones reales):")
    for name, path in paths.items():
        print(f"  {name}: {path}")
    print(f"Calibrar con: python -m src.macetas calibrate --config configs/model.json "
          f"--data-config {paths['config']}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m src.macetas")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("validate-data", help="Controles de calidad de data/raw")
    p.add_argument("--config", default="configs/data.json")
    p.add_argument("--show", type=int, default=20, help="Incidencias a mostrar en pantalla")
    p.set_defaults(func=_validate_data)

    p = sub.add_parser("calibrate", help="Ajuste de pérdidas con la fase fit")
    p.add_argument("--config", default="configs/model.json")
    p.add_argument("--data-config", default=None, help="Sustituye a data_config de model.json")
    p.set_defaults(func=_calibrate)

    p = sub.add_parser("make-synthetic", help="Genera un conjunto SINTÉTICO etiquetado")
    p.add_argument("--out", default="data/synthetic")
    p.add_argument("--seed", type=int, default=20260001)
    p.set_defaults(func=_make_synthetic)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
