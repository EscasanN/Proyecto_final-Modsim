import pandas as pd
import pytest

from src.macetas.time_blocks import block_segments, segment_matrix, validate_blocks

BLOCKS = [{"name": "day", "start_hour": 6, "end_hour": 18}, {"name": "night", "start_hour": 18, "end_hour": 6}]


def ts(text):
    return pd.Timestamp(text).tz_convert("America/Guatemala")


def test_interval_crossing_evening_boundary():
    segs = block_segments(ts("2000-01-01T17:00:00-06:00"), ts("2000-01-01T20:00:00-06:00"), BLOCKS)
    assert segs == [(0, 1.0), (1, 2.0)]


def test_interval_crossing_midnight_and_morning():
    segs = block_segments(ts("2000-01-01T19:00:00-06:00"), ts("2000-01-02T07:00:00-06:00"), BLOCKS)
    assert segs == [(1, 11.0), (0, 1.0)]


def test_multi_day_hours_add_up():
    t0, t1 = ts("2000-01-01T07:30:00-06:00"), ts("2000-01-03T13:15:00-06:00")
    hours, idx = segment_matrix([t0], [t1], BLOCKS)
    assert hours.sum() == pytest.approx((t1 - t0).total_seconds() / 3600)
    assert hours[idx == 1].sum() == pytest.approx(24.0)  # dos noches completas


def test_blocks_must_cover_the_day_once():
    with pytest.raises(ValueError):
        validate_blocks([{"name": "day", "start_hour": 6, "end_hour": 18}])
    with pytest.raises(ValueError):
        validate_blocks(BLOCKS + [{"name": "extra", "start_hour": 10, "end_hour": 12}])
    validate_blocks(BLOCKS)
    validate_blocks([{"name": "all", "start_hour": 0, "end_hour": 24}])
