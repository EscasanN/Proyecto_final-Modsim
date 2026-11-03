"""Estimación de la pérdida de agua E(t, D) a partir de intervalos de secado.

Módulo de Nelson Escalante. Usa exclusivamente lecturas de la fase de ajuste (`fit`);
los datos de validación nunca entran aquí (ver `_assert_fit_only`).

Modelo de pérdida (docs/calibration.md):

    dD/dt = q(t) * max(0, a + b*D)

con `a` en mL/h, `b` en 1/h y `q` adimensional por bloque horario, normalizado a 1
en el primer bloque. Entre dos lecturas sin riego la ecuación tiene solución exacta
por tramos, que se usa como operador de observación del ajuste: así un intervalo
que cruza del día a la noche se trata sin aproximar.

Candidatos: `constant` (solo a), `blocks` (a y q) y `blocks_linear` (a, b y q).
Se elige el más simple cuyo AICc quede a menos de `tolerance` del mínimo.
"""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import least_squares

from .data_io import Dataset, DataQualityError, drying_pairs, format_timestamps, load_data_config, load_dataset
from .time_blocks import segment_matrix, validate_blocks

# Con BOM para que Excel muestre bien los acentos; data_io lee ambos formatos.
CSV_ENCODING = "utf-8-sig"

# modelo -> (ajusta b, ajusta q)
MODELS = {"constant": (False, False), "blocks": (False, True), "blocks_linear": (True, True)}


# ---------------------------------------------------------------------------
# Solución exacta entre riegos
# ---------------------------------------------------------------------------

def predict_deficit(d0, hours, block_idx, a: float, b: float, q) -> np.ndarray:
    """Déficit al final de cada intervalo partiendo de `d0` (mL).

    `hours` y `block_idx` son matrices (n, S) de tramos (ver segment_matrix). En
    cada tramo con factor q se aplica la solución de dD/dt = q(a + bD):

        D1 = D0 + (a + b*D0) * expm1(b*q*h) / b      (b != 0)
        D1 = D0 + (a + b*D0) * q*h                   (b == 0)

    Si a + b*D <= 0 la pérdida está recortada a 0 y el déficit no cambia.
    """
    d = np.array(d0, dtype=float, copy=True)
    q = np.asarray(q, dtype=float)
    for s in range(hours.shape[1]):
        tau = hours[:, s] * q[block_idx[:, s]]
        rate = a + b * d
        growth = tau if abs(b) < 1e-12 else np.expm1(b * tau) / b
        d = np.where(rate > 0, d + rate * growth, d)
    return d


# ---------------------------------------------------------------------------
# Intervalos de secado
# ---------------------------------------------------------------------------

@dataclass
class IntervalSet:
    """Intervalos sin riego, con sus tramos horarios precalculados."""

    frame: pd.DataFrame
    hours: np.ndarray
    block_idx: np.ndarray

    def __len__(self) -> int:
        return len(self.frame)

    @property
    def d0(self) -> np.ndarray:
        return self.frame["deficit_start_ml"].to_numpy(float)

    @property
    def d1(self) -> np.ndarray:
        return self.frame["deficit_end_ml"].to_numpy(float)

    def subset(self, rows) -> "IntervalSet":
        rows = np.asarray(rows)
        if rows.dtype == bool:
            rows = np.flatnonzero(rows)
        return IntervalSet(self.frame.iloc[rows].reset_index(drop=True), self.hours[rows], self.block_idx[rows])


def drying_intervals(dataset: Dataset, blocks: list[dict], phase: str = "fit",
                     min_h: float = 0.0, max_h: float = np.inf) -> IntervalSet:
    """Intervalos de secado cuyos dos extremos pertenecen a la ventana `phase`."""
    obs = dataset.observations
    records = []
    for _, p in drying_pairs(obs, obs["usable"]).iterrows():
        r0, r1 = obs.loc[p["i0"]], obs.loc[p["i1"]]
        if r0["split"] != phase or r1["split"] != phase:
            continue
        h = (r1["timestamp"] - r0["timestamp"]).total_seconds() / 3600
        if not (min_h <= h <= max_h):
            continue
        records.append({
            "pot_id": p["pot_id"], "split": phase,
            "t_start": r0["timestamp"], "t_end": r1["timestamp"], "hours": h,
            "row_start": r0["row"], "row_end": r1["row"],
            "deficit_start_ml": r0["deficit_ml"], "deficit_end_ml": r1["deficit_ml"],
            "loss_ml": r1["deficit_ml"] - r0["deficit_ml"],
            "mean_rate_ml_per_h": (r1["deficit_ml"] - r0["deficit_ml"]) / h,
            "day": r0["timestamp"].strftime("%Y-%m-%d"),
            "ambient_temperature_c": np.nanmean([r0["ambient_temperature_c"], r1["ambient_temperature_c"]])
            if pd.notna(r0["ambient_temperature_c"]) or pd.notna(r1["ambient_temperature_c"]) else np.nan,
        })
    frame = pd.DataFrame(records, columns=[
        "pot_id", "split", "t_start", "t_end", "hours", "row_start", "row_end",
        "deficit_start_ml", "deficit_end_ml", "loss_ml", "mean_rate_ml_per_h", "day",
        "ambient_temperature_c"])
    hours, idx = segment_matrix(frame["t_start"], frame["t_end"], blocks)
    for k, b in enumerate(blocks):
        frame[f"hours_{b['name']}"] = (hours * (idx == k)).sum(axis=1)
    return IntervalSet(frame, hours, idx)


def _assert_fit_only(intervals: IntervalSet) -> None:
    if len(intervals) and (intervals.frame["split"] != "fit").any():
        raise ValueError("Fuga de información: el ajuste recibió intervalos fuera de la fase 'fit'.")


# ---------------------------------------------------------------------------
# Ajuste y selección
# ---------------------------------------------------------------------------

@dataclass
class FitResult:
    scope: str
    model: str
    names: list[str]
    theta: np.ndarray
    a: float
    b: float
    q: np.ndarray
    n: int
    rss: float
    rmse: float
    aicc: float
    se: np.ndarray
    success: bool
    message: str
    residuals: np.ndarray = field(repr=False)

    @property
    def k(self) -> int:
        return len(self.names)


def _layout(model: str, block_names: list[str]) -> tuple[bool, bool, list[str]]:
    fit_b, fit_q = MODELS[model]
    fit_q = fit_q and len(block_names) > 1
    names = ["a_ml_per_h"] + (["b_per_h"] if fit_b else []) + ([f"q_{n}" for n in block_names[1:]] if fit_q else [])
    return fit_b, fit_q, names


def _unpack(theta, fit_b, fit_q, n_blocks):
    a = theta[0]
    b = theta[1] if fit_b else 0.0
    q = np.ones(n_blocks)
    if fit_q:
        q[1:] = theta[1 + fit_b:]
    return a, b, q


def fit_model(intervals: IntervalSet, model: str, block_names: list[str], bounds: dict,
              scope: str = "pooled", x0=None) -> FitResult:
    """Ajuste por mínimos cuadrados del déficit final de cada intervalo."""
    _assert_fit_only(intervals)
    fit_b, fit_q, names = _layout(model, block_names)
    n, k = len(intervals), len(names)
    lo = np.array([bounds["a_ml_per_h"][0]] + ([bounds["b_per_h"][0]] if fit_b else [])
                  + [bounds["q"][0]] * (k - 1 - fit_b), dtype=float)
    hi = np.array([bounds["a_ml_per_h"][1]] + ([bounds["b_per_h"][1]] if fit_b else [])
                  + [bounds["q"][1]] * (k - 1 - fit_b), dtype=float)
    if n <= k:
        nan = np.full(k, np.nan)
        return FitResult(scope, model, names, nan, np.nan, np.nan, np.full(len(block_names), np.nan),
                         n, np.nan, np.nan, np.inf, nan, False, f"Insuficientes intervalos ({n}) para {k} parámetros.",
                         np.array([]))
    if x0 is None:
        rates = intervals.frame["mean_rate_ml_per_h"].to_numpy(float)
        a0 = float(np.median(rates[rates > 0])) if (rates > 0).any() else 1.0
        x0 = np.array([a0] + ([-1e-3] if fit_b else []) + [1.0] * (k - 1 - fit_b))
    margin = 1e-6 * (hi - lo)
    x0 = np.clip(np.asarray(x0, float), lo + margin, hi - margin)
    d0, d1 = intervals.d0, intervals.d1

    def residuals(theta):
        a, b, q = _unpack(theta, fit_b, fit_q, len(block_names))
        return predict_deficit(d0, intervals.hours, intervals.block_idx, a, b, q) - d1

    sol = least_squares(residuals, x0, bounds=(lo, hi), method="trf")
    a, b, q = _unpack(sol.x, fit_b, fit_q, len(block_names))
    rss = float(np.sum(sol.fun ** 2))
    s2 = rss / (n - k)
    jtj = sol.jac.T @ sol.jac
    se = np.sqrt(np.clip(np.diag(np.linalg.pinv(jtj)) * s2, 0, None))
    aicc = (n * np.log(max(rss, 1e-12) / n) + 2 * k + 2 * k * (k + 1) / (n - k - 1)) if n > k + 1 else np.inf
    return FitResult(scope, model, names, sol.x, a, b, q, n, rss, float(np.sqrt(rss / n)), float(aicc),
                     se, bool(sol.success), sol.message, sol.fun)


def select_model(fits: list[FitResult], tolerance: float) -> FitResult | None:
    """El modelo con menos parámetros entre los que quedan a `tolerance` del menor AICc."""
    ok = [f for f in fits if f.success and np.isfinite(f.aicc)]
    if not ok:
        return None
    best = min(f.aicc for f in ok)
    eligible = [f for f in ok if f.aicc <= best + tolerance]
    return min(eligible, key=lambda f: (f.k, f.aicc))


def bootstrap(intervals: IntervalSet, fit: FitResult, block_names, bounds, n_boot: int, seed: int) -> np.ndarray:
    """Remuestreo por días completos (los intervalos de un mismo día no son independientes).

    Devuelve una matriz (réplicas, parámetros); vacía si hay menos de 3 días.
    """
    days = intervals.frame["day"].to_numpy()
    unique_days = np.unique(days)
    if len(unique_days) < 3 or n_boot <= 0:
        return np.empty((0, fit.k))
    rng = np.random.default_rng(seed)
    rows_by_day = {d: np.flatnonzero(days == d) for d in unique_days}
    samples = []
    for _ in range(n_boot):
        chosen = rng.choice(unique_days, size=len(unique_days), replace=True)
        rows = np.concatenate([rows_by_day[d] for d in chosen])
        res = fit_model(intervals.subset(rows), fit.model, block_names, bounds, fit.scope, x0=fit.theta)
        if res.success:
            samples.append(res.theta)
    return np.array(samples).reshape(-1, fit.k)


# ---------------------------------------------------------------------------
# Diagnósticos de eventos de riego
# ---------------------------------------------------------------------------

def irrigation_events(dataset: Dataset, blocks, fit: FitResult | None = None,
                      phases=("pilot", "fit")) -> pd.DataFrame:
    """Contrasta cada riego con la regla ideal Q = max(0, I - D-), D+ = max(0, D- - I).

    Solo usa piloto y ajuste: los eventos de validación son de D. `apparent_loss_ml`
    = (D+ - D-) - (Q - I) es el agua que el balance atribuye a pérdidas durante el
    evento; `expected_loss_ml` es la que predice el ajuste en el mismo lapso.
    """
    obs = dataset.observations
    ev = obs[obs["event_id"].notna() & obs["split"].isin(phases) & obs["usable"]]
    pre = ev[ev["reading_stage"] == "pre_irrigation"].drop_duplicates("event_id", keep=False).set_index("event_id")
    post = ev[ev["reading_stage"] == "post_drainage"].drop_duplicates("event_id", keep=False).set_index("event_id")
    ids = pre.index.intersection(post.index)
    out = pd.DataFrame({
        "event_id": ids,
        "pot_id": post.loc[ids, "pot_id"].to_numpy(),
        "split": post.loc[ids, "split"].to_numpy(),
        "t_pre": pre.loc[ids, "timestamp"].to_numpy(),
        "t_irrigation": post.loc[ids, "irrigation_timestamp"].to_numpy(),
        "t_post": post.loc[ids, "timestamp"].to_numpy(),
        "deficit_pre_ml": pre.loc[ids, "deficit_ml"].to_numpy(float),
        "irrigation_ml": post.loc[ids, "irrigation_ml"].to_numpy(float),
        "drainage_obs_ml": post.loc[ids, "drainage_ml"].to_numpy(float),
        "deficit_post_obs_ml": post.loc[ids, "deficit_ml"].to_numpy(float),
    })
    out["drain_minutes"] = (out["t_post"] - out["t_irrigation"]).dt.total_seconds() / 60
    if fit is not None and len(out):
        hours, idx = segment_matrix(out["t_pre"], out["t_post"], blocks)
        d_pre = out["deficit_pre_ml"].to_numpy()
        out["expected_loss_ml"] = predict_deficit(d_pre, hours, idx, fit.a, fit.b, fit.q) - d_pre
    else:
        out["expected_loss_ml"] = 0.0
    d_pre, irr = out["deficit_pre_ml"], out["irrigation_ml"]
    out["drainage_ideal_ml"] = np.maximum(0.0, irr - d_pre)
    out["deficit_post_ideal_ml"] = np.maximum(0.0, d_pre - irr) + out["expected_loss_ml"]
    out["drainage_residual_ml"] = out["drainage_obs_ml"] - out["drainage_ideal_ml"]
    out["deficit_post_residual_ml"] = out["deficit_post_obs_ml"] - out["deficit_post_ideal_ml"]
    out["apparent_loss_ml"] = (out["deficit_post_obs_ml"] - d_pre) - (out["drainage_obs_ml"] - irr)
    return out.sort_values("t_pre").reset_index(drop=True)


def drainage_time_estimates(dataset: Dataset, threshold_g: float) -> pd.DataFrame:
    """Minutos tras el riego a partir de los cuales la masa deja de cambiar más que `threshold_g`.

    Usa los eventos con lecturas `drainage_check` (piloto). NaN si no se estabilizó.
    Sin umbral finito (no hay verificación de balanza) devuelve una tabla vacía.
    """
    columns = ["event_id", "pot_id", "n_readings", "last_minute", "stable_after_minutes", "threshold_g"]
    if not np.isfinite(threshold_g):
        return pd.DataFrame(columns=columns)
    obs = dataset.observations
    irr_time = obs.loc[obs["reading_stage"] == "post_drainage"].set_index("event_id")["irrigation_timestamp"]
    rows = obs[obs["usable"] & obs["reading_stage"].isin(["drainage_check", "post_drainage"])
               & obs["event_id"].isin(irr_time.dropna().index)]
    records = []
    for event_id, g in rows.groupby("event_id"):
        if (g["reading_stage"] == "drainage_check").sum() < 2:
            continue
        g = g.sort_values("timestamp")
        minutes = ((g["timestamp"] - irr_time[event_id]).dt.total_seconds() / 60).to_numpy()
        steps = np.abs(np.diff(g["mass_g"].to_numpy()))
        big = np.flatnonzero(steps > threshold_g)
        stable = np.nan if len(big) and big[-1] == len(steps) - 1 else minutes[big[-1] + 1 if len(big) else 0]
        records.append({"event_id": event_id, "pot_id": g["pot_id"].iloc[0], "n_readings": len(g),
                        "last_minute": minutes[-1], "stable_after_minutes": stable, "threshold_g": threshold_g})
    return pd.DataFrame(records, columns=columns)


# ---------------------------------------------------------------------------
# Orquestación
# ---------------------------------------------------------------------------

@dataclass
class CalibrationResult:
    dataset: Dataset
    model_config: dict
    intervals: IntervalSet
    fits: dict[str, list[FitResult]]
    selected: dict[str, FitResult | None]
    boot: dict[str, np.ndarray]
    events: pd.DataFrame
    drainage: pd.DataFrame
    status: str


def load_model_config(path) -> dict:
    path = Path(path).resolve()
    cfg = json.loads(path.read_text(encoding="utf-8"))
    cfg["_path"] = str(path)
    cfg["_data_config"] = str((path.parent / cfg["data_config"]).resolve())
    return cfg


def calibrate(model_config_path, data_config_path=None) -> CalibrationResult:
    """Ajusta la pérdida de agua con los datos de la fase `fit`.

    Lanza DataQualityError si los datos tienen errores y ValueError si la partición
    no define la ventana de ajuste.
    """
    mcfg = load_model_config(model_config_path)
    dcfg = load_data_config(data_config_path or mcfg["_data_config"])
    dataset = load_dataset(dcfg)
    if dataset.n_errors:
        raise DataQualityError(f"{dataset.n_errors} errores de calidad; ejecute validate-data y corríjalos.")
    if not any(phase == "fit" for phase, _, _ in dataset.windows):
        raise ValueError("Defina la ventana 'fit' en split.windows antes de calibrar.")

    blocks = mcfg["time_blocks"]
    validate_blocks(blocks)
    block_names = [b["name"] for b in blocks]
    cal = mcfg["calibration"]
    intervals = drying_intervals(dataset, blocks, "fit", cal["min_interval_h"], cal["max_interval_h"])
    if len(intervals) == 0:
        raise ValueError("No hay intervalos de secado en la fase 'fit'.")

    scopes = ["pooled"] + sorted(intervals.frame["pot_id"].unique())
    fits, selected, boot = {}, {}, {}
    for i, scope in enumerate(scopes):
        subset = intervals if scope == "pooled" else intervals.subset(intervals.frame["pot_id"] == scope)
        fits[scope] = [fit_model(subset, m, block_names, cal["bounds"], scope) for m in cal["candidate_models"]]
        selected[scope] = select_model(fits[scope], cal["selection"]["tolerance"])
        boot[scope] = (bootstrap(subset, selected[scope], block_names, cal["bounds"],
                                 cal["bootstrap"]["n"], cal["bootstrap"]["seed"] + i)
                       if selected[scope] is not None else np.empty((0, 0)))

    events = irrigation_events(dataset, blocks, selected["pooled"])
    drainage = drainage_time_estimates(dataset, dataset.tolerances["mass_tolerance_g"])
    status = "frozen" if dcfg["split"].get("frozen") else "preliminary"
    return CalibrationResult(dataset, mcfg, intervals, fits, selected, boot, events, drainage, status)


# ---------------------------------------------------------------------------
# Tablas y archivos de salida
# ---------------------------------------------------------------------------

_UNITS = {"a_ml_per_h": "mL/h", "b_per_h": "1/h"}


def _origins(result: CalibrationResult) -> str:
    return ",".join(sorted(result.dataset.observations["data_origin"].dropna().unique()))


def model_selection_table(result: CalibrationResult) -> pd.DataFrame:
    rows = []
    for scope, fits in result.fits.items():
        best = min((f.aicc for f in fits if np.isfinite(f.aicc)), default=np.nan)
        for f in fits:
            rows.append({"scope": scope, "model": f.model, "k": f.k, "n_intervals": f.n, "rss_ml2": f.rss,
                         "rmse_ml": f.rmse, "aicc": f.aicc, "delta_aicc": f.aicc - best,
                         "selected": f is result.selected[scope], "success": f.success, "message": f.message})
    return pd.DataFrame(rows)


def parameter_table(result: CalibrationResult) -> pd.DataFrame:
    """Tabla de parámetros con unidad, tipo, procedimiento, incertidumbre y origen."""
    blocks = result.model_config["time_blocks"]
    origin = _origins(result)
    method = "Mínimos cuadrados (scipy least_squares, trf) sobre el déficit final; solución exacta por tramos"
    source = "Intervalos de secado de la fase fit (data/processed/intervalos_secado_fit.csv)"
    rows = []
    for scope, fit in result.selected.items():
        if fit is None:
            continue
        sub = result.intervals.frame if scope == "pooled" else result.intervals.frame.query("pot_id == @scope")
        boot = result.boot[scope]
        lo, hi = (np.percentile(boot, [2.5, 97.5], axis=0) if len(boot) >= 20 else (np.full(fit.k, np.nan),) * 2)
        values = {"a_ml_per_h": fit.a, "b_per_h": fit.b, **{f"q_{b['name']}": fit.q[i] for i, b in enumerate(blocks)}}
        for name, value in values.items():
            free = name in fit.names
            j = fit.names.index(name) if free else None
            note = ("" if free else "Normalizado a 1 (referencia de q)" if name == f"q_{blocks[0]['name']}"
                    else f"Fijado por el modelo '{fit.model}'")
            rows.append({"scope": scope, "parameter": name, "value": value, "unit": _UNITS.get(name, "adimensional"),
                         "kind": "fitted" if free else "fixed", "model": fit.model,
                         "se": fit.se[j] if free else np.nan,
                         "ci95_low": lo[j] if free else np.nan, "ci95_high": hi[j] if free else np.nan,
                         "n_intervals": fit.n, "n_days": sub["day"].nunique(), "n_bootstrap": len(boot),
                         "method": method if free else "", "source": source, "data_origin": origin, "notes": note})

    def add(parameter, value, unit, kind, method_, source_, notes=""):
        rows.append({"scope": "global", "parameter": parameter, "value": value, "unit": unit, "kind": kind,
                     "method": method_, "source": source_, "data_origin": origin, "notes": notes})

    ds = result.dataset
    st = ds.scale_stats
    rho = ds.config["water_density_g_per_ml"]
    scale_src = "data/raw/balanza.csv"
    add("water_density", rho, "g/mL", "assumed", "Supuesto de trabajo", "Plan, sección 5.2",
        "Simplificación: 1 g de pérdida de masa = 1 mL de agua")
    add("scale_resolution", st["resolution_g"], "g", "measured", "Máxima resolución declarada", scale_src)
    add("scale_repeatability_sd", st["repeatability_sd_g"], "g", "measured",
        "Desviación estándar agrupada de pesajes repetidos", scale_src)
    add("scale_max_abs_bias", st["max_abs_bias_g"], "g", "measured", "|media - masa conocida|", scale_src)
    add("sigma_reading", st["sigma_reading_g"], "g", "measured", "sqrt(sd^2 + res^2/12)", scale_src,
        "Error de una lectura; usar como error de medición de D_hat")
    add("sigma_deficit", st["sigma_reading_g"] / rho, "mL", "derived", "sigma_reading / rho_w", scale_src)
    add("mass_tolerance", ds.tolerances["mass_tolerance_g"], "g", "derived",
        "tolerance_sigmas * sqrt(2) * sigma_reading", ds.tolerances["mass_tolerance_source"])
    f = result.intervals.frame
    for col, unit, label in (("deficit_start_ml", "mL", "deficit"), ("mean_rate_ml_per_h", "mL/h", "loss_rate"),
                             ("ambient_temperature_c", "°C", "ambient_temperature")):
        values = pd.concat([f[col], f["deficit_end_ml"]]) if col == "deficit_start_ml" else f[col]
        if values.notna().any():
            add(f"{label}_min_fit", values.min(), unit, "observed_range", "Mínimo en intervalos de ajuste", source,
                "No extrapolar fuera del rango observado")
            add(f"{label}_max_fit", values.max(), unit, "observed_range", "Máximo en intervalos de ajuste", source,
                "No extrapolar fuera del rango observado")
    if len(result.drainage) and result.drainage["stable_after_minutes"].notna().any():
        add("drainage_stable_minutes_median", result.drainage["stable_after_minutes"].median(), "min",
            "measured", "Mediana del tiempo de estabilización en eventos con drainage_check",
            "results/tables/tiempo_drenaje.csv")
    for _, p in ds.pots.iterrows():
        rows.append({"scope": p["pot_id"], "parameter": "reference_mass", "value": p["reference_mass_g"],
                     "unit": "g", "kind": "measured", "method": "Masa drenada de referencia (protocolo 5.1)",
                     "source": "data/raw/macetas.csv", "data_origin": p["data_origin"], "notes": ""})
    table = pd.DataFrame(rows)
    for col in ("n_intervals", "n_days", "n_bootstrap"):
        table[col] = table[col].astype("Int64")
    return table


def _jsonable(x):
    if isinstance(x, dict):
        return {k: _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple, np.ndarray)):
        return [_jsonable(v) for v in x]
    if isinstance(x, (np.floating, float)):
        return None if not np.isfinite(x) else float(x)
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, np.bool_):
        return bool(x)
    return x


def parameters_for_model(result: CalibrationResult) -> dict:
    """Parámetros en formato para el simulador de B (results/tables/parametros_modelo.json)."""
    blocks = result.model_config["time_blocks"]
    table = parameter_table(result)

    def describe(fit, scope):
        if fit is None:
            return None
        sub = table[table["scope"] == scope].set_index("parameter")
        return {"model": fit.model, "a_ml_per_h": fit.a, "b_per_h": fit.b,
                "q": {b["name"]: fit.q[i] for i, b in enumerate(blocks)},
                "ci95": {n: [sub.loc[n, "ci95_low"], sub.loc[n, "ci95_high"]] for n in fit.names},
                "rmse_ml": fit.rmse, "n_intervals": fit.n}

    glob = table[table["scope"] == "global"].set_index("parameter")["value"]
    ds = result.dataset
    return _jsonable({
        "status": result.status,
        "data_origin": _origins(result).split(","),
        "loss_model": "dD/dt = q(t) * max(0, a + b*D); D en mL, t en h",
        "time_blocks": blocks,
        "timezone": ds.config["timezone"],
        "selected_scope": result.model_config["calibration"]["scope"],
        "pooled": describe(result.selected["pooled"], "pooled"),
        "per_pot": {s: describe(f, s) for s, f in result.selected.items() if s != "pooled"},
        "reference_mass_g": dict(zip(ds.pots["pot_id"], ds.pots["reference_mass_g"])),
        "water_density_g_per_ml": ds.config["water_density_g_per_ml"],
        "measurement": {"sigma_reading_g": glob.get("sigma_reading"), "sigma_deficit_ml": glob.get("sigma_deficit")},
        "observed_range_fit": {"deficit_ml": [glob.get("deficit_min_fit"), glob.get("deficit_max_fit")],
                               "loss_rate_ml_per_h": [glob.get("loss_rate_min_fit"), glob.get("loss_rate_max_fit")]},
        "drainage_stable_minutes_median": glob.get("drainage_stable_minutes_median"),
        "irrigation_event_check": {
            "n_events": len(result.events),
            "drainage_residual_mean_ml": result.events["drainage_residual_ml"].mean() if len(result.events) else None,
            "drainage_residual_sd_ml": result.events["drainage_residual_ml"].std() if len(result.events) > 1 else None,
            "deficit_post_residual_mean_ml": result.events["deficit_post_residual_ml"].mean() if len(result.events) else None,
        },
    })


def _sha256(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def _git_commit() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def manifest(result: CalibrationResult) -> dict:
    ds = result.dataset
    data_dir = Path(ds.config["_data_dir"])
    public = lambda cfg: {k: v for k, v in cfg.items() if not k.startswith("_")}
    return _jsonable({
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": result.status,
        "git_commit": _git_commit(),
        "python": platform.python_version(),
        "packages": {"numpy": np.__version__, "pandas": pd.__version__,
                     "scipy": __import__("scipy").__version__},
        "input_sha256": {name: _sha256(data_dir / fname) for name, fname in ds.config["files"].items()},
        "data_config": public(ds.config),
        "model_config": public(result.model_config),
        "bootstrap_seeds": {s: result.model_config["calibration"]["bootstrap"]["seed"] + i
                            for i, s in enumerate(result.fits)},
        "n_observations": len(ds.observations),
        "n_fit_intervals": len(result.intervals),
        "issues": {"errors": ds.n_errors, "warnings": ds.n_warnings},
    })


def write_outputs(result: CalibrationResult) -> dict[str, Path]:
    """Escribe datos procesados y tablas. Devuelve las rutas escritas."""
    out = result.dataset.config["_outputs"]
    processed, tables = Path(out["processed_dir"]), Path(out["tables_dir"])
    processed.mkdir(parents=True, exist_ok=True)
    tables.mkdir(parents=True, exist_ok=True)
    paths = {
        "observaciones": processed / "observaciones_procesadas.csv",
        "intervalos": processed / "intervalos_secado_fit.csv",
        "calidad": tables / "calidad_datos.csv",
        "seleccion": tables / "seleccion_modelos.csv",
        "parametros": tables / "parametros.csv",
        "eventos": tables / "eventos_riego.csv",
        "drenaje": tables / "tiempo_drenaje.csv",
        "parametros_modelo": tables / "parametros_modelo.json",
        "manifest": tables / "calibracion_manifest.json",
    }
    format_timestamps(result.dataset.observations).to_csv(paths["observaciones"], index=False, encoding=CSV_ENCODING)
    format_timestamps(result.intervals.frame).to_csv(paths["intervalos"], index=False, encoding=CSV_ENCODING)
    result.dataset.issues.to_csv(paths["calidad"], index=False, encoding=CSV_ENCODING)
    model_selection_table(result).to_csv(paths["seleccion"], index=False, encoding=CSV_ENCODING)
    parameter_table(result).to_csv(paths["parametros"], index=False, encoding=CSV_ENCODING)
    format_timestamps(result.events).to_csv(paths["eventos"], index=False, encoding=CSV_ENCODING)
    result.drainage.to_csv(paths["drenaje"], index=False, encoding=CSV_ENCODING)
    paths["parametros_modelo"].write_text(json.dumps(parameters_for_model(result), indent=2, ensure_ascii=False),
                                          encoding="utf-8")
    paths["manifest"].write_text(json.dumps(manifest(result), indent=2, ensure_ascii=False), encoding="utf-8")
    return paths
