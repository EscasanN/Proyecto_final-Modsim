"""Lectura, control de calidad y transformación a déficit de las observaciones.

Módulo de Nelson Escalante (datos, protocolo y calibración). Las reglas que aplica
están descritas en docs/data_dictionary.md; un cambio en ellas debe reflejarse
en ese documento.

Principios:
- Los CSV originales solo se leen; nunca se modifican ni se completan.
- Un valor faltante sigue faltante (NaN); nunca se convierte en cero.
- Cada fila conserva su número de línea del CSV (`row`) para rastrear incidencias.
- Las incidencias se reportan; los datos no se corrigen en silencio.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

POT_COLUMNS = (
    "pot_id", "species", "substrate", "location", "pair_id", "treatment",
    "reference_mass_g", "reference_timestamp", "pot_dimensions",
    "plant_description", "data_origin", "notes",
)
OBSERVATION_COLUMNS = (
    "timestamp", "pot_id", "observer", "phase", "treatment", "reading_stage",
    "mass_g", "irrigation_ml", "drainage_ml", "irrigation_timestamp", "event_id",
    "ambient_temperature_c", "top_soil_dry", "notes", "quality_flag", "data_origin",
)
SCALE_COLUMNS = (
    "timestamp", "observer", "scale_id", "object_id", "known_mass_g",
    "reading_g", "resolution_g", "notes", "data_origin",
)

PHASES = ("pilot", "fit", "validation", "intervention")
STAGES = ("pre_irrigation", "post_drainage", "no_irrigation", "drainage_check")
TREATMENTS = ("none", "base", "optimized")
# Prueba táctil de los ~2.5 cm superiores del sustrato (criterio de riego de las fuentes de manejo).
TOP_SOIL_VALUES = ("yes", "no")
QUALITY_FLAGS = ("ok", "suspect", "bad")
DATA_ORIGINS = ("observed", "public", "estimated", "synthetic")

# Una lectura "después de evento" puede iniciar un intervalo de secado y una
# lectura "antes de evento" puede cerrarlo.
STAGES_AFTER_EVENT = ("post_drainage", "no_irrigation")
STAGES_BEFORE_EVENT = ("pre_irrigation", "no_irrigation")
EVENT_STAGES = ("pre_irrigation", "post_drainage", "drainage_check")

ISSUE_COLUMNS = ("severity", "check", "file", "row", "pot_id", "message")
_OFFSET_PATTERN = r"(?:Z|[+-]\d{2}:?\d{2})$"


class DataQualityError(RuntimeError):
    """Los datos tienen errores de calidad que impiden continuar."""


@dataclass
class Dataset:
    """Datos leídos y comprobados, listos para calibración o validación."""

    pots: pd.DataFrame
    observations: pd.DataFrame
    scale_checks: pd.DataFrame
    issues: pd.DataFrame
    scale_stats: dict
    tolerances: dict
    windows: list
    config: dict

    @property
    def n_errors(self) -> int:
        return int((self.issues["severity"] == "error").sum())

    @property
    def n_warnings(self) -> int:
        return int((self.issues["severity"] == "warning").sum())


class IssueLog:
    """Acumula incidencias de calidad con su archivo y línea de origen."""

    def __init__(self) -> None:
        self._rows: list[dict] = []

    def add(self, severity, check, file, message, row=None, pot_id=None) -> None:
        self._rows.append(dict(severity=severity, check=check, file=file,
                               row=row, pot_id=pot_id, message=message))

    def add_rows(self, severity, check, file, frame, mask, message) -> None:
        """Registra una incidencia por cada fila de `frame` donde `mask` es True.

        `message` puede ser un texto o una función que recibe la fila.
        """
        for _, r in frame.loc[mask].iterrows():
            text = message(r) if callable(message) else message
            self.add(severity, check, file, text, r["row"], r.get("pot_id"))

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame(self._rows, columns=list(ISSUE_COLUMNS))


# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

def load_data_config(path) -> dict:
    """Lee la configuración de datos y resuelve rutas relativas al archivo."""
    path = Path(path).resolve()
    cfg = json.loads(path.read_text(encoding="utf-8"))
    base = path.parent
    cfg["_path"] = str(path)
    cfg["_data_dir"] = str((base / cfg["data_dir"]).resolve())
    cfg["_outputs"] = {k: str((base / v).resolve()) for k, v in cfg["outputs"].items()}
    return cfg


def parse_windows(split_cfg: dict, tz: str) -> list[tuple[str, pd.Timestamp, pd.Timestamp]]:
    """Convierte las ventanas de partición en (fase, inicio, fin) comprobadas.

    Se ignoran las ventanas sin inicio o fin (aún no definidas). Inicio incluido,
    fin excluido. Las ventanas no pueden solaparse.
    """
    windows = []
    for w in split_cfg.get("windows", []):
        if w.get("start") is None or w.get("end") is None:
            continue
        if w["phase"] not in PHASES:
            raise ValueError(f"Fase de partición desconocida: {w['phase']!r}")
        start, end = (_parse_one_timestamp(w[k], tz) for k in ("start", "end"))
        if start >= end:
            raise ValueError(f"Ventana {w['phase']}: el inicio debe ser anterior al fin.")
        windows.append((w["phase"], start, end))
    windows.sort(key=lambda w: w[1])
    for (p0, _, e0), (p1, s1, _) in zip(windows, windows[1:]):
        if s1 < e0:
            raise ValueError(f"Las ventanas {p0} y {p1} se solapan.")
    return windows


def _parse_one_timestamp(text: str, tz: str) -> pd.Timestamp:
    if not pd.Series([text]).str.contains(_OFFSET_PATTERN, regex=True).iloc[0]:
        raise ValueError(f"Fecha sin zona horaria: {text!r}")
    return pd.Timestamp(text).tz_convert(tz)


def assign_windows(timestamps: pd.Series, windows) -> pd.Series:
    """Fase de partición que corresponde a cada instante (NaN si ninguna)."""
    out = pd.Series(np.nan, index=timestamps.index, dtype=object)
    for phase, start, end in windows:
        out[(timestamps >= start) & (timestamps < end)] = phase
    return out


# ---------------------------------------------------------------------------
# Lectura de archivos
# ---------------------------------------------------------------------------

def _read_csv(path: Path, columns, label: str, issues: IssueLog, required: bool) -> pd.DataFrame:
    if not path.exists():
        issues.add("error" if required else "warning", "archivo", label,
                   f"No existe el archivo {path}.")
        frame = pd.DataFrame({c: pd.Series(dtype="str") for c in columns})
        frame.insert(0, "row", pd.Series(dtype=int))
        return frame
    frame = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    for col in frame.columns:
        values = frame[col].astype("string").str.strip()
        frame[col] = values.mask(values.eq(""))
    for col in columns:
        if col not in frame.columns:
            issues.add("error", "columnas", label, f"Falta la columna obligatoria '{col}'.")
            frame[col] = pd.Series(np.nan, index=frame.index, dtype="str")
    for col in frame.columns:
        if col not in columns:
            issues.add("warning", "columnas", label, f"Columna no documentada '{col}'; se conserva.")
    frame.insert(0, "row", np.arange(len(frame)) + 2)  # línea 1 = encabezado
    return frame


def _to_numeric(frame, col, label, issues) -> None:
    raw = frame[col]
    num = pd.to_numeric(raw, errors="coerce").astype(float)
    issues.add_rows("error", "numerico", label, frame, raw.notna() & num.isna(),
                    lambda r: f"'{col}' no es numérico: {r[col]!r}.")
    frame[col] = num


def _to_timestamp(frame, col, tz, label, issues, required: bool) -> None:
    raw = frame[col]
    present = raw.notna()
    has_offset = raw.str.contains(_OFFSET_PATTERN, regex=True, na=False)
    parsed = pd.to_datetime(raw.where(has_offset), format="ISO8601", utc=True, errors="coerce")
    issues.add_rows("error", "zona_horaria", label, frame, present & ~has_offset,
                    lambda r: f"'{col}' sin zona horaria: {r[col]!r} (use p. ej. -06:00).")
    issues.add_rows("error", "fecha", label, frame, present & has_offset & parsed.isna(),
                    lambda r: f"'{col}' no es una fecha ISO 8601 válida: {r[col]!r}.")
    if required:
        issues.add_rows("error", "faltante", label, frame, ~present, f"Falta '{col}'.")
    frame[col] = parsed.dt.tz_convert(tz)


def _check_category(frame, col, allowed, label, issues, required: bool) -> None:
    raw = frame[col]
    issues.add_rows("error", "categoria", label, frame, raw.notna() & ~raw.isin(allowed),
                    lambda r: f"'{col}' = {r[col]!r} no está en {list(allowed)}.")
    if required:
        issues.add_rows("error", "faltante", label, frame, raw.isna(), f"Falta '{col}'.")


def _check_origin(frame, cfg, label, issues) -> None:
    _check_category(frame, "data_origin", DATA_ORIGINS, label, issues, required=True)
    allowed = cfg["allowed_data_origins"]
    issues.add_rows("error", "origen", label, frame,
                    frame["data_origin"].isin(DATA_ORIGINS) & ~frame["data_origin"].isin(allowed),
                    lambda r: f"Origen '{r['data_origin']}' no permitido en este conjunto "
                              f"(permitidos: {allowed}). No mezclar datos sintéticos o "
                              f"estimados con observaciones reales.")


# ---------------------------------------------------------------------------
# Comprobaciones por archivo
# ---------------------------------------------------------------------------

def _check_pots(pots, cfg, issues) -> None:
    label = "macetas"
    issues.add_rows("error", "faltante", label, pots, pots["pot_id"].isna(), "Falta 'pot_id'.")
    dup = pots["pot_id"].notna() & pots["pot_id"].duplicated(keep=False)
    issues.add_rows("error", "duplicado", label, pots, dup,
                    lambda r: f"pot_id repetido: {r['pot_id']}.")
    _to_numeric(pots, "reference_mass_g", label, issues)
    issues.add_rows("error", "referencia", label, pots, ~(pots["reference_mass_g"] > 0),
                    "reference_mass_g debe ser una masa positiva medida (M_ref).")
    _to_timestamp(pots, "reference_timestamp", cfg["timezone"], label, issues, required=True)
    _check_category(pots, "treatment", TREATMENTS, label, issues, required=False)
    _check_origin(pots, cfg, label, issues)


def _check_scale(scale, cfg, issues) -> None:
    label = "balanza"
    for col in ("known_mass_g", "reading_g", "resolution_g"):
        _to_numeric(scale, col, label, issues)
    _to_timestamp(scale, "timestamp", cfg["timezone"], label, issues, required=True)
    issues.add_rows("error", "faltante", label, scale, scale["object_id"].isna(), "Falta 'object_id'.")
    issues.add_rows("error", "faltante", label, scale, scale["reading_g"].isna(), "Falta 'reading_g'.")
    issues.add_rows("error", "resolucion", label, scale, ~(scale["resolution_g"] > 0),
                    "resolution_g debe ser positiva (resolución indicada por la balanza).")
    if len(scale):
        _check_origin(scale, cfg, label, issues)


def _check_observations(obs, pots, cfg, issues) -> None:
    label = "observaciones"
    tz = cfg["timezone"]
    _to_timestamp(obs, "timestamp", tz, label, issues, required=True)
    _to_timestamp(obs, "irrigation_timestamp", tz, label, issues, required=False)
    for col in ("mass_g", "irrigation_ml", "drainage_ml", "ambient_temperature_c"):
        _to_numeric(obs, col, label, issues)

    _check_category(obs, "phase", PHASES, label, issues, required=True)
    _check_category(obs, "reading_stage", STAGES, label, issues, required=True)
    _check_category(obs, "treatment", TREATMENTS, label, issues, required=False)
    _check_category(obs, "quality_flag", QUALITY_FLAGS, label, issues, required=True)
    _check_category(obs, "top_soil_dry", TOP_SOIL_VALUES, label, issues, required=False)
    _check_origin(obs, cfg, label, issues)

    known = set(pots["pot_id"].dropna())
    issues.add_rows("error", "maceta", label, obs, ~obs["pot_id"].isin(known),
                    lambda r: f"pot_id {r['pot_id']!r} no figura en macetas.csv.")
    issues.add_rows("warning", "faltante", label, obs, obs["observer"].isna(), "Falta 'observer'.")
    issues.add_rows("warning", "faltante", label, obs, obs["mass_g"].isna(),
                    "Lectura sin masa: se conserva como faltante y no se usa en el ajuste.")
    issues.add_rows("error", "masa", label, obs, obs["mass_g"] <= 0, "mass_g debe ser positiva.")

    key = ["pot_id", "timestamp", "reading_stage"]
    dup = obs[key].notna().all(axis=1) & obs.duplicated(key, keep=False)
    issues.add_rows("error", "duplicado", label, obs, dup,
                    "Lectura duplicada (misma maceta, hora y etapa).")

    stage = obs["reading_stage"]
    is_post = stage == "post_drainage"
    for col in ("irrigation_ml", "drainage_ml", "irrigation_timestamp"):
        issues.add_rows("error", "evento", label, obs, ~is_post & obs[col].notna(),
                        f"'{col}' solo se registra en la fila post_drainage del evento "
                        f"(evita contar el riego dos veces).")
    for col in ("irrigation_ml", "drainage_ml"):
        issues.add_rows("error", "negativo", label, obs, obs[col] < 0, f"'{col}' no puede ser negativo.")
    issues.add_rows("error", "evento", label, obs, is_post & obs["irrigation_ml"].isna(),
                    "Fila post_drainage sin irrigation_ml.")
    issues.add_rows("warning", "evento", label, obs, is_post & obs["drainage_ml"].isna(),
                    "Drenaje no medido: queda faltante (no se asume cero).")
    issues.add_rows("warning", "evento", label, obs, is_post & obs["irrigation_timestamp"].isna(),
                    "Falta la hora real de aplicación del riego.")
    issues.add_rows("error", "evento", label, obs, stage.isin(EVENT_STAGES) & obs["event_id"].isna(),
                    "Las etapas de riego requieren event_id.")
    issues.add_rows("error", "evento", label, obs, (stage == "no_irrigation") & obs["event_id"].notna(),
                    "Una lectura no_irrigation no debe tener event_id.")
    _check_events(obs, cfg, issues)


def _check_events(obs, cfg, issues) -> None:
    label = "observaciones"
    ev = obs[obs["event_id"].notna()]
    tol = cfg["quality"]["drainage_excess_tolerance_ml"]
    for event_id, g in ev.groupby("event_id"):
        first = g.iloc[0]
        if g["pot_id"].nunique() > 1:
            issues.add("error", "evento", label, f"El evento {event_id} mezcla macetas.", first["row"])
        counts = g["reading_stage"].value_counts()
        for st in ("pre_irrigation", "post_drainage"):
            if counts.get(st, 0) > 1:
                issues.add("error", "evento", label, f"El evento {event_id} tiene más de una fila {st}.",
                           first["row"], first["pot_id"])
            if counts.get(st, 0) == 0:
                issues.add("warning", "evento", label, f"El evento {event_id} no tiene fila {st}.",
                           first["row"], first["pot_id"])
        pre = g[g["reading_stage"] == "pre_irrigation"]
        post = g[g["reading_stage"] == "post_drainage"]
        if len(pre) == 1 and len(post) == 1:
            t_pre, p = pre["timestamp"].iloc[0], post.iloc[0]
            t_irr, t_post = p["irrigation_timestamp"], p["timestamp"]
            if pd.notna(t_irr) and pd.notna(t_pre) and pd.notna(t_post) and not (t_pre <= t_irr <= t_post):
                issues.add("warning", "evento", label,
                           f"Evento {event_id}: la hora de riego no está entre el pesaje previo y el posterior.",
                           p["row"], p["pot_id"])
        if len(post) == 1:
            p = post.iloc[0]
            if p["drainage_ml"] > p["irrigation_ml"] + tol:
                issues.add("warning", "evento", label,
                           f"Evento {event_id}: drenaje mayor que el riego aplicado.", p["row"], p["pot_id"])


# ---------------------------------------------------------------------------
# Transformaciones y comprobaciones físicas
# ---------------------------------------------------------------------------

def add_deficit(obs: pd.DataFrame, pots: pd.DataFrame, rho_w: float) -> pd.DataFrame:
    """Añade D = (M_ref - M) / rho_w en mL. Lecturas negativas se conservan."""
    ref = pots.dropna(subset=["pot_id"]).drop_duplicates("pot_id").set_index("pot_id")["reference_mass_g"]
    obs = obs.copy()
    obs["reference_mass_g"] = obs["pot_id"].map(ref).astype(float)
    obs["deficit_ml"] = (obs["reference_mass_g"] - obs["mass_g"]) / rho_w
    return obs


def scale_statistics(scale: pd.DataFrame) -> dict:
    """Resumen de la verificación de balanza.

    sigma_reading_g combina la repetibilidad (desviación agrupada entre objetos)
    con el error de cuantización de la resolución (res / sqrt(12)).
    """
    s = scale[scale["reading_g"].notna()]
    resolution = float(s["resolution_g"].max()) if s["resolution_g"].notna().any() else np.nan
    groups = s.groupby("object_id")["reading_g"]
    dof = (groups.count() - 1).clip(lower=0)
    var = groups.var(ddof=1).fillna(0.0)
    sd = float(np.sqrt((var * dof).sum() / dof.sum())) if dof.sum() > 0 else np.nan
    known = s.dropna(subset=["known_mass_g"]).groupby("object_id").agg(
        known=("known_mass_g", "first"), mean=("reading_g", "mean"))
    bias = (known["mean"] - known["known"]).abs()
    quant = resolution ** 2 / 12 if np.isfinite(resolution) else 0.0
    return {
        "n_readings": int(len(s)),
        "n_objects": int(groups.ngroups),
        "resolution_g": resolution,
        "repeatability_sd_g": sd,
        "max_abs_bias_g": float(bias.max()) if len(bias) else np.nan,
        "sigma_reading_g": float(np.sqrt(sd ** 2 + quant)) if np.isfinite(sd) else np.nan,
    }


def resolve_tolerances(cfg: dict, scale_stats: dict, issues: IssueLog) -> dict:
    """Tolerancias de masa: valor configurado o k * sqrt(2) * sigma de la balanza.

    El factor sqrt(2) aparece porque cada comprobación compara dos lecturas.
    """
    q = cfg["quality"]
    mass_tol = q.get("mass_tolerance_g")
    source = "configuración"
    if mass_tol is None:
        sigma = scale_stats["sigma_reading_g"]
        if np.isfinite(sigma):
            mass_tol = q["tolerance_sigmas"] * np.sqrt(2) * sigma
            source = "verificación de balanza"
        else:
            mass_tol = np.nan
            source = "no disponible"
            issues.add("warning", "tolerancia", "balanza",
                       "Sin verificación de balanza: no se evalúan aumentos de masa ni déficits negativos.")
    return {"mass_tolerance_g": float(mass_tol), "mass_tolerance_source": source,
            "drainage_excess_tolerance_ml": float(q["drainage_excess_tolerance_ml"])}


def drying_pairs(obs: pd.DataFrame, usable: pd.Series) -> pd.DataFrame:
    """Pares de lecturas consecutivas de una maceta sin riego ni drenaje entre ellas.

    El par (i0, i1) es válido si i0 es una lectura posterior a un evento
    (post_drainage o no_irrigation), i1 es anterior a un evento (pre_irrigation o
    no_irrigation) y ninguna fila de riego de esa maceta, con cualquier marca de
    calidad, cae estrictamente entre ambas.
    """
    rows = obs[usable & obs["timestamp"].notna() & (obs["reading_stage"] != "drainage_check")]
    event_times = pd.concat([
        obs.loc[obs["reading_stage"].isin(EVENT_STAGES), ["pot_id", "timestamp"]],
        obs.loc[obs["irrigation_timestamp"].notna(), ["pot_id", "irrigation_timestamp"]]
           .rename(columns={"irrigation_timestamp": "timestamp"}),
    ]).dropna()
    pairs = []
    for pot_id, g in rows.sort_values("timestamp").groupby("pot_id"):
        times = event_times.loc[event_times["pot_id"] == pot_id, "timestamp"]
        readings = list(g.iterrows())
        for (i0, r0), (i1, r1) in zip(readings, readings[1:]):
            if r0["reading_stage"] not in STAGES_AFTER_EVENT or r1["reading_stage"] not in STAGES_BEFORE_EVENT:
                continue
            if ((times > r0["timestamp"]) & (times < r1["timestamp"])).any():
                continue
            pairs.append((pot_id, i0, i1))
    return pd.DataFrame(pairs, columns=["pot_id", "i0", "i1"])


def _check_physical(obs, tolerances, issues) -> None:
    label = "observaciones"
    tol = tolerances["mass_tolerance_g"]
    if not np.isfinite(tol):
        return
    issues.add_rows("warning", "deficit_negativo", label, obs,
                    (obs["reading_stage"] != "drainage_check")  # durante el drenaje es esperable
                    & ((obs["mass_g"] - obs["reference_mass_g"]) > tol),
                    lambda r: f"Masa {r['mass_g'] - r['reference_mass_g']:.1f} g sobre M_ref: "
                              f"revisar drenaje incompleto o error; se conserva sin corregir.")
    usable = obs["mass_g"].notna() & obs["quality_flag"].ne("bad")
    for _, p in drying_pairs(obs, usable).iterrows():
        r0, r1 = obs.loc[p["i0"]], obs.loc[p["i1"]]
        gain = r1["mass_g"] - r0["mass_g"]
        if gain > tol:
            issues.add("warning", "aumento_masa", label,
                       f"La masa subió {gain:.1f} g sin riego registrado desde la fila {r0['row']} "
                       f"(¿riego o lluvia no anotados, error de pesaje?).", r1["row"], r1["pot_id"])


def _check_phase_windows(obs, windows, issues) -> None:
    if not windows:
        return
    label = "observaciones"
    mismatch = obs["phase"].notna() & obs["split"].notna() & (obs["phase"] != obs["split"])
    issues.add_rows("error", "particion", label, obs, mismatch,
                    lambda r: f"Fase registrada '{r['phase']}' distinta de la ventana congelada '{r['split']}'.")
    issues.add_rows("warning", "particion", label, obs, obs["timestamp"].notna() & obs["split"].isna(),
                    "Lectura fuera de toda ventana de partición; no se usa en ajuste ni validación.")


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def load_dataset(config) -> Dataset:
    """Lee los tres CSV, aplica los controles de calidad y calcula el déficit.

    `config` es la ruta a configs/data.json o un diccionario ya cargado con
    load_data_config. Nunca lanza por datos defectuosos: las incidencias quedan
    en `Dataset.issues` y los pasos siguientes deciden si pueden continuar.
    """
    cfg = config if isinstance(config, dict) else load_data_config(config)
    tz = cfg["timezone"]
    issues = IssueLog()
    data_dir = Path(cfg["_data_dir"])
    files = cfg["files"]

    pots = _read_csv(data_dir / files["pots"], POT_COLUMNS, "macetas", issues, required=True)
    obs = _read_csv(data_dir / files["observations"], OBSERVATION_COLUMNS, "observaciones", issues, required=True)
    scale = _read_csv(data_dir / files["scale_checks"], SCALE_COLUMNS, "balanza", issues, required=False)

    _check_pots(pots, cfg, issues)
    _check_scale(scale, cfg, issues)
    _check_observations(obs, pots, cfg, issues)

    windows = parse_windows(cfg["split"], tz)
    obs = add_deficit(obs, pots, cfg["water_density_g_per_ml"])
    obs["split"] = assign_windows(obs["timestamp"], windows)
    _check_phase_windows(obs, windows, issues)

    stats = scale_statistics(scale)
    tolerances = resolve_tolerances(cfg, stats, issues)
    _check_physical(obs, tolerances, issues)

    issue_frame = issues.frame()
    error_rows = issue_frame.loc[(issue_frame["severity"] == "error")
                                 & (issue_frame["file"] == "observaciones"), "row"]
    obs["has_error"] = obs["row"].isin(error_rows)
    obs["usable"] = (obs["mass_g"].notna() & ~obs["has_error"]
                     & ~obs["quality_flag"].isin(cfg["quality"]["exclude_flags"]))
    return Dataset(pots=pots, observations=obs, scale_checks=scale, issues=issue_frame,
                   scale_stats=stats, tolerances=tolerances, windows=windows, config=cfg)


def format_timestamps(frame: pd.DataFrame) -> pd.DataFrame:
    """Copia con las columnas de fecha en ISO 8601 con zona horaria, para exportar."""
    out = frame.copy()
    for col in out.columns:
        if isinstance(out[col].dtype, pd.DatetimeTZDtype):
            out[col] = out[col].map(lambda t: t.isoformat() if pd.notna(t) else "")
    return out
