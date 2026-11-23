"""The loader: what it accepts, how it reads time, and what it says when it refuses."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from conftest import WriteCsv
from coroner.trades import TradeLogError, load_trades

GOOD = [
    ["2025-01-02T10:00:00", "2025-01-02T10:30:00", "12.00", "10.00"],
    ["2025-01-03T11:00:00", "2025-01-03T11:05:00", "-3.00", "-5.00"],
]


def test_loads_a_plain_file(write_csv: WriteCsv) -> None:
    log = load_trades(write_csv(GOOD))
    assert len(log) == 2
    assert log.net.tolist() == [10.0, -5.0] and log.gross.tolist() == [12.0, -3.0]
    assert log.hold_minutes.tolist() == [30.0, 5.0]
    assert log.symbol is None and log.side is None and log.size is None
    assert "used as written" in log.clock


def test_sorts_by_exit_time(write_csv: WriteCsv) -> None:
    rows = [
        ["2025-01-02T10:00:00", "2025-01-02T15:00:00", "1", "1"],  # exits last
        ["2025-01-02T11:00:00", "2025-01-02T11:05:00", "2", "2"],
        ["2025-01-02T09:00:00", "2025-01-02T11:05:00", "3", "3"],  # same exit, earlier entry
    ]
    assert load_trades(write_csv(rows)).net.tolist() == [3.0, 2.0, 1.0]


def test_header_case_spaces_extra_columns_and_thousands(write_csv: WriteCsv) -> None:
    rows = [
        ["2025-01-02 10:00:00", "2025-01-02 10:30:00", '"1,234.50"', "1200", "note"],
        ["2025-01-03 11:00:00", "2025-01-03 11:05:00", "-3", "-5", ""],
    ]
    log = load_trades(write_csv(rows, header=[" Entry_Time", "EXIT_TIME ", "Gross", "net", "memo"]))
    assert log.gross.tolist() == [1234.5, -3.0]


def test_aware_timestamps_keep_wall_clock_across_dst(write_csv: WriteCsv) -> None:
    # New York: -05:00 in January, -04:00 in July. Both trades enter at 09:30 local.
    rows = [
        ["2025-01-02T09:30:00-05:00", "2025-01-02T09:40:00-05:00", "1", "1"],
        ["2025-07-02T09:30:00-04:00", "2025-07-02T09:45:00-04:00", "1", "1"],
    ]
    log = load_trades(write_csv(rows))
    assert [str(x)[11:16] for x in log.entry_local] == ["09:30", "09:30"]
    # the instants are UTC: 14:30 and 13:30
    assert [str(x)[11:16] for x in log.entry] == ["14:30", "13:30"]
    assert log.hold_minutes.tolist() == [10.0, 15.0]


def test_tz_option_converts_aware_timestamps(write_csv: WriteCsv) -> None:
    rows = [
        ["2025-01-02T14:30:00Z", "2025-01-02T14:40:00Z", "1", "1"],
        ["2025-07-02T13:30:00+00:00", "2025-07-02T13:45:00+00:00", "1", "1"],
    ]
    path = write_csv(rows)
    assert [str(x)[11:16] for x in load_trades(path).entry_local] == ["14:30", "13:30"]
    log = load_trades(path, tz="America/New_York")
    assert [str(x)[11:16] for x in log.entry_local] == ["09:30", "09:30"]
    assert "America/New_York" in log.clock


def test_hold_time_uses_instants_not_wall_clock(write_csv: WriteCsv) -> None:
    # Clocks went back at 02:00 on 2025-11-02 in New York. 01:30 EDT to 01:30 EST is an hour.
    rows = [
        ["2025-11-02T01:30:00-04:00", "2025-11-02T01:30:00-05:00", "1", "1"],
        ["2025-11-03T10:00:00-05:00", "2025-11-03T10:01:00-05:00", "1", "1"],
    ]
    assert load_trades(write_csv(rows)).hold_minutes.tolist() == [60.0, 1.0]


def test_optional_columns(write_csv: WriteCsv) -> None:
    header = ["entry_time", "exit_time", "gross", "net", "symbol", "side", "size"]
    rows = [[*GOOD[0], "ES", "Buy", "2"], [*GOOD[1], "NQ", "short", "1.5"]]
    log = load_trades(write_csv(rows, header=header))
    assert log.symbol == ("ES", "NQ") and log.side == ("long", "short")
    assert log.size is not None and log.size.tolist() == [2.0, 1.5]


def expect_error(path: Path, *fragments: str, tz: str | None = None) -> None:
    with pytest.raises(TradeLogError) as info:
        load_trades(path, tz=tz)
    for fragment in fragments:
        assert fragment in str(info.value)


def test_missing_file(tmp_path: Path) -> None:
    expect_error(tmp_path / "nope.csv", "no such file")


def test_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "empty.csv"
    path.write_text("", encoding="utf-8")
    expect_error(path, "empty")


def test_missing_columns_are_named(write_csv: WriteCsv) -> None:
    path = write_csv([["2025-01-02T10:00:00", "5"]], header=["entry_time", "pnl"])
    expect_error(
        path, "missing required column(s): exit_time, gross, net", "Found: entry_time, pnl"
    )


def test_duplicate_columns(write_csv: WriteCsv) -> None:
    header = ["entry_time", "exit_time", "gross", "net", "Net"]
    expect_error(write_csv([[*GOOD[0], "1"]], header=header), "duplicate column(s): net")


def test_too_few_trades(write_csv: WriteCsv) -> None:
    expect_error(write_csv(GOOD[:1]), "1 trade(s) found; at least 2 are needed")


@pytest.mark.parametrize(
    ("column", "value", "fragments"),
    [
        (0, "yesterday", ("row 2", "entry_time 'yesterday'", "ISO 8601")),
        (1, "02/01/2025 10:00", ("row 2", "exit_time", "ISO 8601")),
        (2, "abc", ("row 2", "gross 'abc' is not a number")),
        (3, "nan", ("row 2", "net 'nan' is not a finite number")),
        (3, "inf", ("row 2", "not a finite number")),
        (3, "", ("row 2", "net is empty")),
        (1, "2025-01-03T10:59:59", ("row 2", "is before entry_time")),
    ],
)
def test_bad_cells_name_the_row(
    write_csv: WriteCsv, column: int, value: str, fragments: tuple[str, ...]
) -> None:
    bad = list(GOOD[1])
    bad[column] = value
    expect_error(write_csv([GOOD[0], bad]), *fragments)


def test_mixed_aware_and_naive(write_csv: WriteCsv) -> None:
    rows = [GOOD[0], ["2025-01-03T11:00:00-05:00", "2025-01-03T11:05:00-05:00", "1", "1"]]
    expect_error(write_csv(rows), "row 2", "mix values with and without a UTC offset")


def test_tz_with_naive_timestamps(write_csv: WriteCsv) -> None:
    expect_error(write_csv(GOOD), "carry no UTC offset", tz="America/New_York")


def test_unknown_tz(write_csv: WriteCsv) -> None:
    expect_error(write_csv(GOOD), "unknown timezone 'Mars/Olympus'", tz="Mars/Olympus")


@pytest.mark.parametrize(
    ("side", "size", "fragments"),
    [
        ("sideways", "1", ("row 2", "side 'sideways'")),
        ("long", "0", ("row 2", "size '0' is not positive")),
        ("long", "-2", ("row 2", "not positive")),
        ("long", "", ("row 2", "size is empty")),
    ],
)
def test_bad_optional_cells(
    write_csv: WriteCsv, side: str, size: str, fragments: tuple[str, ...]
) -> None:
    header = ["entry_time", "exit_time", "gross", "net", "side", "size"]
    rows = [[*GOOD[0], "long", "1"], [*GOOD[1], side, size]]
    expect_error(write_csv(rows, header=header), *fragments)


def test_arrays_are_float64_and_microsecond(write_csv: WriteCsv) -> None:
    log = load_trades(write_csv(GOOD))
    assert log.net.dtype == np.float64 and log.entry.dtype == np.dtype("datetime64[us]")
