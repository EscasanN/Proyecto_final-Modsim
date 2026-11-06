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


def _simulate(args) -> int:
    from .simulation_io import run_from_files

    result, paths = run_from_files(args.config, args.base, args.parameters, args.out, args.pot_id,
                                    args.allow_synthetic, args.method, args.step_h)
    print(f"Origen: {result.metrics['data_origin']} | Método: {result.metrics['method']}")
    print(f"Agua total: {result.metrics['total_irrigation_ml']:.6f} mL | "
          f"Reposición final: {result.metrics['final_refill_ml']:.6f} mL")
    print(f"Balance: {result.metrics['balance_residual_ml']:.3e} mL | "
          f"Factible: {result.metrics['feasible']}")
    for name, path in paths.items():
        print(f"  {name}: {path}")
    return 0


def _validate_model(args) -> int:
    from .verification import verify_numerics

    for name, path in verify_numerics(args.out).items():
        print(f"  {name}: {path}")
    print("Verificación analítica completada; no constituye validación con mediciones reales.")
    return 0


def _optimize(args) -> int:
    from .optimization import run_optimization

    policy, output = run_optimization(args.config, allow_synthetic=args.allow_synthetic, output_dir=args.out)
    print(f"Estado: {policy['status']} | Origen: {policy['data_origin']} | Salidas: {output}")
    print("Búsqueda de desarrollo; no constituye validación real ni evaluación final.")
    return 0 if policy["status"] == "frozen" else 2


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

    p = sub.add_parser("simulate", help="Simulación del balance con política fija")
    p.add_argument("--config", default="configs/model.json")
    p.add_argument("--base", default="configs/base.json")
    p.add_argument("--parameters", required=True)
    p.add_argument("--out", default="results/base")
    p.add_argument("--pot-id", default=None)
    p.add_argument("--allow-synthetic", action="store_true")
    p.add_argument("--method", choices=("euler", "rk4"), default=None)
    p.add_argument("--step-h", type=float, default=None)
    p.set_defaults(func=_simulate)

    p = sub.add_parser("validate-model", help="Casos analíticos y convergencia de Euler y RK4")
    p.add_argument("--out", default="results/verification")
    p.set_defaults(func=_validate_model)

    p = sub.add_parser("optimize", help="PSO y búsqueda aleatoria; congela una política de desarrollo")
    p.add_argument("--config", default="configs/pso.json")
    p.add_argument("--allow-synthetic", action="store_true")
    p.add_argument("--out", default=None)
    p.set_defaults(func=_optimize)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, OSError, KeyError, TypeError, RuntimeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
