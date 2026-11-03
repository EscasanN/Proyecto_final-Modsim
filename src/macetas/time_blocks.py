"""Bloques horarios del factor q(t) de la pérdida de agua.

Compartido entre calibración y simulación. Un bloque se define por su hora
local de inicio y fin; los bloques deben cubrir las 24 h sin solaparse. La hora
local se toma de la zona horaria de los instantes recibidos (America/Guatemala no
tiene horario de verano; en zonas con cambio horario habría que revisar los cortes).
"""

from __future__ import annotations

from math import isfinite

import numpy as np
import pandas as pd


def validate_blocks(blocks: list[dict]) -> None:
    """Comprueba cobertura completa sin solapamientos."""
    names = [b["name"] for b in blocks]
    if len(set(names)) != len(names):
        raise ValueError("Los bloques horarios deben tener nombres únicos.")
    for b in blocks:
        if not (isfinite(b["start_hour"]) and isfinite(b["end_hour"])
                and 0 <= b["start_hour"] < 24 and 0 <= b["end_hour"] <= 24):
            raise ValueError(f"Horas fuera de rango en el bloque {b['name']}.")
    cuts = sorted({0, 24, *(b["start_hour"] for b in blocks), *(b["end_hour"] for b in blocks)})
    for left, right in zip(cuts, cuts[1:]):
        hour = (left + right) / 2
        hits = sum(_contains(b, hour) for b in blocks)
        if hits != 1:
            raise ValueError(f"La hora {hour:.6f} pertenece a {hits} bloques; deben cubrir el día exactamente una vez.")


def _contains(block: dict, hour: float) -> bool:
    s, e = block["start_hour"], block["end_hour"] % 24
    if s == e:
        return True
    return s <= hour < e if s < e else (hour >= s or hour < e)


def block_index(hour: float, blocks: list[dict]) -> int:
    for i, b in enumerate(blocks):
        if _contains(b, hour):
            return i
    raise ValueError(f"La hora {hour} no pertenece a ningún bloque.")


def block_segments(t0: pd.Timestamp, t1: pd.Timestamp, blocks: list[dict]) -> list[tuple[int, float]]:
    """Divide [t0, t1) en tramos (índice de bloque, horas) en orden temporal."""
    if t1 <= t0:
        return []
    starts = sorted({b["start_hour"] for b in blocks})
    day0 = t0.normalize() - pd.Timedelta(days=1)
    n_days = (t1.normalize() - day0).days + 2
    cuts = sorted(c for d in range(n_days) for h in starts
                  if t0 < (c := day0 + pd.Timedelta(days=d, hours=h)) < t1)
    edges = [t0, *cuts, t1]
    segments = []
    for e0, e1 in zip(edges, edges[1:]):
        mid = e0 + (e1 - e0) / 2
        hour = (mid - mid.normalize()).value / 3_600_000_000_000
        segments.append((block_index(hour, blocks), (e1 - e0).total_seconds() / 3600))
    return segments


def segment_matrix(starts, ends, blocks) -> tuple[np.ndarray, np.ndarray]:
    """Matrices (n, S) de horas e índice de bloque por tramo, rellenadas con 0 h."""
    segs = [block_segments(t0, t1, blocks) for t0, t1 in zip(starts, ends)]
    width = max((len(s) for s in segs), default=1) or 1
    hours = np.zeros((len(segs), width))
    index = np.zeros((len(segs), width), dtype=int)
    for i, s in enumerate(segs):
        for j, (k, h) in enumerate(s):
            index[i, j], hours[i, j] = k, h
    return hours, index
