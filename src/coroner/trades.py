"""Reading and validating a trade log.

The input is a CSV with one row per closed trade.

Required columns
    entry_time  ISO 8601 timestamp, e.g. ``2025-03-10T09:31:00-04:00``
    exit_time   ISO 8601 timestamp, not before ``entry_time``
    gross       result of the trade before costs, in account currency
    net         result of the trade after costs, in account currency

Optional columns
    symbol      free text
    side        ``long`` or ``short`` (``buy`` and ``sell`` are accepted)
    size        positive number

Other columns are ignored. Column names are matched after stripping spaces and
lower-casing. Timestamps must either all carry a UTC offset or all carry none.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import numpy as np
import numpy.typing as npt
import pandas as pd

FloatArray = npt.NDArray[np.float64]
TimeArray = npt.NDArray[np.datetime64]

REQUIRED_COLUMNS: tuple[str, ...] = ("entry_time", "exit_time", "gross", "net")
OPTIONAL_COLUMNS: tuple[str, ...] = ("symbol", "side", "size")
_SIDES = {"long": "long", "buy": "long", "short": "short", "sell": "short"}


class TradeLogError(ValueError):
    """The trade log cannot be used. The message says which row and why."""


@dataclass(frozen=True)
class TradeLog:
    """Validated trades, sorted by exit time (then entry time, then file order).

    ``entry`` and ``exit`` are instants: UTC when the file carried offsets,
    otherwise the times as written. ``entry_local`` and ``exit_local`` are the
    wall-clock times used for time-of-day, weekday and calendar buckets.
    """

    entry: TimeArray
    exit: TimeArray
    entry_local: TimeArray
    exit_local: TimeArray
    gross: FloatArray
    net: FloatArray
    symbol: tuple[str, ...] | None
    side: tuple[str, ...] | None
    size: FloatArray | None
    clock: str

    def __len__(self) -> int:
        return int(self.net.shape[0])

    @property
    def hold_minutes(self) -> FloatArray:
        """Holding time of each trade in minutes."""
        seconds = (self.exit - self.entry) / np.timedelta64(1, "s")
        return np.asarray(seconds, dtype=np.float64) / 60.0


def _parse_time(text: str, row: int, column: str) -> datetime:
    try:
        return datetime.fromisoformat(text.strip())
    except ValueError:
        raise TradeLogError(
            f"row {row}: {column} {text!r} is not an ISO 8601 timestamp "
            "(expected e.g. 2025-03-10T09:31:00-04:00)"
        ) from None


def _parse_number(text: str, row: int, column: str) -> float:
    try:
        value = float(text.strip().replace(",", ""))
    except ValueError:
        raise TradeLogError(f"row {row}: {column} {text!r} is not a number") from None
    if not math.isfinite(value):
        raise TradeLogError(f"row {row}: {column} {text!r} is not a finite number")
    return value


def _to_datetime64(values: list[datetime]) -> TimeArray:
    return np.array([np.datetime64(v, "us") for v in values], dtype="datetime64[us]")


def load_trades(path: str | Path, tz: str | None = None) -> TradeLog:
    """Read ``path`` and return a validated :class:`TradeLog`.

    ``tz`` is an IANA zone name such as ``America/New_York``. When given,
    timezone-aware timestamps are converted to that zone before time-of-day,
    weekday and calendar buckets are formed. Without it the wall-clock time is
    taken as written in the file. ``tz`` is an error for files without offsets.

    Raises :class:`TradeLogError` with the offending row (1 is the first data
    row) when the file cannot be used.
    """
    path = Path(path)
    if not path.is_file():
        raise TradeLogError(f"{path}: no such file")
    try:
        frame = pd.read_csv(path, dtype=str, keep_default_na=False, skipinitialspace=True)
    except pd.errors.EmptyDataError:
        raise TradeLogError(f"{path}: the file is empty") from None
    except (pd.errors.ParserError, UnicodeDecodeError) as exc:
        raise TradeLogError(f"{path}: not a readable CSV ({exc})") from None

    names = [str(c).strip().lower() for c in frame.columns]
    duplicated = sorted({c for c in names if names.count(c) > 1})
    if duplicated:
        raise TradeLogError(f"{path}: duplicate column(s): {', '.join(duplicated)}")
    missing = [c for c in REQUIRED_COLUMNS if c not in names]
    if missing:
        raise TradeLogError(
            f"{path}: missing required column(s): {', '.join(missing)}. "
            f"Required: {', '.join(REQUIRED_COLUMNS)}. Found: {', '.join(names)}"
        )
    n = len(frame)
    if n < 2:
        raise TradeLogError(f"{path}: {n} trade(s) found; at least 2 are needed")

    zone: ZoneInfo | None = None
    if tz is not None:
        try:
            zone = ZoneInfo(tz)
        except (ZoneInfoNotFoundError, ValueError):
            raise TradeLogError(
                f"unknown timezone {tz!r} (expected e.g. America/New_York)"
            ) from None

    columns: dict[str, list[str]] = {
        name: [str(v) for v in frame.iloc[:, j].tolist()] for j, name in enumerate(names)
    }
    entries: list[datetime] = []
    exits: list[datetime] = []
    gross: list[float] = []
    net: list[float] = []
    for i in range(n):
        row = i + 1
        for column in REQUIRED_COLUMNS:
            if columns[column][i].strip() == "":
                raise TradeLogError(f"row {row}: {column} is empty")
        entries.append(_parse_time(columns["entry_time"][i], row, "entry_time"))
        exits.append(_parse_time(columns["exit_time"][i], row, "exit_time"))
        gross.append(_parse_number(columns["gross"][i], row, "gross"))
        net.append(_parse_number(columns["net"][i], row, "net"))

    aware = [t.tzinfo is not None for t in entries + exits]
    if any(aware) and not all(aware):
        odd = aware.index(not aware[0])
        raise TradeLogError(
            f"row {odd % n + 1}: timestamps mix values with and without a UTC offset; "
            "use one form throughout"
        )
    is_aware = aware[0]
    if not is_aware and zone is not None:
        raise TradeLogError(
            "a timezone was given but the timestamps carry no UTC offset; "
            "drop --tz and they are used as written"
        )

    if is_aware:
        entry = _to_datetime64([t.astimezone(UTC).replace(tzinfo=None) for t in entries])
        exit_ = _to_datetime64([t.astimezone(UTC).replace(tzinfo=None) for t in exits])
        if zone is not None:
            entries = [t.astimezone(zone) for t in entries]
            exits = [t.astimezone(zone) for t in exits]
            clock = f"timezone-aware timestamps converted to {tz}"
        else:
            clock = "timezone-aware timestamps, wall-clock time as written in the file"
    else:
        entry = _to_datetime64(entries)
        exit_ = _to_datetime64(exits)
        clock = "timestamps without offset, used as written"
    entry_local = _to_datetime64([t.replace(tzinfo=None) for t in entries])
    exit_local = _to_datetime64([t.replace(tzinfo=None) for t in exits])

    early = np.flatnonzero(exit_ < entry)
    if early.size:
        i = int(early[0])
        raise TradeLogError(
            f"row {i + 1}: exit_time {columns['exit_time'][i]!r} is before "
            f"entry_time {columns['entry_time'][i]!r}"
        )

    symbol: tuple[str, ...] | None = None
    if "symbol" in columns:
        symbol = tuple(s.strip() for s in columns["symbol"])
        for i, s in enumerate(symbol):
            if s == "":
                raise TradeLogError(f"row {i + 1}: symbol is empty")
    side: tuple[str, ...] | None = None
    if "side" in columns:
        sides: list[str] = []
        for i, s in enumerate(columns["side"]):
            key = s.strip().lower()
            if key not in _SIDES:
                raise TradeLogError(f"row {i + 1}: side {s!r} is not one of long, short, buy, sell")
            sides.append(_SIDES[key])
        side = tuple(sides)
    size: FloatArray | None = None
    if "size" in columns:
        sizes: list[float] = []
        for i, s in enumerate(columns["size"]):
            if s.strip() == "":
                raise TradeLogError(f"row {i + 1}: size is empty")
            value = _parse_number(s, i + 1, "size")
            if value <= 0:
                raise TradeLogError(f"row {i + 1}: size {s!r} is not positive")
            sizes.append(value)
        size = np.asarray(sizes, dtype=np.float64)

    order = np.lexsort((np.arange(n), entry, exit_))
    return TradeLog(
        entry=entry[order],
        exit=exit_[order],
        entry_local=entry_local[order],
        exit_local=exit_local[order],
        gross=np.asarray(gross, dtype=np.float64)[order],
        net=np.asarray(net, dtype=np.float64)[order],
        symbol=None if symbol is None else tuple(symbol[i] for i in order),
        side=None if side is None else tuple(side[i] for i in order),
        size=None if size is None else size[order],
        clock=clock,
    )
