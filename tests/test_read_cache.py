"""Critical tests for the opt-in on-disk cache for adjusted wide-frame reads."""

from datetime import date
from pathlib import Path

import pandas as pd
from pandas.testing import assert_frame_equal
from support import staged_path, write_staged

from powernse.data import NSEData
from powernse.datasets import BHAVCOPY, CORPORATE_ACTIONS
from powernse.reading import WideFrameCache

_PARTS = {"column": "close", "from_date": date(2024, 1, 1), "latest_bhavcopy": date(2024, 1, 3)}


def _matrix(*rows: tuple[date, float]) -> pd.DataFrame:
    frame = pd.DataFrame({"RELIANCE": [v for _, v in rows]}, index=[d for d, _ in rows])
    frame.index = list(frame.index)  # object index of datetime.date, like _as_matrix
    frame.index.name = "Date"
    return frame


def _bhav(root: Path, day: date, close: float) -> None:
    write_staged(
        root,
        BHAVCOPY,
        day,
        f"SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,TOTTRDQTY\nRELIANCE,EQ,{close},{close},{close},{close},100\n",
    )


def _bonus_on(root: Path, ex_day: date) -> None:
    ca = staged_path(root, CORPORATE_ACTIONS, ex_day)
    ca.parent.mkdir(parents=True, exist_ok=True)
    ca.write_text(f'[{{"symbol":"RELIANCE","subject":"Bonus 1:1","exDate":"{ex_day.isoformat()}"}}]', encoding="utf-8")


def test_cache_roundtrips_and_treats_corruption_as_miss(tmp_path: Path) -> None:
    cache = WideFrameCache(tmp_path)
    frame = _matrix((date(2024, 1, 2), 1.0), (date(2024, 1, 3), 2.0))

    got = cache.frame(_PARTS, lambda: frame)
    assert_frame_equal(got, frame)
    # a stored frame is returned without recomputing
    assert_frame_equal(cache.frame(_PARTS, lambda: (_ for _ in ()).throw(AssertionError("recomputed"))), frame)

    # a different key is a miss
    other = _matrix((date(2024, 1, 2), 9.0))
    assert_frame_equal(cache.frame({**_PARTS, "column": "volume"}, lambda: other), other)

    # a truncated / foreign file is a miss, then overwritten
    path = cache._path(_PARTS)
    path.write_bytes(b"not a parquet file")
    rebuilt = _matrix((date(2024, 1, 2), 3.0))
    assert_frame_equal(cache.frame(_PARTS, lambda: rebuilt), rebuilt)
    assert_frame_equal(cache.get(_PARTS), rebuilt)


def test_wide_frame_adjusted_cache_hit_and_bhavcopy_invalidation(tmp_path: Path) -> None:
    root, cache_dir = tmp_path / "arc", tmp_path / "cache"
    day_before, ex_day = date(2024, 8, 1), date(2024, 8, 2)
    _bhav(root, day_before, 200.0)
    _bhav(root, ex_day, 100.0)
    _bonus_on(root, ex_day)

    data = NSEData(root, cache_dir=cache_dir)
    cold = data.wide_frame(column="close", from_date=day_before, to_date=ex_day, adjusted=True)
    assert cold.loc[day_before, "RELIANCE"] == 100.0  # halved by the 1:1 bonus factor

    # the result is on disk and equal to an uncached recompute
    (pkl,) = (cache_dir / "wide_frame").glob("*.parquet")
    uncached = NSEData(root).wide_frame(column="close", from_date=day_before, to_date=ex_day, adjusted=True)
    assert_frame_equal(cold, uncached)

    # overwrite the cache file with a sentinel -> proves the read path is used
    sentinel = _matrix((day_before, -1.0), (ex_day, -2.0))
    sentinel.to_parquet(pkl)
    served = data.wide_frame(column="close", from_date=day_before, to_date=ex_day, adjusted=True)
    assert served["RELIANCE"].tolist() == [-1.0, -2.0]

    # staging a newer bhavcopy day moves latest_bhavcopy_date -> new key -> recompute (not the sentinel)
    _bhav(root, date(2024, 8, 5), 90.0)
    fresh = NSEData(root, cache_dir=cache_dir).wide_frame(
        column="close", from_date=day_before, to_date=ex_day, adjusted=True
    )
    assert fresh.loc[day_before, "RELIANCE"] == 100.0

    # cache=False bypasses the cache entirely
    bypass = data.wide_frame(column="close", from_date=day_before, to_date=ex_day, adjusted=True, cache=False)
    assert bypass.loc[day_before, "RELIANCE"] == 100.0


def test_wide_frames_shares_cache_entries_with_wide_frame(tmp_path: Path) -> None:
    root, cache_dir = tmp_path / "arc", tmp_path / "cache"
    _bhav(root, date(2024, 8, 1), 200.0)
    _bhav(root, date(2024, 8, 2), 100.0)
    _bonus_on(root, date(2024, 8, 2))
    data = NSEData(root, cache_dir=cache_dir)

    one = data.wide_frame(column="close", from_date=date(2024, 8, 1), to_date=date(2024, 8, 2), adjusted=True)
    panel = data.wide_frames(
        columns=["close", "volume"], from_date=date(2024, 8, 1), to_date=date(2024, 8, 2), adjusted=True
    )
    assert_frame_equal(panel["close"], one)  # close came straight from the entry wide_frame wrote
    assert len(list((cache_dir / "wide_frame").glob("*.parquet"))) == 2  # close + volume, close not duplicated


def test_no_cache_dir_keeps_current_behaviour(tmp_path: Path) -> None:
    _bhav(tmp_path, date(2024, 1, 2), 10.0)
    data = NSEData(tmp_path)  # no cache_dir
    frame = data.wide_frame(column="close", from_date=date(2024, 1, 2), to_date=date(2024, 1, 2), adjusted=True)
    assert frame.loc[date(2024, 1, 2), "RELIANCE"] == 10.0
    assert not (tmp_path / "wide_frame").exists()
