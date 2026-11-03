"""Conjunto de datos SINTÉTICO con el mismo formato que data/raw.

Sirve para probar data_io y calibration con parámetros verdaderos conocidos y
para desarrollar antes de tener mediciones. Todas las filas llevan
data_origin = "synthetic" y la configuración generada solo admite ese origen, de
modo que no pueden mezclarse con observaciones reales. Estos datos NO validan el
modelo contra la realidad.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .calibration import predict_deficit
from .time_blocks import segment_matrix

DEFAULT_BLOCKS = [{"name": "day", "start_hour": 6, "end_hour": 18},
                  {"name": "night", "start_hour": 18, "end_hour": 6}]
DEFAULT_PARAMS = {"a_ml_per_h": 2.5, "b_per_h": -0.006, "q": [1.0, 0.35]}


def generate_synthetic(out_dir, seed: int = 20260001, n_pots: int = 6, start_date: str = "2000-01-03",
                       phase_days: dict | None = None, revision_hours=(7, 13, 19), dose_ml: float = 150.0,
                       irrigation_days=(1, 4, 7, 10, 13), drain_minutes: float = 30.0,
                       drain_tau_minutes: float = 4.0, noise_g: float = 0.4, resolution_g: float = 0.1,
                       pot_variation: float = 0.10, params: dict | None = None, blocks: list | None = None,
                       timezone: str = "America/Guatemala") -> dict[str, Path]:
    """Genera macetas.csv, observaciones.csv, balanza.csv y data_config.json en `out_dir`.

    El riego es fijo (dosis `dose_ml` en la revisión de las 07:00 de los días de
    `irrigation_days`); solo sirve para producir ciclos de secado. El agua excedente
    drena con constante `drain_tau_minutes` (0 = instantáneo). Con noise_g=0 y
    resolution_g=0 las lecturas son exactas.
    """
    rng = np.random.default_rng(seed)
    phase_days = phase_days or {"pilot": 2, "fit": 7, "validation": 7}
    params = params or DEFAULT_PARAMS
    blocks = blocks or DEFAULT_BLOCKS
    q = np.asarray(params["q"], float)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    start = pd.Timestamp(start_date).tz_localize(timezone)
    n_days = sum(phase_days.values())
    day_phase = [p for p, n in phase_days.items() for _ in range(n)]
    windows, cursor = [], start
    for p, n in phase_days.items():
        windows.append({"phase": p, "start": cursor.isoformat(), "end": (cursor + pd.Timedelta(days=n)).isoformat()})
        cursor += pd.Timedelta(days=n)

    def measure(mass):
        m = mass + rng.normal(0, noise_g) if noise_g > 0 else mass
        return round(m / resolution_g) * resolution_g if resolution_g > 0 else m

    def evolve(d, t0, t1, a):
        hours, idx = segment_matrix([t0], [t1], blocks)
        return float(predict_deficit([d], hours, idx, a, params["b_per_h"], q)[0])

    pots, rows, truth = [], [], {}
    for p in range(n_pots):
        pot_id = f"M{p + 1:02d}"
        m_ref = round(float(rng.uniform(850, 1150)), 1)
        a = params["a_ml_per_h"] * (float(rng.lognormal(0, pot_variation)) if pot_variation > 0 else 1.0)
        truth[pot_id] = {"reference_mass_g": m_ref, "a_ml_per_h": a}
        t_ref = start - pd.Timedelta(minutes=30)
        pots.append({"pot_id": pot_id, "species": "SINTETICA", "substrate": "SINTETICO", "location": "simulada",
                     "pair_id": f"P{p // 2 + 1}", "treatment": "base", "reference_mass_g": m_ref,
                     "reference_timestamp": t_ref.isoformat(), "pot_dimensions": "", "plant_description": "",
                     "data_origin": "synthetic", "notes": "Maceta sintética"})
        d, t_prev, n_event = 0.0, t_ref, 0

        def row(t, stage, mass, **extra):
            base = {"timestamp": t.isoformat(), "pot_id": pot_id, "observer": "simulado",
                    "phase": day_phase[(t - start).days], "treatment": "base", "reading_stage": stage,
                    "mass_g": mass, "irrigation_ml": "", "drainage_ml": "", "irrigation_timestamp": "",
                    "event_id": "", "ambient_temperature_c": "", "notes": "", "quality_flag": "ok",
                    "data_origin": "synthetic"}
            base.update(extra)
            rows.append(base)

        for day in range(n_days):
            for hour in revision_hours:
                t = start + pd.Timedelta(days=day, hours=hour - start.hour)
                d = evolve(d, t_prev, t, a)
                if not (day in irrigation_days and hour == revision_hours[0]):
                    row(t, "no_irrigation", measure(m_ref - d))
                    t_prev = t
                    continue
                n_event += 1
                event_id = f"{pot_id}-E{n_event:03d}"
                row(t, "pre_irrigation", measure(m_ref - d), event_id=event_id)
                t_irr = t + pd.Timedelta(minutes=3)
                d = evolve(d, t, t_irr, a)
                excess = max(0.0, dose_ml - d)
                d = max(0.0, d - dose_ml)

                def remaining(minutes):
                    return excess * np.exp(-minutes / drain_tau_minutes) if drain_tau_minutes > 0 else 0.0

                if day_phase[day] == "pilot":
                    d_check, t_check = d, t_irr
                    for minute in (5, 10, 15, 20):
                        tc = t_irr + pd.Timedelta(minutes=minute)
                        d_check = evolve(d_check, t_check, tc, a)
                        t_check = tc
                        row(tc, "drainage_check", measure(m_ref - d_check + remaining(minute)), event_id=event_id)
                t_post = t_irr + pd.Timedelta(minutes=drain_minutes)
                d = evolve(d, t_irr, t_post, a)
                rem = remaining(drain_minutes)
                drained = excess - rem
                drained_rec = max(0.0, round(drained + (rng.normal(0, 1.0) if noise_g > 0 else 0.0)))
                row(t_post, "post_drainage", measure(m_ref - d + rem), irrigation_ml=dose_ml,
                    drainage_ml=drained_rec if noise_g > 0 else drained,
                    irrigation_timestamp=t_irr.isoformat(), event_id=event_id)
                t_prev = t_post  # el excedente restante drena a la bandeja y se retira

    scale = []
    for obj, known in (("pesa_500g", 500.0), ("objeto_estable", None)):
        center = known if known is not None else 312.4
        for i in range(10):
            scale.append({"timestamp": (start - pd.Timedelta(hours=2, minutes=-i)).isoformat(), "observer": "simulado",
                          "scale_id": "BAL-SINT", "object_id": obj, "known_mass_g": "" if known is None else known,
                          "reading_g": measure(center), "resolution_g": resolution_g if resolution_g > 0 else 0.1,
                          "notes": "", "data_origin": "synthetic"})

    paths = {"pots": out_dir / "macetas.csv", "observations": out_dir / "observaciones.csv",
             "scale_checks": out_dir / "balanza.csv", "config": out_dir / "data_config.json",
             "truth": out_dir / "parametros_verdaderos.json"}
    pd.DataFrame(pots).to_csv(paths["pots"], index=False)
    pd.DataFrame(rows).to_csv(paths["observations"], index=False)
    pd.DataFrame(scale).to_csv(paths["scale_checks"], index=False)
    config = {
        "_nota": "DATOS SINTÉTICOS generados por src/macetas/synthetic_data.py. No son mediciones reales.",
        "data_dir": ".",
        "files": {"pots": "macetas.csv", "observations": "observaciones.csv", "scale_checks": "balanza.csv"},
        "timezone": timezone,
        "water_density_g_per_ml": 1.0,
        "allowed_data_origins": ["synthetic"],
        "split": {"frozen": True, "frozen_on": "generado", "windows": windows},
        "quality": {"exclude_flags": ["bad"], "tolerance_sigmas": 3.0, "mass_tolerance_g": None,
                    "drainage_excess_tolerance_ml": 2.0},
        "outputs": {"processed_dir": "salidas/processed", "tables_dir": "salidas/tables"},
    }
    paths["config"].write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    paths["truth"].write_text(json.dumps({
        "seed": seed, "params": params, "time_blocks": blocks, "per_pot": truth, "dose_ml": dose_ml,
        "noise_g": noise_g, "resolution_g": resolution_g, "drain_tau_minutes": drain_tau_minutes,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    return paths
