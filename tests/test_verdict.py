"""Each verdict rule, with the exact sentence it must produce."""

from __future__ import annotations

import math

import numpy as np

from coroner import checks, verdict
from coroner.checks import BucketRow, CostShare, PermutationResult


def f(*values: float) -> checks.FloatArray:
    return np.asarray(values, dtype=np.float64)


def perm(p: float) -> PermutationResult:
    return PermutationResult(1.0, p, 2000, 5)


def row(label: str, n: int, total: float, share: float, hold: float, flag: bool) -> BucketRow:
    return BucketRow(label, n, total, total / n, share, 0.5, hold, flag)


def test_formatting_helpers() -> None:
    assert verdict.money(1234.5) == "1,234.50"
    assert verdict.money(-0.001) == "0.00"
    assert verdict.percent(0.99) == "99%"
    assert verdict.count_word(10) == "ten"
    assert verdict.count_word(10, capital=True) == "Ten"
    assert verdict.count_word(13) == "13"


def test_headline_strong() -> None:
    # mean 2.5, t = sqrt(15) = 3.87
    assert verdict.headline_sentence(checks.trade_stats(f(1, 2, 3, 4))) == (
        "4 trades made 10.00 net, a mean of 2.50 per trade with a t-statistic of 3.87, "
        "which is more than two standard errors from zero."
    )


def test_headline_weak_and_losing() -> None:
    # sum -3 over six trades: mean -0.5, small against a spread of several units
    stats = checks.trade_stats(f(1, -3, 0, 4, -4.5, -0.5))
    assert abs(stats.t_stat) < 2
    sentence = verdict.headline_sentence(checks.trade_stats(f(1, -3, 0, 4, -4.5, -0.5)))
    assert sentence.startswith("6 trades lost 3.00 net, a mean of -0.50 per trade")
    assert sentence.endswith("which is within two standard errors of zero.")


def test_headline_without_a_t_statistic() -> None:
    sentence = verdict.headline_sentence(checks.trade_stats(f(5, 5, 5)))
    assert "t-statistic of" not in sentence and "same result" in sentence


def null(p: float, median: float = 0.3) -> checks.ConcentrationNull:
    return checks.ConcentrationNull("normal", 2000, median, 0.45, p, 40.0, 25.0, 0.5, 0)


def test_concentration_when_the_best_carry_more_than_the_null_gives() -> None:
    # 10 trades of 99 and 20 of 0.5: total 1000, best ten carry 99%
    values = f(*([99.0] * 10 + [0.5] * 20))
    sentence = verdict.concentration_sentence(checks.leave_out_best(values, 10), 11, null(0.01))
    assert sentence == (
        "Ten trades carry 99% of the profit, against a median of 30% for logs drawn from a "
        "Normal with the same mean and spread (p = 0.0100): the other 20 made 10.00 between them."
    )


def test_concentration_when_the_rest_lost() -> None:
    values = f(100, 100, -30, -20)
    sentence = verdict.concentration_sentence(checks.leave_out_best(values, 2), 2, null(0.001))
    assert sentence.startswith("Two trades carry 133% of the profit, against a median of 30%")
    assert sentence.endswith(": the other 2 lost 50.00 between them.")


def test_concentration_within_the_null() -> None:
    values = f(*([10.0] * 100))
    sentence = verdict.concentration_sentence(
        checks.leave_out_best(values, 10), checks.trades_to_zero(values), null(0.5, 0.1)
    )
    assert sentence == (
        "The best ten trades carry 10% of the profit, against a median of 10% for logs drawn "
        "from a Normal with the same mean and spread (p = 0.5000), and the best 100 would have "
        "to go before the total reached zero."
    )


def test_concentration_without_a_null_names_no_reference() -> None:
    values = f(*([99.0] * 10 + [0.5] * 20))
    sentence = verdict.concentration_sentence(checks.leave_out_best(values, 10), 11)
    assert sentence == (
        "The best ten trades carry 99% of the profit, and the best eleven would have to go "
        "before the total reached zero."
    )


def test_concentration_threshold_is_p_below_five_percent() -> None:
    leave = checks.leave_out_best(f(5, 5, 4, 3, 2, 1), 2)
    assert verdict.concentration_sentence(leave, 4, null(0.0499)).startswith("Two trades carry")
    assert verdict.concentration_sentence(leave, 4, null(0.05)).startswith("The best two trades")


def test_concentration_with_one_trade_left_out() -> None:
    sentence = verdict.concentration_sentence(checks.leave_out_best(f(5, 1, 1), 1), 1)
    assert sentence.startswith("The best trade carries 71% of the profit")


def test_concentration_when_no_profit_or_too_few_trades() -> None:
    lost = verdict.concentration_sentence(checks.leave_out_best(f(1, -2, -3), 1), 0)
    assert lost.startswith("The log did not make money")
    few = verdict.concentration_sentence(checks.leave_out_best(f(1, 2, 3), 10), 3)
    assert few == "The log has only three trades, too few to leave the best ones out."


def test_halves_sentence() -> None:
    assert verdict.halves_sentence(checks.half_split(f(5, 5, -3, 1))) == (
        "The first half of the trades made 10.00 and the second half lost 2.00."
    )


def test_time_sentence_names_the_flagged_bucket_with_most_profit() -> None:
    rows = [
        row("09:00-10:00", 60, 19432.24, 0.972, 3.2, True),
        row("10:00-11:00", 40, 500.0, 0.025, 2.0, True),
        row("11:00-12:00", 30, 67.76, 0.003, 40.0, False),
    ]
    assert verdict.time_sentence(rows, perm(0.5), perm(0.5)) == (
        "The 09:00-10:00 window holds 60 trades for a median of 3.2 minutes "
        "and accounts for 97% of the profit."
    )


def test_time_sentence_flag_without_share() -> None:
    rows = [row("09:00-10:00", 25, -100.0, math.nan, 1.0, True)]
    assert verdict.time_sentence(rows, perm(0.5), perm(0.5)) == (
        "The 09:00-10:00 window holds 25 trades for a median of 1.0 minutes."
    )


def test_time_sentence_falls_back_to_the_permutation_tests() -> None:
    rows = [row("09:00-10:00", 60, 100.0, 1.0, 30.0, False)]
    assert verdict.time_sentence(rows, perm(0.004), perm(0.5)) == (
        "Results differ by time of day more than shuffled labels would give (p = 0.004)."
    )
    assert verdict.time_sentence(rows, perm(0.5), perm(0.002)) == (
        "Results differ by weekday more than shuffled labels would give (p = 0.002)."
    )


def test_time_sentence_is_silent_otherwise() -> None:
    rows = [row("09:00-10:00", 60, 100.0, 1.0, 30.0, False)]
    assert verdict.time_sentence(rows, perm(0.01), perm(0.03)) is None  # 0.01 is not below 0.01
    assert verdict.time_sentence(rows, perm(math.nan), perm(math.nan)) is None


def test_cost_sentence() -> None:
    assert verdict.cost_sentence(CostShare(100.0, 80.0, 20.0, 0.2)) is None
    assert verdict.cost_sentence(CostShare(100.0, 50.0, 50.0, 0.5)) == (
        "Costs took 50% of the gross profit."
    )
    assert verdict.cost_sentence(CostShare(-40.0, -90.0, 50.0, None)) == (
        "The gross result was -40.00, so costs cannot be stated as a share of gross profit."
    )
