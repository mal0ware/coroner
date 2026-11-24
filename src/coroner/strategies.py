"""Trade logs from simple public-data strategies, for running Coroner on real returns.

The input is Ken French's daily return files (see ``scripts/fetch_data.py``).
Three rules, all on daily closes, all chosen for being plain rather than good:

``market_ma200``       The US market (Mkt-RF + RF). Long while the total-return
                       index closed above its 200-day simple moving average on
                       the previous day, flat otherwise. 100,000 per trade.
``industry_ma200``     The same rule on each of the ten value-weighted industry
                       portfolios separately. 10,000 per trade.
``industry_reversal``  Every five trading days, buy the industry with the lowest
                       return over the last five days and hold it for five days.
                       100,000 per trade.

A signal is computed at a close and the position starts with the next day's
return, so the trade enters at the close the signal was computed on. Each trade
is charged a flat cost of 10 basis points of notional for the round trip. No
interest is earned while flat. A position still open on the last day of the
data is closed at that day's close. Trades carry the close date at 16:00 with
no timezone; the files give no intraday times.
"""

from __future__ import annotations

import csv
import hashlib
import io
import zipfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import numpy.typing as npt
import pandas as pd

FloatArray = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.int64]

COST_RATE = 0.001
CLOSE_TIME = "16:00:00"
FACTORS_ZIP = "F-F_Research_Data_Factors_daily_CSV.zip"
INDUSTRY_ZIP = "10_Industry_Portfolios_daily_CSV.zip"
HEADER = ("entry_time", "exit_time", "gross", "net", "symbol", "side")


@dataclass(frozen=True)
class Trade:
    """One closed trade. Times are close dates; amounts are in currency."""

    entry: pd.Timestamp
    exit: pd.Timestamp
    gross: float
    net: float
    symbol: str
    side: str


def parse_french_csv(text: str) -> pd.DataFrame:
    """The first table of a Ken French CSV, as decimal returns indexed by date.

    The table starts at the first line that begins with a comma (the column
    names) and runs while lines start with an eight-digit date. Values are in
    percent in the file and divided by 100 here. Missing-value codes (-99.99,
    -999) raise ``ValueError``.
    """
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith(",")), None)
    if start is None:
        raise ValueError("no header line starting with a comma")
    names = [name.strip() for name in lines[start].split(",")[1:]]
    dates: list[str] = []
    rows: list[list[float]] = []
    for line in lines[start + 1 :]:
        fields = [field.strip() for field in line.split(",")]
        if len(fields[0]) != 8 or not fields[0].isdigit():
            break
        dates.append(fields[0])
        rows.append([float(field) for field in fields[1:]])
    values = np.asarray(rows, dtype=np.float64)
    if values.size == 0:
        raise ValueError("the table has no rows")
    if np.any(values <= -99.99):
        raise ValueError("the table contains missing-value codes")
    index = pd.DatetimeIndex(pd.to_datetime(dates, format="%Y%m%d"), name="date")
    return pd.DataFrame(values / 100.0, index=index, columns=names)


def read_french_zip(path: Path) -> pd.DataFrame:
    """Parse the single CSV inside one of Ken French's zip files."""
    with zipfile.ZipFile(path) as archive:
        (name,) = archive.namelist()
        text = archive.read(name).decode("latin-1")
    return parse_french_csv(text)


def market_returns(factors: pd.DataFrame) -> pd.Series:
    """Daily total return of the US market: Mkt-RF plus RF."""
    return (factors["Mkt-RF"] + factors["RF"]).rename("Market")


def ma_position(returns: FloatArray, window: int) -> IntArray:
    """1 on days held long, 0 on days flat, under the moving-average rule.

    The total-return index is ``cumprod(1 + r)``. The signal at close ``t`` is
    index_t > mean(index_{t-window+1} .. index_t), and it needs ``window``
    closes. The position over day ``t + 1`` is the signal at close ``t``.
    """
    if window < 1:
        raise ValueError("window must be at least 1")
    level = np.cumprod(1.0 + returns)
    sums = np.cumsum(level)
    sma = np.full(level.shape[0], np.nan)
    sma[window - 1 :] = (sums[window - 1 :] - np.concatenate(([0.0], sums[:-window]))) / window
    signal = np.zeros(level.shape[0], dtype=np.int64)
    ready = ~np.isnan(sma)
    signal[ready] = (level[ready] > sma[ready]).astype(np.int64)
    position = np.zeros_like(signal)
    position[1:] = signal[:-1]
    return position


def runs_to_trades(
    dates: pd.DatetimeIndex,
    returns: FloatArray,
    position: IntArray,
    notional: float,
    symbol: str,
    cost_rate: float = COST_RATE,
) -> list[Trade]:
    """One trade per maximal run of days with the same non-zero position.

    A run over days ``k .. m`` enters at the close of day ``k - 1`` and exits at
    the close of day ``m``. Gross is ``side x notional x (prod(1 + r) - 1)``
    over the run; net is gross less ``cost_rate x notional``. A run may not
    start on the first day, since there is no earlier close to enter at.
    """
    if not dates.shape[0] == returns.shape[0] == position.shape[0]:
        raise ValueError("dates, returns and position differ in length")
    if position.shape[0] and position[0] != 0:
        raise ValueError("a position cannot start on the first day")
    trades: list[Trade] = []
    n = position.shape[0]
    k = 0
    while k < n:
        side = int(position[k])
        if side == 0:
            k += 1
            continue
        m = k
        while m + 1 < n and position[m + 1] == side:
            m += 1
        growth = float(np.prod(1.0 + returns[k : m + 1]))
        gross = round(side * notional * (growth - 1.0), 2)
        net = round(gross - cost_rate * notional, 2)
        trades.append(
            Trade(dates[k - 1], dates[m], gross, net, symbol, "long" if side > 0 else "short")
        )
        k = m + 1
    return trades


def reversal_trades(
    returns: pd.DataFrame,
    lookback: int,
    hold: int,
    notional: float,
    cost_rate: float = COST_RATE,
) -> list[Trade]:
    """Every ``hold`` days, buy the column with the lowest ``lookback``-day return.

    The first choice is made at close ``lookback - 1`` (the first close with a
    full lookback) and later ones every ``hold`` closes after it. Each holding
    is its own trade over the next ``hold`` days, or fewer at the end of the
    data. Ties go to the first column.
    """
    if lookback < 1 or hold < 1:
        raise ValueError("lookback and hold must be at least 1")
    values = returns.to_numpy(dtype=np.float64)
    log_growth = np.cumsum(np.log1p(values), axis=0)
    dates = pd.DatetimeIndex(returns.index)
    trades: list[Trade] = []
    t = lookback - 1
    while t + 1 < values.shape[0]:
        before = log_growth[t - lookback] if t >= lookback else np.zeros(values.shape[1])
        pick = int(np.argmin(log_growth[t] - before))
        end = min(t + hold, values.shape[0] - 1)
        growth = float(np.prod(1.0 + values[t + 1 : end + 1, pick]))
        gross = round(notional * (growth - 1.0), 2)
        net = round(gross - cost_rate * notional, 2)
        trades.append(Trade(dates[t], dates[end], gross, net, str(returns.columns[pick]), "long"))
        t += hold
    return trades


def build_logs(data_dir: Path) -> dict[str, list[Trade]]:
    """All three trade logs from the two zip files in ``data_dir``."""
    factors = read_french_zip(data_dir / FACTORS_ZIP)
    industries = read_french_zip(data_dir / INDUSTRY_ZIP)
    market = market_returns(factors)
    market_index = pd.DatetimeIndex(market.index)
    market_values = market.to_numpy(dtype=np.float64)
    logs: dict[str, list[Trade]] = {
        "market_ma200": runs_to_trades(
            market_index, market_values, ma_position(market_values, 200), 100_000.0, "Market"
        )
    }
    industry_index = pd.DatetimeIndex(industries.index)
    per_industry: list[Trade] = []
    for name in industries.columns:
        values = industries[name].to_numpy(dtype=np.float64)
        per_industry += runs_to_trades(
            industry_index, values, ma_position(values, 200), 10_000.0, str(name)
        )
    per_industry.sort(key=lambda trade: (trade.exit, trade.entry, trade.symbol))
    logs["industry_ma200"] = per_industry
    logs["industry_reversal"] = reversal_trades(industries, 5, 5, 100_000.0)
    return logs


def write_log(trades: list[Trade], path: Path) -> None:
    """Write a trade log in the format ``coroner report`` reads, with LF endings."""
    path.parent.mkdir(parents=True, exist_ok=True)
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(HEADER)
    for trade in trades:
        writer.writerow(
            (
                f"{trade.entry:%Y-%m-%d} {CLOSE_TIME}",
                f"{trade.exit:%Y-%m-%d} {CLOSE_TIME}",
                f"{trade.gross:.2f}",
                f"{trade.net:.2f}",
                trade.symbol,
                trade.side,
            )
        )
    path.write_text(buffer.getvalue(), encoding="utf-8", newline="\n")


def data_summary(data_dir: Path) -> list[tuple[str, str, str, str]]:
    """(file, sha256, first date, last date) for each input file."""
    rows = []
    for name in (FACTORS_ZIP, INDUSTRY_ZIP):
        path = data_dir / name
        frame = read_french_zip(path)
        rows.append(
            (
                name,
                hashlib.sha256(path.read_bytes()).hexdigest(),
                f"{frame.index[0]:%Y-%m-%d}",
                f"{frame.index[-1]:%Y-%m-%d}",
            )
        )
    return rows
