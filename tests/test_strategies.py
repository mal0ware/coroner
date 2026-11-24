"""The public-data strategies that produce the real trade logs."""

from __future__ import annotations

import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from coroner import strategies
from coroner.trades import load_trades

FRENCH = """This file was created by a test.

,A,B
20200102,   1.00,  -2.00
20200103,   0.50,   0.00
20200106,  -1.00,   3.00

Copyright line
"""


def test_parse_french_csv_reads_the_first_table_in_decimals() -> None:
    frame = strategies.parse_french_csv(FRENCH)
    assert list(frame.columns) == ["A", "B"]
    assert [f"{d:%Y-%m-%d}" for d in frame.index] == ["2020-01-02", "2020-01-03", "2020-01-06"]
    assert frame["A"].tolist() == pytest.approx([0.01, 0.005, -0.01])
    assert frame["B"].tolist() == pytest.approx([-0.02, 0.0, 0.03])


def test_parse_french_csv_stops_at_the_second_table_and_rejects_missing_codes() -> None:
    two = FRENCH.replace("Copyright line", "  Equal weighted\n,A,B\n20200107, 9.0, 9.0")
    assert len(strategies.parse_french_csv(two)) == 3
    with pytest.raises(ValueError, match="missing"):
        strategies.parse_french_csv(FRENCH.replace("0.50", "-99.99"))
    with pytest.raises(ValueError, match="header"):
        strategies.parse_french_csv("no table here\n")


def test_read_french_zip(tmp_path: Path) -> None:
    path = tmp_path / "x.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("x.csv", FRENCH)
    assert strategies.read_french_zip(path).shape == (3, 2)


def test_ma_position_by_hand() -> None:
    # index levels 1.1, 1.1, 0.99, 1.089 (returns +10%, 0, -10%, +10%)
    # window 2: sma from day 1 is 1.1, 1.045, 1.0395
    # signal at close: day1 1.1 > 1.1 no, day2 0.99 > 1.045 no, day3 1.089 > 1.0395 yes
    returns = np.asarray([0.1, 0.0, -0.1, 0.1, 0.0])
    # level day4 1.089 vs sma (1.089 + 1.089) / 2: not above
    assert strategies.ma_position(returns, 2).tolist() == [0, 0, 0, 0, 1]


def test_ma_position_never_uses_the_same_day() -> None:
    rng = np.random.default_rng(1)
    returns = rng.normal(0.0, 0.01, size=300)
    base = strategies.ma_position(returns, 20)
    changed = returns.copy()
    changed[150] = 0.5  # a jump on day 150 cannot change the position held over day 150
    assert strategies.ma_position(changed, 20)[:151].tolist() == base[:151].tolist()


def test_runs_to_trades_by_hand() -> None:
    dates = pd.DatetimeIndex(pd.date_range("2020-01-01", periods=6, freq="D"))
    returns = np.asarray([0.0, 0.1, 0.1, 0.0, -0.5, 0.2])
    position = np.asarray([0, 1, 1, 0, -1, -1])
    long, short = strategies.runs_to_trades(dates, returns, position, 1000.0, "X")
    # long over days 1-2: 1.1 x 1.1 - 1 = 0.21 -> 210.00, cost 1.00
    assert (long.entry, long.exit) == (dates[0], dates[2])
    assert (long.gross, long.net, long.side) == (210.0, 209.0, "long")
    # short over days 4-5: 0.5 x 1.2 - 1 = -0.4 -> short gains 400.00, open at the end
    assert (short.entry, short.exit) == (dates[3], dates[5])
    assert (short.gross, short.net, short.side) == (400.0, 399.0, "short")
    with pytest.raises(ValueError):
        strategies.runs_to_trades(dates, returns, np.ones(6, dtype=np.int64), 1.0, "X")


def test_reversal_buys_the_worst_recent_column() -> None:
    dates = pd.date_range("2020-01-01", periods=7, freq="D")
    frame = pd.DataFrame(
        {"A": [0.0, -0.1, 0.0, 0.1, 0.0, 0.0, 0.0], "B": [0.0, 0.0, 0.0, 0.0, 0.2, -0.1, 0.0]},
        index=dates,
    )
    trades = strategies.reversal_trades(frame, lookback=2, hold=2, notional=100.0)
    # close 1: A -10%, B 0 -> buy A over days 2-3: 1.0 x 1.1 - 1 = 10.00
    # close 3: A +10%, B 0 -> buy B over days 4-5: 1.2 x 0.9 - 1 = 8.00
    # close 5: A 0, B +8% -> buy A over day 6 only, the data end: 0.00
    assert [(t.symbol, t.gross, t.net) for t in trades] == [
        ("A", 10.0, 9.9),
        ("B", 8.0, 7.9),
        ("A", 0.0, -0.1),
    ]
    assert (trades[0].entry, trades[0].exit) == (dates[1], dates[3])
    assert trades[-1].exit == dates[6]


def test_written_log_loads(tmp_path: Path) -> None:
    dates = pd.DatetimeIndex(pd.date_range("2020-01-01", periods=4, freq="D"))
    trades = strategies.runs_to_trades(
        dates, np.asarray([0.0, 0.1, 0.0, 0.2]), np.asarray([0, 1, 0, 1]), 100.0, "X"
    )
    path = tmp_path / "log.csv"
    strategies.write_log(trades, path)
    log = load_trades(path)
    assert len(log) == 2 and log.net.tolist() == [9.9, 19.9] and log.symbol == ("X", "X")
