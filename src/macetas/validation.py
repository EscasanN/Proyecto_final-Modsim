"""Validación temporal de dinámica con riegos registrados, sin recalibración."""
import argparse
from hashlib import sha256
from pathlib import Path

import pandas as pd

from .data_io import load_dataset
from .experiments import read_json, write_json
from .metrics import validation_errors
from .model import load_calibrated_model
from .simulator import IrrigationEvent, SimulationConfig, simulate


def run_validation(data_config, parameters_path, output_dir, *, allow_synthetic=False,
                   method="rk4", step_h=0.25):
    ds = load_dataset(data_config)
    if ds.n_errors or not ds.config["split"]["frozen"]:
        raise ValueError("Se requieren datos sin errores y partición temporal congelada.")
    fits = [end for phase, _, end in ds.windows if phase == "fit"]
    windows = [(start, end) for phase, start, end in ds.windows if phase == "validation"]
    if not fits or not windows or any(start < max(fits) for start, _ in windows):
        raise ValueError("La validación debe ser posterior a todas las ventanas de ajuste.")
    payload = read_json(parameters_path)
    calibration_manifest = Path(parameters_path).parent / "calibracion_manifest.json"
    calibration = read_json(calibration_manifest)
    if calibration["data_config"]["split"] != ds.config["split"]:
        raise ValueError("La partición no coincide con la usada por la calibración de A.")
    for name, filename in ds.config["files"].items():
        digest = sha256((Path(ds.config["_data_dir"]) / filename).read_bytes()).hexdigest()
        if digest != calibration["input_sha256"][name]:
            raise ValueError("Los datos cambiaron desde la calibración; revisar procedencia antes de validar.")
    origins = set(ds.observations.data_origin.dropna())
    if origins != set(payload["data_origin"]):
        raise ValueError("Los parámetros y observaciones deben tener el mismo origen.")
    if payload["water_density_g_per_ml"] != ds.config["water_density_g_per_ml"]:
        raise ValueError("Densidad de agua incompatible con calibración.")
    rows, traces, event_rows = [], [], []
    for pot_id, all_obs in ds.observations.groupby("pot_id"):
        model = load_calibrated_model(parameters_path, pot_id, allow_synthetic)
        reference = float(ds.pots.set_index("pot_id").loc[pot_id, "reference_mass_g"])
        if abs(payload["reference_mass_g"][pot_id] - reference) > 1e-9:
            raise ValueError("No cambiar la referencia de masa después de calibrar.")
        for window_id, (left, right) in enumerate(windows):
            raw = all_obs[all_obs.timestamp.ge(left) & all_obs.timestamp.lt(right)].sort_values("timestamp")
            obs = raw[raw.usable & raw.reading_stage.ne("drainage_check")]
            if len(obs) < 2:
                raise ValueError(f"{pot_id}: faltan observaciones reservadas para validar.")
            initial = obs.iloc[0]
            start, end = initial.timestamp, obs.timestamp.iloc[-1]
            if initial.deficit_ml < 0:
                raise ValueError("El déficit inicial negativo no es representable por el simulador.")
            # No se interpretan cantidades ausentes como riegos nulos.
            posts = raw[raw.reading_stage.eq("post_drainage")]
            if posts[["irrigation_ml", "irrigation_timestamp"]].isna().any().any():
                raise ValueError("Hay riegos registrados incompletos.")
            events = []
            for event in posts.itertuples():
                time = event.irrigation_timestamp
                if start < time < end or (time == start and initial.reading_stage == "pre_irrigation"):
                    events.append(IrrigationEvent(time, event.irrigation_ml, event.event_id))
            pre_ids = set(raw.loc[raw.reading_stage.eq("pre_irrigation") & raw.timestamp.gt(start)
                                  & raw.timestamp.lt(end), "event_id"].dropna())
            if not pre_ids <= set(posts.event_id.dropna()):
                raise ValueError("Un riego dentro de la ventana carece de registro posterior.")
            config = SimulationConfig(str(start), str(end), float(initial.deficit_ml), method=method,
                                      step_h=step_h, close_balance=False)
            result = simulate(model, config, irrigation_events=events, observation_times=list(obs.timestamp))
            for reading in obs.iloc[1:].itertuples():
                matches = result.trajectory[result.trajectory.timestamp.eq(reading.timestamp)]
                # La trayectoria registra la llegada antes del salto; post_drainage usa el estado posterior.
                predicted = float(matches.deficit_ml.iloc[0 if reading.reading_stage == "pre_irrigation" else -1])
                rows.append({"pot_id": pot_id, "window_id": window_id, "row": reading.row,
                             "timestamp": reading.timestamp, "observed_deficit_ml": reading.deficit_ml,
                             "predicted_deficit_ml": predicted, "error_ml": predicted - reading.deficit_ml,
                             "data_origin": model.data_origin})
            traces.append(result.trajectory.assign(pot_id=pot_id, window_id=window_id))
            event_rows.append(result.events.assign(pot_id=pot_id, window_id=window_id))
    if not rows:
        raise ValueError("No hay observaciones reservadas utilizables.")
    comparisons = pd.DataFrame(rows)
    errors = [{"pot_id": pot_id, **validation_errors(g.observed_deficit_ml, g.predicted_deficit_ml)}
              for pot_id, g in comparisons.groupby("pot_id")]
    errors.append({"pot_id": "ALL", **validation_errors(comparisons.observed_deficit_ml,
                                                        comparisons.predicted_deficit_ml)})
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    for name, frame in {"comparisons": comparisons, "errors": pd.DataFrame(errors),
                        "trajectory": pd.concat(traces), "events": pd.concat(event_rows)}.items():
        frame.to_csv(output / f"{name}.csv", index=False)
    inputs = {"parameters": Path(parameters_path), "data_config": Path(data_config),
              "calibration_manifest": calibration_manifest}
    inputs.update({k: Path(ds.config["_data_dir"]) / v for k, v in ds.config["files"].items()})
    write_json(output / "validation_manifest.json", {
        "data_origin": sorted(origins), "real_validation": origins == {"observed"},
        "method": method, "step_h": step_h, "split": ds.config["split"],
        "initialization": "Primera lectura utilizable por maceta y ventana; excluida de los errores.",
        "limitations": "Drenaje instantáneo del modelo B; no se reinicia con observaciones posteriores.",
        "input_sha256": {k: sha256(p.read_bytes()).hexdigest() for k, p in inputs.items()},
        "source_sha256": {p.name: sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob("*.py")}})
    return comparisons, pd.DataFrame(errors)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-config", default="configs/data.json")
    parser.add_argument("--parameters", default="results/tables/parametros_modelo.json")
    parser.add_argument("--out", default="results/validation/observed")
    parser.add_argument("--allow-synthetic", action="store_true")
    parser.add_argument("--method", choices=("euler", "rk4"), default="rk4")
    parser.add_argument("--step-h", type=float, default=0.25)
    args = parser.parse_args()
    _, errors = run_validation(args.data_config, args.parameters, args.out,
                              allow_synthetic=args.allow_synthetic, method=args.method, step_h=args.step_h)
    print(errors.to_string(index=False))


if __name__ == "__main__":
    main()
