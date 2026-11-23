"""The plain-language verdict: three to five sentences from fixed rules.

Each rule is one function that returns a sentence or ``None``. The rules, in
the order they are applied:

1. Headline (always). Trade count, net total, mean per trade and t-statistic,
   saying whether the mean is more than two standard errors from zero.
2. Concentration (always). If the log made money: when the best N trades carry
   at least half of the profit, "N trades carry X% of the profit" and what the
   rest made; otherwise the share they carry and how many of the best trades
   must go before the total reaches zero. If the log did not make money, it
   says there is no profit to attribute.
3. Halves (always). What the first and the second half made or lost.
4. Time (only when triggered). If a time-of-day bucket is flagged for a short
   median hold, the flagged bucket with the largest absolute profit is named.
   Failing that, if the time-of-day or weekday permutation test has
   p < 0.01, that is stated.
5. Costs (only when triggered). If costs are at least half of gross profit, or
   gross profit is zero or negative.

Rules 1 to 3 always fire, so the verdict has three to five sentences.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from coroner.analysis import Analysis
from coroner.checks import (
    BucketRow,
    CostShare,
    HalfSplit,
    LeaveOut,
    PermutationResult,
    TradeStats,
)

CONCENTRATION_SHARE = 0.5
PERMUTATION_P = 0.01
COST_SHARE = 0.5
T_THRESHOLD = 2.0

_WORDS = (
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
)


def money(value: float) -> str:
    """``1234.5`` -> ``1,234.50``."""
    text = f"{value:,.2f}"
    return "0.00" if text == "-0.00" else text


def percent(fraction: float) -> str:
    """``0.99`` -> ``99%`` (whole percent)."""
    return f"{100 * fraction:.0f}%"


def count_word(n: int, capital: bool = False) -> str:
    """Numbers up to twelve as words, larger ones as digits."""
    text = _WORDS[n] if 0 <= n < len(_WORDS) else f"{n:,}"
    return text.capitalize() if capital else text


def _made(value: float) -> str:
    return f"made {money(value)}" if value >= 0 else f"lost {money(-value)}"


def headline_sentence(net: TradeStats) -> str:
    """Rule 1."""
    start = f"{net.n:,} trades {_made(net.total)} net, a mean of {money(net.mean)} per trade"
    if math.isnan(net.t_stat):
        return start + "; every trade had the same result, so there is no t-statistic."
    side = (
        "more than two standard errors from zero"
        if abs(net.t_stat) >= T_THRESHOLD
        else "within two standard errors of zero"
    )
    return start + f" with a t-statistic of {net.t_stat:.2f}, which is {side}."


def concentration_sentence(leave: LeaveOut, to_zero: int) -> str:
    """Rule 2."""
    total = leave.removed_total + leave.rest.total
    if total <= 0:
        return "The log did not make money, so there is no profit to attribute to the best trades."
    if leave.rest.n == 0:
        return (
            f"The log has only {count_word(leave.removed)} trades, "
            "too few to leave the best ones out."
        )
    carry = "trade carries" if leave.removed == 1 else "trades carry"
    if leave.share >= CONCENTRATION_SHARE:
        return (
            f"{count_word(leave.removed, capital=True)} {carry} {percent(leave.share)} "
            f"of the profit: the other {leave.rest.n:,} {_made(leave.rest.total)} between them."
        )
    return (
        f"The best {count_word(leave.removed)} {carry} {percent(leave.share)} of the "
        f"profit, and the best {count_word(to_zero)} would have to go before the total "
        "reached zero."
    )


def halves_sentence(halves: HalfSplit) -> str:
    """Rule 3."""
    return (
        f"The first half of the trades {_made(halves.first.total)} "
        f"and the second half {_made(halves.second.total)}."
    )


def time_sentence(
    time_of_day: Sequence[BucketRow],
    perm_time_of_day: PermutationResult,
    perm_weekday: PermutationResult,
) -> str | None:
    """Rule 4."""
    flagged = [row for row in time_of_day if row.short_hold]
    if flagged:
        row = max(flagged, key=lambda r: abs(r.total))
        text = (
            f"The {row.label} window holds {row.n:,} trades for a median of "
            f"{row.median_hold_minutes:.1f} minutes"
        )
        if not math.isnan(row.share):
            text += f" and accounts for {percent(row.share)} of the profit"
        return text + "."
    for name, perm in (("time of day", perm_time_of_day), ("weekday", perm_weekday)):
        if perm.p_value < PERMUTATION_P:
            return (
                f"Results differ by {name} more than shuffled labels would give "
                f"(p = {perm.p_value:.3f})."
            )
    return None


def cost_sentence(cost: CostShare) -> str | None:
    """Rule 5."""
    if cost.share is None:
        return (
            f"The gross result was {money(cost.gross_total)}, so costs cannot be stated "
            "as a share of gross profit."
        )
    if cost.share >= COST_SHARE:
        return f"Costs took {percent(cost.share)} of the gross profit."
    return None


def verdict(a: Analysis) -> list[str]:
    """The verdict sentences for an analysis, in rule order."""
    sentences = [
        headline_sentence(a.net),
        concentration_sentence(a.leave_n, a.to_zero),
        halves_sentence(a.halves),
        time_sentence(a.time_of_day, a.perm_time_of_day, a.perm_weekday),
        cost_sentence(a.cost),
    ]
    return [s for s in sentences if s is not None]
