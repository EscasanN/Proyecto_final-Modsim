"""Conversión de datos públicos con un archivo de prueba que imita el formato de la fuente."""

import json

import numpy as np
import pandas as pd
import pytest

from src.macetas.data_io import load_dataset
from src.macetas.public_data import convert_chase2026, watered_plants


def fake_source(path, days=10):
    """Dos plantas en secado continuo y una con aportes de agua; filas cada 15 min."""
    times = pd.date_range("2024-07-24 00:30", periods=days * 96, freq="15min")
    rows = []
    for plant_id, watered in ((1, False), (2, False), (3, True)):
        mass = 7000.0
        for t in times:
            mass -= 2.0 if 6 <= t.hour < 18 else 0.1
            if watered and t.hour == 1 and t.minute == 0:
                mass += 120.0
            rows.append({"datetime": t.strftime("%d/%m/%Y %H:%M"), "sensor": "A", "ID": f"A{plant_id}",
                         "id": plant_id, "genotype": "Wild ", "treatment": "stress", "weight": round(mass, 1),
                         "pot": 620, "drySoil": 2000.0})
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def test_conversion_marks_public_origin_and_excludes_watered(tmp_path):
    src = fake_source(tmp_path / "Phenospex_data.csv")
    paths = convert_chase2026(src, tmp_path / "out", check_hash=False)
    cfg = json.loads(paths["config"].read_text(encoding="utf-8"))
    assert cfg["allowed_data_origins"] == ["public"]
    assert cfg["conversion"]["excluded_plant_ids"] == [3]
    obs = pd.read_csv(paths["observations"])
    assert set(obs["data_origin"]) == {"public"} and set(obs["pot_id"]) == {"E01", "E02"}
    assert set(obs["reading_stage"]) == {"no_irrigation"}
    hours = pd.to_datetime(obs["timestamp"].str[:19]).dt.hour
    assert set(hours) <= {7, 13, 19}
    assert obs["timestamp"].str.endswith("-06:00").all()

    ds = load_dataset(paths["config"])
    assert ds.n_errors == 0, ds.issues
    assert ds.observations["deficit_ml"].iloc[0] >= 0
    assert {w[0] for w in ds.windows} == {"fit", "validation"}


def test_hash_check_rejects_modified_source(tmp_path):
    src = fake_source(tmp_path / "Phenospex_data.csv", days=2)
    with pytest.raises(ValueError, match="sha256"):
        convert_chase2026(src, tmp_path / "out")


def test_watered_plants_uses_net_rise_over_three_hours():
    t = pd.date_range("2024-07-24", periods=12, freq="15min")
    slow = np.r_[np.full(4, 5000.0), 5000 + 20 * np.arange(1, 9)]  # +160 g en 2 h, pasos de 20 g
    data = pd.DataFrame({"t": np.tile(t, 2), "id": np.repeat([1, 2], 12),
                         "weight": np.r_[slow, 5000 - np.arange(12.0)]})
    assert watered_plants(data, 50.0) == [1]
