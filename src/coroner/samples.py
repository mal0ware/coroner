"""Two synthetic trade logs with the same net total and different causes.

``broad``         400 trades, each a draw from one distribution with a small
                  positive mean. Entries spread over the trading day.
``concentrated``  400 trades. 390 of them are noise that sums to 1% of the
                  profit. Ten large winners carry the other 99%. Sixty trades,
                  the ten winners among them, are entered between 09:30 and
                  10:00 and held for a few minutes.

Both are built to total exactly ``TOTAL`` net. Nothing here is market data:
the dates are the weekdays of 2025 with no holiday calendar, and the amounts
are random numbers. The generator is seeded, so the files never change.
"""

from __future__ import annotations

import csv
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.float64]

SEED = 1989
N_TRADES = 400
TOTAL = 20_000.00
N_BIG = 10
BIG_SHARE = 0.99
N_OPEN = 60
ZONE = ZoneInfo("America/New_York")
OPEN_S = 9 * 3600 + 30 * 60
CLOSE_S = 16 * 3600
HEADER = ("entry_time", "exit_time", "gross", "net")

Row = tuple[str, str, str, str]


def _weekdays(year: int) -> list[date]:
    day = date(year, 1, 2)
    out = []
    while day.year == year:
        if day.weekday() < 5:
            out.append(day)
        day += timedelta(days=1)
    return out


def _to_total(values: FloatArray, total: float) -> FloatArray:
    """Shift ``values`` so that, rounded to cents, they sum to ``total`` exactly."""
    shifted = np.round(values + (total - values.sum()) / values.shape[0], 2)
    cents = round(total * 100) - int(np.round(shifted * 100).sum())
    shifted[0] += cents / 100
    return np.asarray(np.round(shifted, 2), dtype=np.float64)


def _rows(
    rng: np.random.Generator, entry_s: FloatArray, hold_s: FloatArray, net: FloatArray
) -> list[Row]:
    days = _weekdays(2025)
    n = net.shape[0]
    day_index = np.asarray(rng.integers(0, len(days), size=n), dtype=np.int64)
    cost = np.round(rng.uniform(6.0, 14.0, size=n), 2)
    hold_s = np.maximum(20.0, np.minimum(hold_s, CLOSE_S - entry_s))
    rows: list[tuple[datetime, Row]] = []
    for i in range(n):
        midnight = datetime.combine(days[int(day_index[i])], datetime.min.time(), tzinfo=ZONE)
        entry = midnight + timedelta(seconds=int(entry_s[i]))
        exit_ = entry + timedelta(seconds=int(hold_s[i]))
        rows.append(
            (
                entry,
                (
                    entry.isoformat(),
                    exit_.isoformat(),
                    f"{net[i] + cost[i]:.2f}",
                    f"{net[i]:.2f}",
                ),
            )
        )
    rows.sort(key=lambda pair: (pair[0], pair[1]))
    return [row for _, row in rows]


def broad_rows() -> list[Row]:
    """The broad small edge."""
    rng = np.random.default_rng([SEED, 1])
    net = _to_total(rng.normal(50.0, 250.0, size=N_TRADES), TOTAL)
    entry_s = rng.uniform(OPEN_S, CLOSE_S - 1800, size=N_TRADES)
    hold_s = 60.0 * rng.lognormal(np.log(45.0), 0.6, size=N_TRADES)
    return _rows(rng, entry_s, hold_s, net)


def concentrated_rows() -> list[Row]:
    """Ten trades carry nearly everything; one early window holds trades for minutes."""
    rng = np.random.default_rng([SEED, 2])
    big_total = round(BIG_SHARE * TOTAL, 2)
    big = rng.uniform(1200.0, 2800.0, size=N_BIG)
    big = _to_total(big * big_total / big.sum(), big_total)
    rest = _to_total(rng.normal(0.0, 250.0, size=N_TRADES - N_BIG), TOTAL - big_total)
    # The first N_OPEN trades are the opening-window trades; the big ones lead them.
    net = np.concatenate((big, rest))
    n_day = N_TRADES - N_OPEN
    entry_s = np.concatenate(
        (
            rng.uniform(OPEN_S, OPEN_S + 1800, size=N_OPEN),
            rng.uniform(10 * 3600, CLOSE_S - 1800, size=n_day),
        )
    )
    hold_s = 60.0 * np.concatenate(
        (
            rng.lognormal(np.log(3.0), 0.5, size=N_OPEN),
            rng.lognormal(np.log(45.0), 0.6, size=n_day),
        )
    )
    return _rows(rng, entry_s, hold_s, net)


def write_csv(rows: list[Row], path: Path) -> None:
    """Write a sample to ``path`` with a header row and LF line endings."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(HEADER)
        writer.writerows(rows)


def write_samples(directory: Path) -> tuple[Path, Path]:
    """Write ``broad.csv`` and ``concentrated.csv`` into ``directory``."""
    broad = directory / "broad.csv"
    concentrated = directory / "concentrated.csv"
    write_csv(broad_rows(), broad)
    write_csv(concentrated_rows(), concentrated)
    return broad, concentrated
