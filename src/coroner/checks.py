"""The checks, as pure functions of arrays.

Nothing here reads files, draws charts or knows about the report. Each function
takes numbers and returns numbers, so each can be tested by hand arithmetic.
Formulas and their sources are listed in ``PAPER.md``.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.int64]
TimeArray = npt.NDArray[np.datetime64]

WEEKDAYS: tuple[str, ...] = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)

_NAN = float("nan")


# --------------------------------------------------------------------------
# 1. Per-trade mean, standard deviation, t-statistic
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class TradeStats:
    """Count, total, mean, sample standard deviation and t-statistic."""

    n: int
    total: float
    mean: float
    sd: float
    t_stat: float


def trade_stats(values: FloatArray) -> TradeStats:
    """Per-trade statistics.

    ``sd`` uses the n - 1 divisor. ``t_stat`` is ``mean / sd * sqrt(n)``. With
    fewer than two trades, or when every trade is identical (sd of zero), the
    quantities that cannot be computed are NaN.
    """
    n = int(values.shape[0])
    if n == 0:
        return TradeStats(0, 0.0, _NAN, _NAN, _NAN)
    total = float(values.sum())
    mean = total / n
    if n < 2:
        return TradeStats(n, total, mean, _NAN, _NAN)
    sd = float(values.std(ddof=1))
    t_stat = mean / sd * math.sqrt(n) if sd > 0 else _NAN
    return TradeStats(n, total, mean, sd, t_stat)


# --------------------------------------------------------------------------
# 2. Label-shuffle permutation test
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class PermutationResult:
    """Outcome of a label-shuffle test."""

    statistic: float
    p_value: float
    n_draws: int
    n_groups: int


def between_group_ss(values: FloatArray, codes: IntArray, n_codes: int) -> float:
    """Between-group sum of squares: sum over groups of n_g * (mean_g - mean)^2."""
    counts = np.bincount(codes, minlength=n_codes).astype(np.float64)
    sums = np.bincount(codes, weights=values, minlength=n_codes)
    used = counts > 0
    grand = float(values.mean())
    means = sums[used] / counts[used]
    return float(np.sum(counts[used] * (means - grand) ** 2))


def permutation_test(
    values: FloatArray, codes: IntArray, n_draws: int = 2000, seed: int = 0
) -> PermutationResult:
    """Do the labels say anything about the results?

    The statistic is the between-group sum of squares of ``values`` grouped by
    ``codes`` (non-negative integers). The labels are shuffled ``n_draws`` times
    and the statistic recomputed. The p-value is
    ``(1 + number of shuffles with statistic >= observed) / (1 + n_draws)``.
    A small p-value means results differ across labels more than chance gives.
    With fewer than two groups the p-value is NaN.
    """
    if values.shape[0] != codes.shape[0]:
        raise ValueError("values and codes differ in length")
    n_codes = int(codes.max()) + 1 if codes.size else 0
    n_groups = int(np.unique(codes).size)
    if n_groups < 2:
        return PermutationResult(_NAN, _NAN, n_draws, n_groups)
    observed = between_group_ss(values, codes, n_codes)
    rng = np.random.default_rng(seed)
    # A tolerance keeps ties (e.g. a shuffle that reproduces the data) on the >= side.
    threshold = observed - 1e-9 * max(1.0, abs(observed))
    at_least = 0
    for _ in range(n_draws):
        shuffled = rng.permutation(values)
        if between_group_ss(shuffled, codes, n_codes) >= threshold:
            at_least += 1
    return PermutationResult(observed, (1 + at_least) / (1 + n_draws), n_draws, n_groups)


# --------------------------------------------------------------------------
# 3. First half against second half
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class HalfSplit:
    """Statistics of the earlier and later half of the trades."""

    first: TradeStats
    second: TradeStats


def half_split(values: FloatArray) -> HalfSplit:
    """Split time-ordered ``values`` by count: the first ``n // 2`` and the rest."""
    k = int(values.shape[0]) // 2
    return HalfSplit(trade_stats(values[:k]), trade_stats(values[k:]))


# --------------------------------------------------------------------------
# 4. Time-of-day and weekday buckets, holding time
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class BucketRow:
    """One time-of-day or weekday bucket."""

    label: str
    n: int
    total: float
    mean: float
    share: float
    win_rate: float
    median_hold_minutes: float
    short_hold: bool


def time_of_day_codes(local: TimeArray, bucket_minutes: int = 60) -> tuple[IntArray, list[str]]:
    """Bucket index of each wall-clock time, and the label of every bucket.

    Buckets start at midnight and are ``bucket_minutes`` wide; the width must
    divide 1440. Labels look like ``09:00-10:00``.
    """
    if bucket_minutes <= 0 or 1440 % bucket_minutes != 0:
        raise ValueError("bucket_minutes must be a positive divisor of 1440")
    midnight = local.astype("datetime64[D]")
    minutes = ((local - midnight) / np.timedelta64(1, "m")).astype(np.int64)
    codes = (minutes // bucket_minutes).astype(np.int64)
    labels = []
    for start in range(0, 1440, bucket_minutes):
        end = start + bucket_minutes
        labels.append(f"{start // 60:02d}:{start % 60:02d}-{end // 60:02d}:{end % 60:02d}")
    return codes, labels


def weekday_codes(local: TimeArray) -> IntArray:
    """Weekday of each wall-clock time, Monday = 0 ... Sunday = 6."""
    days = local.astype("datetime64[D]").astype(np.int64)
    return ((days + 3) % 7).astype(np.int64)  # 1970-01-01 was a Thursday


def bucket_table(
    values: FloatArray,
    hold_minutes: FloatArray,
    codes: IntArray,
    labels: Sequence[str],
    short_hold_minutes: float = 5.0,
    min_trades: int = 20,
) -> list[BucketRow]:
    """Profit and median holding time per bucket, for buckets that have trades.

    ``share`` is the bucket total over the overall total, NaN when the overall
    total is not positive. ``short_hold`` is set when the bucket's median hold
    is below ``short_hold_minutes`` and it has at least ``min_trades`` trades.
    """
    overall = float(values.sum())
    rows: list[BucketRow] = []
    for code in np.unique(codes):
        mask = codes == code
        bucket = values[mask]
        n = int(bucket.shape[0])
        total = float(bucket.sum())
        median_hold = float(np.median(hold_minutes[mask]))
        rows.append(
            BucketRow(
                label=labels[int(code)],
                n=n,
                total=total,
                mean=total / n,
                share=total / overall if overall > 0 else _NAN,
                win_rate=float(np.mean(bucket > 0)),
                median_hold_minutes=median_hold,
                short_hold=median_hold < short_hold_minutes and n >= min_trades,
            )
        )
    return rows


# --------------------------------------------------------------------------
# 5. Leave out the best trades
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class LeaveOut:
    """The result with the ``removed`` best trades taken out."""

    removed: int
    removed_total: float
    share: float
    rest: TradeStats


def five_percent_count(n: int) -> int:
    """Number of trades in the best 5%: ``ceil(0.05 * n)``."""
    return math.ceil(n / 20)


def leave_out_best(values: FloatArray, k: int) -> LeaveOut:
    """Statistics of the trades left after removing the ``k`` largest.

    ``share`` is the sum of the removed trades over the total of all trades,
    NaN when that total is not positive. ``k`` is capped at the trade count.
    """
    if k < 0:
        raise ValueError("k must not be negative")
    n = int(values.shape[0])
    k = min(k, n)
    ordered = np.sort(values)[::-1]
    removed_total = float(ordered[:k].sum())
    total = float(values.sum())
    share = removed_total / total if total > 0 else _NAN
    return LeaveOut(k, removed_total, share, trade_stats(ordered[k:]))


def trades_to_zero(values: FloatArray) -> int:
    """Smallest number of best trades whose removal leaves a total <= 0.

    Zero when the total is already <= 0. At most the number of winning trades.
    """
    remaining = float(values.sum())
    if remaining <= 0:
        return 0
    ordered = np.sort(values)[::-1]
    totals = remaining - np.cumsum(ordered)
    # Guard against a last-digit residue when every trade is removed.
    totals[-1] = min(totals[-1], 0.0) if np.all(ordered >= 0) else totals[-1]
    hits = np.flatnonzero(totals <= 1e-9 * max(1.0, abs(remaining)))
    return int(hits[0]) + 1


# --------------------------------------------------------------------------
# 6. Cost share
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class CostShare:
    """Total cost and its share of the gross result."""

    gross_total: float
    net_total: float
    cost_total: float
    share: float | None


def cost_share(gross: FloatArray, net: FloatArray) -> CostShare:
    """Total cost (gross minus net) divided by total gross result.

    ``share`` is ``None`` when the gross total is zero or negative: there is no
    gross profit for costs to be a share of.
    """
    gross_total = float(gross.sum())
    net_total = float(net.sum())
    cost_total = gross_total - net_total
    share = cost_total / gross_total if gross_total > 0 else None
    return CostShare(gross_total, net_total, cost_total, share)


# --------------------------------------------------------------------------
# 7. Drawdown measures
# --------------------------------------------------------------------------


def drawdown_pct(equity: FloatArray) -> FloatArray:
    """Percentage drawdown from the running maximum, as positive numbers.

    ``100 * (running_max - equity) / running_max``. The first value must be
    positive; it is the starting equity.
    """
    if equity.shape[0] == 0 or equity[0] <= 0:
        raise ValueError("equity must start with a positive value")
    peak = np.maximum.accumulate(equity)
    return np.asarray(100.0 * (peak - equity) / peak, dtype=np.float64)


def ulcer_index(equity: FloatArray) -> float:
    """Ulcer index (Martin): sqrt of the mean squared percentage drawdown."""
    dd = drawdown_pct(equity)
    return float(np.sqrt(np.mean(dd**2)))


def max_drawdown(equity: FloatArray) -> tuple[float, float]:
    """Largest drop from a running maximum, as (currency amount, percent)."""
    peak = np.maximum.accumulate(equity)
    return float(np.max(peak - equity)), float(np.max(drawdown_pct(equity)))


def longest_underwater(times: TimeArray, equity: FloatArray) -> tuple[np.timedelta64, bool]:
    """Longest time between a peak and the first return to it.

    Returns ``(duration, recovered)``. A spell still open at the last
    observation is measured to that observation and has ``recovered`` False.
    Zero duration when equity never falls below a previous peak.
    """
    if times.shape[0] != equity.shape[0]:
        raise ValueError("times and equity differ in length")
    longest = np.timedelta64(0, "us")
    longest_recovered = True
    peak = equity[0]
    peak_time = times[0]
    under = False
    for t, e in zip(times[1:], equity[1:], strict=True):
        if e >= peak:
            if under and t - peak_time > longest:
                longest = (t - peak_time).astype("timedelta64[us]")
                longest_recovered = True
            peak, peak_time, under = e, t, False
        else:
            under = True
    if under and times[-1] - peak_time > longest:
        longest = (times[-1] - peak_time).astype("timedelta64[us]")
        longest_recovered = False
    return longest, longest_recovered


def annualised_return_pct(start: float, end: float, days: float) -> float:
    """Compound annual return in percent over ``days`` days of 365.25 per year.

    NaN when the span is zero or the ending equity is not positive.
    """
    if days <= 0 or start <= 0 or end <= 0:
        return _NAN
    return float(100.0 * ((end / start) ** (365.25 / days) - 1.0))


def martin_ratio(annual_return_pct: float, ulcer: float, risk_free_pct: float = 0.0) -> float:
    """Martin ratio: annual return over the risk-free rate, divided by the ulcer index.

    NaN when the ulcer index is zero (no drawdown to divide by).
    """
    if not ulcer > 0:
        return _NAN
    return (annual_return_pct - risk_free_pct) / ulcer


def recovery_factor(net_profit: float, max_drawdown_amount: float) -> float:
    """Net profit over maximum drawdown, both in currency. NaN with no drawdown."""
    if not max_drawdown_amount > 0:
        return _NAN
    return net_profit / max_drawdown_amount


def daily_equity(
    exit_local: TimeArray, net: FloatArray, capital: float
) -> tuple[TimeArray, FloatArray]:
    """End-of-day equity for every calendar day from the first exit to the last.

    The series starts with ``capital`` dated the day before the first exit. Days
    with no closed trade carry the previous value.
    """
    days = exit_local.astype("datetime64[D]")
    first, last = days.min(), days.max()
    span = int((last - first) / np.timedelta64(1, "D")) + 1
    offsets = ((days - first) / np.timedelta64(1, "D")).astype(np.int64)
    per_day = np.bincount(offsets, weights=net, minlength=span)
    equity = np.concatenate(([capital], capital + np.cumsum(per_day)))
    dates = first + np.arange(-1, span).astype("timedelta64[D]")
    return dates, np.asarray(equity, dtype=np.float64)


# --------------------------------------------------------------------------
# 8. Share of positive days, months and quarters
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class PeriodShare:
    """How many periods with at least one closed trade ended positive."""

    name: str
    positive: int
    total: int

    @property
    def share(self) -> float:
        return self.positive / self.total if self.total else _NAN


def period_keys(local: TimeArray, period: str) -> IntArray:
    """Integer key of the calendar day, month or quarter of each timestamp."""
    if period == "day":
        return local.astype("datetime64[D]").astype(np.int64)
    months = local.astype("datetime64[M]").astype(np.int64)
    if period == "month":
        return months
    if period == "quarter":
        return np.asarray(months // 3, dtype=np.int64)
    raise ValueError(f"unknown period {period!r}")


def positive_share(keys: IntArray, values: FloatArray, name: str) -> PeriodShare:
    """Count periods whose summed result is above zero.

    Only periods that contain at least one trade are counted.
    """
    _, inverse = np.unique(keys, return_inverse=True)
    sums = np.bincount(inverse, weights=values)
    return PeriodShare(name, int(np.sum(sums > 0)), int(sums.shape[0]))
