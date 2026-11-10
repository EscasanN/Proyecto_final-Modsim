"""Conversión de datos PÚBLICOS de terceros al formato de data/raw.

Fuente: Chase, R. R. (2026). *Transpiration monitoring reveals diverse drought
coping strategies in wild and cultivated enset (Ensete ventricosum)* [Conjunto de
datos]. Zenodo. https://doi.org/10.5281/zenodo.23213759 (CC BY 4.0).

`Phenospex_data.csv` contiene la masa de cada maceta cada 15 min en una plataforma
gravimétrica. Se usa el periodo de estrés hídrico (secado continuo) de las plantas
que pasaron de control a estrés. Todas las filas llevan `data_origin = public`: son
mediciones reales de otro equipo y otra especie, no observaciones del proyecto.

Decisiones de conversión (docs/datos_publicos.md):
- Lecturas a las horas de revisión del protocolo (07:00, 13:00, 19:00), tomando la
  lectura original más cercana dentro de `tolerance_min`.
- M_ref = primera masa del periodo de estrés (referencia operacional, no drenada).
- Se excluye toda planta cuya masa sube más de `rise_threshold_g` en alguna
  ventana de 3 h durante el estrés: indica aportes de agua que la fuente no
  documenta (cantidad y momento), y no se reconstruyen. La regla se aplica a todas
  las plantas por igual y las excluidas quedan registradas en data_config.json.
- La fuente no declara zona horaria; se conserva la hora de reloj y se etiqueta con el
  desfase nominal -06:00 (America/Guatemala, sin horario de verano), que exige el simulador.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .data_io import OBSERVATION_COLUMNS, POT_COLUMNS, SCALE_COLUMNS

SOURCE = {
    "citation": "Chase, R. R. (2026). Transpiration monitoring reveals diverse drought coping strategies "
                "in wild and cultivated enset (Ensete ventricosum) [Data set]. Zenodo.",
    "doi": "10.5281/zenodo.23213759",
    "url": "https://zenodo.org/records/23213759",
    "license": "CC BY 4.0",
    "file": "Phenospex_data.csv",
    "sha256": "f3dc9a70477d8a9423d665a813c3391f5db9eb4282338ff89050f93d52c36336",
}
OFFSET = "-06:00"  # nominal: solo conserva la hora de reloj de la fuente


def _iso(t: pd.Timestamp) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%S") + OFFSET


def watered_plants(data: pd.DataFrame, rise_threshold_g: float) -> list[int]:
    """Plantas con una subida neta de masa mayor que el umbral en alguna ventana de 3 h."""
    rises = (data.sort_values("t").set_index("t").groupby("id")["weight"]
             .apply(lambda w: (w - w.rolling("3h").min()).max()))
    return sorted(int(i) for i in rises.index[rises > rise_threshold_g])


def convert_chase2026(source_csv, out_dir, review_hours=(7, 13, 19), tolerance_min: float = 15.0,
                      rise_threshold_g: float = 50.0, fit_days: int = 7, check_hash: bool = True) -> dict[str, Path]:
    """Escribe macetas.csv, observaciones.csv, balanza.csv vacío y data_config.json en `out_dir`."""
    source_csv, out_dir = Path(source_csv), Path(out_dir)
    if check_hash:
        digest = hashlib.sha256(source_csv.read_bytes()).hexdigest()
        if digest != SOURCE["sha256"]:
            raise ValueError(f"El archivo no coincide con la versión publicada (sha256 {digest}).")
    raw = pd.read_csv(source_csv)
    raw["genotype"] = raw["genotype"].str.strip()
    raw["t"] = pd.to_datetime(raw["datetime"], format="%d/%m/%Y %H:%M")
    stressed = raw.groupby("id")["treatment"].transform(lambda s: (s == "stress").any())
    data = raw[stressed & (raw["treatment"] == "stress")].sort_values(["id", "t"]).reset_index(drop=True)
    excluded = watered_plants(data, rise_threshold_g)
    data = data[~data["id"].isin(excluded)].reset_index(drop=True)

    start = data["t"].min().normalize()
    end = data["t"].max().normalize() + pd.Timedelta(days=1)
    split = start + pd.Timedelta(days=fit_days)
    phase = lambda t: "fit" if t < split else "validation"

    pots, rows = [], []
    for plant_id, g in data.groupby("id"):
        g = g.reset_index(drop=True)
        pot_id = f"E{plant_id:02d}"
        pots.append({"pot_id": pot_id, "species": "Ensete ventricosum", "substrate": "No especificado en la fuente",
                     "location": f"Plataforma Phenospex, posición {g['ID'].iloc[0]}", "pair_id": "",
                     "treatment": "none", "reference_mass_g": g["weight"].iloc[0],
                     "reference_timestamp": _iso(g["t"].iloc[0]),
                     "pot_dimensions": f"Masa de maceta {g['pot'].iloc[0]} g; suelo seco {g['drySoil'].iloc[0]:.1f} g",
                     "plant_description": f"Genotipo {g['genotype'].iloc[0]}",
                     "data_origin": "public",
                     "notes": "M_ref = primera masa del periodo de estrés (referencia operacional, no drenada)"})

        def row(i, stage):
            r = {c: "" for c in OBSERVATION_COLUMNS}
            r.update(timestamp=_iso(g.at[i, "t"]), pot_id=pot_id, observer="Chase (2026), plataforma Phenospex",
                     phase=phase(g.at[i, "t"]), treatment="none", reading_stage=stage, mass_g=g.at[i, "weight"],
                     quality_flag="ok", data_origin="public",
                     notes=f"Fila original {g.at[i, 'datetime']}, sensor {g.at[i, 'sensor']}")
            rows.append(r)

        # Lecturas a las horas de revisión del protocolo; sin riegos en el periodo de estrés.
        used = set()
        days = pd.date_range(start, end - pd.Timedelta(days=1), freq="D")
        for day in days:
            for hour in review_hours:
                target = day + pd.Timedelta(hours=hour)
                gap = (g["t"] - target).abs()
                i = int(gap.idxmin())
                if gap[i] > pd.Timedelta(minutes=tolerance_min) or i in used:
                    continue
                row(i, "no_irrigation")
                used.add(i)

    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {"pots": out_dir / "macetas.csv", "observations": out_dir / "observaciones.csv",
             "scale_checks": out_dir / "balanza.csv", "config": out_dir / "data_config.json"}
    pd.DataFrame(pots, columns=list(POT_COLUMNS)).to_csv(paths["pots"], index=False)
    obs = pd.DataFrame(rows, columns=list(OBSERVATION_COLUMNS)).sort_values(["pot_id", "timestamp"])
    obs.to_csv(paths["observations"], index=False)
    pd.DataFrame(columns=list(SCALE_COLUMNS)).to_csv(paths["scale_checks"], index=False)

    # Diferencias entre lecturas consecutivas de 15 min de la misma noche (pérdida casi nula).
    diff = data.groupby("id")["weight"].diff()
    gap = data.groupby("id")["t"].diff()
    night = diff[data["t"].dt.hour.isin([1, 2, 3, 4]) & gap.eq(pd.Timedelta(minutes=15))]
    noise_sd = float(night.std())
    config = {
        "_nota": "DATOS PÚBLICOS de terceros (Chase 2026, Zenodo, CC BY 4.0), convertidos por "
                 "src/macetas/public_data.py. Otra especie y otro montaje; no son mediciones del proyecto.",
        "source": SOURCE,
        "data_dir": ".",
        "files": {"pots": "macetas.csv", "observations": "observaciones.csv", "scale_checks": "balanza.csv"},
        "timezone": "America/Guatemala",
        "_nota_timezone": "La fuente no declara zona horaria; se conserva la hora de reloj del registro "
                          "con desfase nominal -06:00. No indica que el ensayo ocurriera en Guatemala.",
        "water_density_g_per_ml": 1.0,
        "allowed_data_origins": ["public"],
        "split": {"frozen": True, "frozen_on": "conversión", "windows": [
            {"phase": "fit", "start": _iso(start), "end": _iso(split)},
            {"phase": "validation", "start": _iso(split), "end": _iso(end)}]},
        "quality": {
            "exclude_flags": ["bad"], "tolerance_sigmas": 3.0,
            "mass_tolerance_g": round(3 * np.sqrt(2) * noise_sd, 2),
            "_nota_tolerancia": f"Sin verificación de balanza en la fuente. Se estima con la desviación de las "
                                f"diferencias de 15 min entre 01:00 y 04:59 ({noise_sd:.2f} g), cota superior del ruido.",
            "drainage_excess_tolerance_ml": 2.0},
        "conversion": {"review_hours": list(review_hours), "tolerance_min": tolerance_min,
                       "rise_threshold_g": rise_threshold_g, "fit_days": fit_days, "n_plants": len(pots),
                       "excluded_plant_ids": excluded,
                       "_nota_exclusion": "Subida neta de masa > rise_threshold_g en 3 h durante el estrés: "
                                          "aportes de agua no documentados por la fuente."},
        "outputs": {"processed_dir": "salidas/processed", "tables_dir": "salidas/tables"},
    }
    paths["config"].write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    return paths
