"""Hand arithmetic for each check. Every expected number is worked out in a comment."""

from __future__ import annotations

import math

import numpy as np
import pytest

from coroner import checks


def f(*values: float) -> checks.FloatArray:
    return np.asarray(values, dtype=np.float64)


def t(*stamps: str) -> checks.TimeArray:
    return np.asarray(stamps, dtype="datetime64[us]")


# ---- 1. per-trade statistics ---------------------------------------------


def test_trade_stats_by_hand() -> None:
    # mean 2.5; squared deviations 2.25 + 0.25 + 0.25 + 2.25 = 5; sd = sqrt(5/3)
    # t = 2.5 / sqrt(5/3) * 2 = sqrt(15)
    s = checks.trade_stats(f(1, 2, 3, 4))
    assert (s.n, s.total, s.mean) == (4, 10.0, 2.5)
    assert s.sd == pytest.approx(math.sqrt(5 / 3))
    assert s.t_stat == pytest.approx(math.sqrt(15))


def test_trade_stats_sign_follows_mean() -> None:
    assert checks.trade_stats(f(-1, -2, -3, -4)).t_stat == pytest.approx(-math.sqrt(15))


def test_trade_stats_degenerate_cases_are_nan() -> None:
    same = checks.trade_stats(f(5, 5, 5))
    assert same.mean == 5.0 and same.sd == 0.0 and math.isnan(same.t_stat)
    one = checks.trade_stats(f(7))
    assert one.mean == 7.0 and math.isnan(one.sd) and math.isnan(one.t_stat)
    none = checks.trade_stats(f())
    assert none.n == 0 and none.total == 0.0 and math.isnan(none.mean)


# ---- 2. permutation test ---------------------------------------------------


def test_between_group_ss_by_hand() -> None:
    # group means 2 and 6, grand mean 4: 2 * 4 + 2 * 4 = 16
    codes = np.array([0, 0, 1, 1])
    assert checks.between_group_ss(f(1, 3, 5, 7), codes, 2) == pytest.approx(16.0)


def test_permutation_perfect_separation_matches_exact_p() -> None:
    # Of the C(8, 4) = 70 ways to label four of eight values, two give the
    # observed statistic (the split and its mirror). Exact p = 2 / 70 = 0.0286.
    values = f(1, 1, 1, 1, 5, 5, 5, 5)
    codes = np.array([0, 0, 0, 0, 1, 1, 1, 1])
    result = checks.permutation_test(values, codes, n_draws=4000, seed=1)
    assert result.statistic == pytest.approx(32.0)
    assert result.p_value == pytest.approx(2 / 70, abs=0.012)


def test_permutation_p_is_uniform_when_labels_carry_nothing() -> None:
    # Under the null the p-value is uniform, so its mean over many data sets is
    # 0.5 with standard error 0.289 / sqrt(300) = 0.017, and 5% fall below 0.05.
    rng = np.random.default_rng(42)
    ps = []
    for i in range(300):
        values = rng.normal(size=60)
        codes = rng.integers(0, 3, size=60)
        ps.append(checks.permutation_test(values, codes, n_draws=200, seed=i).p_value)
    assert np.mean(ps) == pytest.approx(0.5, abs=0.06)
    assert 0.01 < np.mean(np.array(ps) < 0.05) < 0.10


def test_permutation_is_seeded_and_bounded() -> None:
    rng = np.random.default_rng(0)
    values, codes = rng.normal(size=40), rng.integers(0, 4, size=40)
    a = checks.permutation_test(values, codes, 500, seed=3)
    b = checks.permutation_test(values, codes, 500, seed=3)
    assert a == b
    assert 1 / 501 <= a.p_value <= 1.0


def test_permutation_single_group_is_nan() -> None:
    result = checks.permutation_test(f(1, 2, 3), np.array([2, 2, 2]), 10)
    assert math.isnan(result.p_value) and result.n_groups == 1


# ---- 3. halves -------------------------------------------------------------


def test_half_split_by_count() -> None:
    halves = checks.half_split(f(1, 2, 3, 4, 5))
    assert (halves.first.n, halves.first.total) == (2, 3.0)
    assert (halves.second.n, halves.second.total) == (3, 12.0)


# ---- 4. buckets ------------------------------------------------------------


def test_time_of_day_codes_and_labels() -> None:
    local = t(
        "2025-03-10T09:30:00", "2025-03-10T09:59:59", "2025-03-11T10:00:00", "2025-03-11T23:59"
    )
    codes, labels = checks.time_of_day_codes(local, 60)
    assert codes.tolist() == [9, 9, 10, 23]
    assert labels[9] == "09:00-10:00" and labels[23] == "23:00-24:00" and len(labels) == 24
    half, half_labels = checks.time_of_day_codes(local, 30)
    assert half.tolist() == [19, 19, 20, 47]
    assert half_labels[19] == "09:30-10:00"


def test_time_of_day_rejects_widths_that_do_not_divide_a_day() -> None:
    with pytest.raises(ValueError):
        checks.time_of_day_codes(t("2025-03-10T09:30"), 7)


def test_weekday_codes() -> None:
    # 2025-03-10 was a Monday and 2025-03-16 a Sunday; 1970-01-01 a Thursday.
    local = t("2025-03-10T12:00", "2025-03-16T00:00", "1970-01-01T00:00", "2025-03-14T23:59")
    assert checks.weekday_codes(local).tolist() == [0, 6, 3, 4]


def test_bucket_table_by_hand() -> None:
    values, hold = f(10, -5, 20, 5), f(1, 2, 3, 60)
    codes = np.array([0, 0, 0, 1])
    a, b = checks.bucket_table(values, hold, codes, ["a", "b"], 5.0, 3)
    # a: 10 - 5 + 20 = 25 of a 30 total; two winners of three; median hold 2
    assert (a.label, a.n, a.total) == ("a", 3, 25.0)
    assert a.mean == pytest.approx(25 / 3)
    assert a.share == pytest.approx(25 / 30)
    assert a.win_rate == pytest.approx(2 / 3)
    assert a.median_hold_minutes == 2.0 and a.short_hold
    assert (b.n, b.total, b.median_hold_minutes, b.short_hold) == (1, 5.0, 60.0, False)


def test_short_hold_flag_needs_enough_trades_and_a_short_median() -> None:
    values, codes = f(10, -5, 20), np.array([0, 0, 0])
    (few,) = checks.bucket_table(values, f(1, 2, 3), codes, ["a"], 5.0, 4)
    assert not few.short_hold  # three trades, four needed
    (slow,) = checks.bucket_table(values, f(1, 5, 9), codes, ["a"], 5.0, 3)
    assert not slow.short_hold  # median exactly 5 is not below 5


def test_bucket_share_is_nan_without_a_profit() -> None:
    (row,) = checks.bucket_table(f(-1, -2), f(1, 1), np.array([0, 0]), ["a"])
    assert math.isnan(row.share)


# ---- 5. leave-out ----------------------------------------------------------


def test_leave_out_best_by_hand() -> None:
    # total 10; best two are 10 and 5 = 15, a share of 150%; left: -2, 1, -4 = -5
    result = checks.leave_out_best(f(10, -2, 5, 1, -4), 2)
    assert (result.removed, result.removed_total) == (2, 15.0)
    assert result.share == pytest.approx(1.5)
    assert (result.rest.n, result.rest.total) == (3, -5.0)
    assert result.rest.mean == pytest.approx(-5 / 3)


def test_leave_out_more_than_there_are() -> None:
    result = checks.leave_out_best(f(1, 2), 10)
    assert result.removed == 2 and result.rest.n == 0 and result.share == pytest.approx(1.0)


def test_leave_out_share_nan_when_no_profit() -> None:
    assert math.isnan(checks.leave_out_best(f(1, -2), 1).share)


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ((10, -2, 5, 1, -4), 1),  # 10 - 10 = 0
        ((3, 3, 3, -1), 3),  # 8 -> 5 -> 2 -> -1
        ((1, 2, 3), 3),  # all winners: every one must go
        ((0.1, 0.2, 0.3), 3),  # the same in floats that do not sum exactly
        ((1, -1), 0),  # already zero
        ((-3, 1), 0),  # already negative
    ],
)
def test_trades_to_zero(values: tuple[float, ...], expected: int) -> None:
    assert checks.trades_to_zero(f(*values)) == expected


@pytest.mark.parametrize(("n", "k"), [(400, 20), (21, 2), (20, 1), (1, 1), (0, 0)])
def test_five_percent_count(n: int, k: int) -> None:
    assert checks.five_percent_count(n) == k


# ---- 6. cost share ---------------------------------------------------------


def test_cost_share_by_hand() -> None:
    cost = checks.cost_share(f(10, 10), f(8, 7))
    assert (cost.gross_total, cost.net_total, cost.cost_total) == (20.0, 15.0, 5.0)
    assert cost.share == pytest.approx(0.25)


@pytest.mark.parametrize("gross", [(-1.0, 1.0), (-5.0, 2.0)])
def test_cost_share_undefined_when_gross_not_positive(gross: tuple[float, float]) -> None:
    cost = checks.cost_share(f(*gross), f(gross[0] - 1, gross[1] - 1))
    assert cost.share is None and cost.cost_total == pytest.approx(2.0)


# ---- 7. drawdown -----------------------------------------------------------

EQUITY = (100.0, 110.0, 99.0, 121.0, 108.9)
# running max 100, 110, 110, 121, 121; drawdowns 0, 0, 10%, 0, 10%


def test_drawdown_pct_by_hand() -> None:
    assert checks.drawdown_pct(f(*EQUITY)).tolist() == pytest.approx([0, 0, 10, 0, 10])


def test_ulcer_index_by_hand() -> None:
    # sqrt((10^2 + 10^2) / 5) = sqrt(40)
    assert checks.ulcer_index(f(*EQUITY)) == pytest.approx(math.sqrt(40))


def test_ulcer_index_matches_martins_loop() -> None:
    # The loop as printed on Martin's page (see PAPER.md).
    rng = np.random.default_rng(5)
    values = 100 * np.exp(np.cumsum(rng.normal(0, 0.02, size=250)))
    sum_sq, max_value = 0.0, 0.0
    for v in values:
        if v > max_value:
            max_value = v
        else:
            sum_sq += (100 * (v / max_value - 1)) ** 2
    assert checks.ulcer_index(values) == pytest.approx(math.sqrt(sum_sq / len(values)))


def test_ulcer_index_zero_when_never_below_peak() -> None:
    assert checks.ulcer_index(f(100, 100, 105, 110)) == 0.0


def test_max_drawdown_by_hand() -> None:
    # 110 -> 99 is 11 (10%); 121 -> 108.9 is 12.1 (10%)
    amount, pct = checks.max_drawdown(f(*EQUITY))
    assert amount == pytest.approx(12.1) and pct == pytest.approx(10.0)


def test_drawdown_needs_positive_start() -> None:
    with pytest.raises(ValueError):
        checks.drawdown_pct(f(0, 1))


def days(*offsets: int) -> checks.TimeArray:
    return (
        np.datetime64("2025-01-01", "us") + np.asarray(offsets).astype("timedelta64[D]")
    ).astype("datetime64[us]")


def test_longest_underwater_recovered() -> None:
    # peak 110 on day 1, back to 110 on day 3: two days. The later spell, day 3
    # to day 5, is also two days and does not replace it.
    duration, recovered = checks.longest_underwater(
        days(0, 1, 2, 3, 4, 5), f(100, 110, 105, 110, 100, 100)
    )
    assert duration == np.timedelta64(2, "D") and recovered


def test_longest_underwater_still_open() -> None:
    duration, recovered = checks.longest_underwater(days(0, 1, 4), f(100, 90, 95))
    assert duration == np.timedelta64(4, "D") and not recovered


def test_longest_underwater_never_under() -> None:
    duration, recovered = checks.longest_underwater(days(0, 1, 2), f(100, 100, 120))
    assert duration == np.timedelta64(0, "D") and recovered


def test_annualised_return() -> None:
    # 21% over two years of 365.25 days is 10% a year
    assert checks.annualised_return_pct(100, 121, 730.5) == pytest.approx(10.0)
    assert math.isnan(checks.annualised_return_pct(100, 121, 0))
    assert math.isnan(checks.annualised_return_pct(100, -5, 100))


def test_martin_ratio_and_recovery_factor() -> None:
    assert checks.martin_ratio(10.0, 2.0, 1.0) == pytest.approx(4.5)
    assert math.isnan(checks.martin_ratio(10.0, 0.0))
    assert checks.recovery_factor(100.0, 25.0) == pytest.approx(4.0)
    assert math.isnan(checks.recovery_factor(100.0, 0.0))


def test_daily_equity_fills_days_without_trades() -> None:
    exits = t("2025-01-02T10:00", "2025-01-02T15:00", "2025-01-05T11:00")
    dates, equity = checks.daily_equity(exits, f(10, -4, 7), 100.0)
    assert [str(d) for d in dates] == [
        "2025-01-01",
        "2025-01-02",
        "2025-01-03",
        "2025-01-04",
        "2025-01-05",
    ]
    assert equity.tolist() == [100.0, 106.0, 106.0, 106.0, 113.0]


# ---- 8. positive periods ---------------------------------------------------


def test_positive_share_counts_only_periods_with_trades() -> None:
    exits = t("2025-01-02T10:00", "2025-01-02T15:00", "2025-01-03T11:00", "2025-01-07T11:00")
    # day 1: +10 - 4 = +6; day 2: -1; day 3: exactly 0, which is not positive
    share = checks.positive_share(checks.period_keys(exits, "day"), f(10, -4, -1, 0), "Days")
    assert (share.positive, share.total) == (1, 3)
    assert share.share == pytest.approx(1 / 3)


def test_period_keys_group_months_and_quarters() -> None:
    stamps = t("2025-01-15T00:00", "2025-01-31T23:59", "2025-03-01T00:00", "2025-04-01T00:00")
    months = checks.period_keys(stamps, "month")
    quarters = checks.period_keys(stamps, "quarter")
    assert months[0] == months[1] != months[2]
    assert quarters[0] == quarters[2] != quarters[3]
    months_share = checks.positive_share(months, f(1, -2, 3, 4), "Months")
    assert (months_share.positive, months_share.total) == (2, 3)
    with pytest.raises(ValueError):
        checks.period_keys(stamps, "week")
