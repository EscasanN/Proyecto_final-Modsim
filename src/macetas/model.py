from __future__ import annotations

import json
from dataclasses import dataclass
from math import isfinite
from pathlib import Path

import pandas as pd

from .time_blocks import block_index, validate_blocks


def nonnegative(value: float, name: str) -> float:
    value = float(value)
    if not isfinite(value) or value < 0:
        raise ValueError(f"{name} debe ser finito y no negativo.")
    return value


def local_timestamp(value, timezone: str) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if pd.isna(timestamp) or timestamp.tzinfo is None:
        raise ValueError("Cada fecha debe incluir zona horaria.")
    return timestamp.tz_convert(timezone)


@dataclass(frozen=True)
class IrrigationBalance:
    deficit_ml: float
    drainage_ml: float
    retained_ml: float


def apply_irrigation(deficit_ml: float, irrigation_ml: float) -> IrrigationBalance:
    deficit = nonnegative(deficit_ml, "El déficit")
    irrigation = nonnegative(irrigation_ml, "El riego")
    retained = min(deficit, irrigation)
    return IrrigationBalance(deficit - retained, irrigation - retained, retained)


@dataclass(frozen=True)
class LossModel:
    a_ml_per_h: float
    b_per_h: float
    q: dict[str, float]
    time_blocks: list[dict]
    timezone: str = "America/Guatemala"
    data_origin: str = "analytical"

    def __post_init__(self):
        nonnegative(self.a_ml_per_h, "a")
        if not isfinite(self.b_per_h):
            raise ValueError("b debe ser finito.")
        validate_blocks(self.time_blocks)
        if set(self.q) != {block["name"] for block in self.time_blocks}:
            raise ValueError("Los factores q deben coincidir con los bloques horarios.")
        for value in self.q.values():
            nonnegative(value, "q")
        local_timestamp("2000-01-01T00:00:00+00:00", self.timezone)

    def factor_at(self, timestamp) -> float:
        timestamp = local_timestamp(timestamp, self.timezone)
        hour = (timestamp - timestamp.normalize()).value / 3_600_000_000_000
        index = block_index(hour, self.time_blocks)
        return self.q[self.time_blocks[index]["name"]]

    def rate(self, deficit_ml: float, factor: float) -> float:
        return factor * max(0.0, self.a_ml_per_h + self.b_per_h * deficit_ml)


def load_calibrated_model(path, pot_id: str | None = None, allow_synthetic: bool = False) -> LossModel:
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    origins = payload.get("data_origin", [])
    # public: mediciones reales de terceros (data/reference), distintas de las propias.
    if origins not in (["observed"], ["public"], ["synthetic"]):
        raise ValueError("Se requiere un único origen de datos: observed, public o synthetic.")
    if origins == ["synthetic"] and not allow_synthetic:
        raise ValueError("Los parámetros son sintéticos; use --allow-synthetic para una demostración.")
    if payload.get("status") != "frozen":
        raise ValueError("La partición de la calibración debe estar congelada.")
    scope = payload.get("selected_scope", "pooled")
    if scope not in ("pooled", "per_pot"):
        raise ValueError("El ámbito de calibración debe ser pooled o per_pot.")
    if scope == "per_pot" and pot_id is None:
        raise ValueError("La calibración por maceta requiere pot_id.")
    selected = payload.get("per_pot", {}).get(pot_id) if pot_id else payload.get("pooled")
    if selected is None:
        raise ValueError("No hay parámetros válidos para la maceta o el ámbito solicitado.")
    return LossModel(selected["a_ml_per_h"], selected["b_per_h"], selected["q"],
                     payload["time_blocks"], payload["timezone"], origins[0])
