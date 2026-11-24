"""Run every check on a trade log and collect the results."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from coroner import barrier, checks
from coroner.checks import FloatArray, TimeArray
from coroner.trades import TradeLog

MIN_DAYS_TO_ANNUALISE = 30.0


@dataclass(frozen=True)
class Settings:
    """Everything the user can set. Defaults are documented in the README."""

    capital: float = 100_000.0
    best_n: int = 10
    bucket_minutes: int = 60
    short_hold_minutes: float = 5.0
    min_bucket_trades: int = 20
    target: float | None = None
    loss_limit: float | None = None
    horizon: int | None = None
    paths: int = 10_000
    draws: int = 2000
    mean_block: float = 10.0
    risk_free_pct: float = 0.0
    seed: int = 0

    def validate(self) -> None:
        """Raise ``ValueError`` with a plain message when a setting is unusable."""
        if not self.capital > 0:
            raise ValueError("capital must be positive")
        if self.best_n < 1:
            raise ValueError("best-n must be at least 1")
        if self.bucket_minutes <= 0 or 1440 % self.bucket_minutes != 0:
            raise ValueError("bucket-minutes must divide 1440 (for example 30, 60 or 120)")
        if self.target is not None and not self.target > 0:
            raise ValueError("target must be positive")
        if self.loss_limit is not None and not self.loss_limit > 0:
            raise ValueError("loss-limit must be positive (give it as a positive amount)")
        if self.horizon is not None and self.horizon < 1:
            raise ValueError("horizon must be at least 1 trade")
        if self.paths < 1 or self.draws < 1:
            raise ValueError("paths and draws must be at least 1")
        if self.mean_block < 1:
            raise ValueError("block must be at least 1 trade")


@dataclass(frozen=True)
class DrawdownSummary:
    """Drawdown measures. See ``PAPER.md`` for which series each one uses."""

    ulcer_index: float
    annual_return_pct: float
    martin_ratio: float
    max_drawdown: float
    max_drawdown_pct: float
    underwater: np.timedelta64
    underwater_recovered: bool
    recovery_factor: float


@dataclass(frozen=True)
class BarrierSummary:
    """Target-before-loss-limit results under each resampling scheme."""

    target: float
    loss_limit: float
    horizon: int
    mean_block: float
    iid: barrier.BarrierResult
    stationary: barrier.BarrierResult
    iid_without_best: barrier.BarrierResult | None
    brownian: float


@dataclass(frozen=True)
class Analysis:
    """The output of every check, plus the series the charts need."""

    settings: Settings
    n: int
    first_entry: np.datetime64
    last_exit: np.datetime64
    clock: str
    net: checks.TradeStats
    gross: checks.TradeStats
    clustered: list[checks.ClusteredT]
    perm_time_of_day: checks.PermutationResult
    perm_weekday: checks.PermutationResult
    halves: checks.HalfSplit
    time_of_day: list[checks.BucketRow]
    weekday: list[checks.BucketRow]
    leave_n: checks.LeaveOut
    leave_5pct: checks.LeaveOut
    to_zero: int
    null_normal: checks.ConcentrationNull | None
    null_symmetric: checks.ConcentrationNull | None
    cost: checks.CostShare
    drawdown: DrawdownSummary
    periods: list[checks.PeriodShare]
    barrier: BarrierSummary
    by_symbol: list[checks.BucketRow] | None
    by_side: list[checks.BucketRow] | None
    size_median: float | None
    exit_times: TimeArray
    cumulative: FloatArray
    cumulative_without_best: FloatArray
    daily_dates: TimeArray
    daily_drawdown_pct: FloatArray


def _group_rows(
    labels: tuple[str, ...], values: FloatArray, hold: FloatArray
) -> list[checks.BucketRow]:
    names = sorted(set(labels))
    index = {name: i for i, name in enumerate(names)}
    codes = np.asarray([index[label] for label in labels], dtype=np.int64)
    rows = checks.bucket_table(values, hold, codes, names, short_hold_minutes=0.0)
    return sorted(rows, key=lambda r: (-r.total, r.label))


def analyse(log: TradeLog, settings: Settings | None = None) -> Analysis:
    """Run all checks on ``log``. Deterministic for a given ``settings.seed``."""
    s = settings or Settings()
    s.validate()
    net, n = log.net, len(log)
    hold = log.hold_minutes

    net_stats = checks.trade_stats(net)

    tod_codes, tod_labels = checks.time_of_day_codes(log.entry_local, s.bucket_minutes)
    wd_codes = checks.weekday_codes(log.entry_local)
    perm_tod = checks.permutation_test(net, tod_codes, s.draws, s.seed)
    perm_wd = checks.permutation_test(net, wd_codes, s.draws, s.seed + 1)
    tod_rows = checks.bucket_table(
        net, hold, tod_codes, tod_labels, s.short_hold_minutes, s.min_bucket_trades
    )
    wd_rows = checks.bucket_table(
        net, hold, wd_codes, checks.WEEKDAYS, s.short_hold_minutes, s.min_bucket_trades
    )

    # Drawdown: the ulcer index and Martin ratio use daily closes; maximum
    # drawdown, time under water and recovery factor use the trade-by-trade curve.
    cumulative = np.cumsum(net)
    trade_equity = np.concatenate(([s.capital], s.capital + cumulative))
    trade_times = np.concatenate(([log.entry.min()], log.exit))
    daily_dates, daily = checks.daily_equity(log.exit_local, net, s.capital)
    ulcer = checks.ulcer_index(daily)
    span_days = float((log.exit.max() - log.entry.min()) / np.timedelta64(1, "s")) / 86_400.0
    # Annualising a few days of trading compounds noise into nonsense, so the
    # annual return and the Martin ratio are left undefined for short logs.
    annual = (
        checks.annualised_return_pct(s.capital, float(trade_equity[-1]), span_days)
        if span_days >= MIN_DAYS_TO_ANNUALISE
        else math.nan
    )
    dd_amount, dd_pct = checks.max_drawdown(trade_equity)
    underwater, recovered = checks.longest_underwater(trade_times, trade_equity)
    drawdown = DrawdownSummary(
        ulcer_index=ulcer,
        annual_return_pct=annual,
        martin_ratio=checks.martin_ratio(annual, ulcer, s.risk_free_pct),
        max_drawdown=dd_amount,
        max_drawdown_pct=dd_pct,
        underwater=underwater,
        underwater_recovered=recovered,
        recovery_factor=checks.recovery_factor(net_stats.total, dd_amount),
    )

    periods = [
        checks.positive_share(checks.period_keys(log.exit_local, key), net, name)
        for key, name in (("day", "Days"), ("month", "Months"), ("quarter", "Quarters"))
    ]

    target = s.target if s.target is not None else 0.10 * s.capital
    loss_limit = s.loss_limit if s.loss_limit is not None else 0.10 * s.capital
    horizon = s.horizon if s.horizon is not None else n
    best = np.argsort(-net, kind="stable")[: min(s.best_n, n)]
    keep = np.ones(n, dtype=bool)
    keep[best] = False
    without = (
        barrier.barrier_odds(
            net[keep], target, loss_limit, horizon, s.paths, "iid", s.mean_block, s.seed + 4
        )
        if keep.any()
        else None
    )
    brownian = (
        barrier.brownian_hit_probability(net_stats.mean, net_stats.sd, target, loss_limit)
        if net_stats.sd > 0
        else math.nan
    )
    barrier_summary = BarrierSummary(
        target=target,
        loss_limit=loss_limit,
        horizon=horizon,
        mean_block=s.mean_block,
        iid=barrier.barrier_odds(
            net, target, loss_limit, horizon, s.paths, "iid", s.mean_block, s.seed + 2
        ),
        stationary=barrier.barrier_odds(
            net, target, loss_limit, horizon, s.paths, "stationary", s.mean_block, s.seed + 3
        ),
        iid_without_best=without,
        brownian=brownian,
    )

    # The concentration nulls need a spread to scale by and a profit to share out.
    can_compare = n >= 2 and net_stats.sd > 0 and net_stats.total > 0
    null_normal, null_symmetric = (
        (
            checks.concentration_null(net, s.best_n, "normal", s.draws, s.seed + 5),
            checks.concentration_null(net, s.best_n, "symmetric", s.draws, s.seed + 6),
        )
        if can_compare
        else (None, None)
    )

    return Analysis(
        settings=s,
        n=n,
        first_entry=log.entry_local.min(),
        last_exit=log.exit_local.max(),
        clock=log.clock,
        net=net_stats,
        gross=checks.trade_stats(log.gross),
        clustered=[
            checks.clustered_t(net, checks.period_keys(log.exit_local, key), name)
            for key, name in (("day", "exit day"), ("month", "exit month"))
        ],
        perm_time_of_day=perm_tod,
        perm_weekday=perm_wd,
        halves=checks.half_split(net),
        time_of_day=tod_rows,
        weekday=wd_rows,
        leave_n=checks.leave_out_best(net, s.best_n),
        leave_5pct=checks.leave_out_best(net, checks.five_percent_count(n)),
        to_zero=checks.trades_to_zero(net),
        null_normal=null_normal,
        null_symmetric=null_symmetric,
        cost=checks.cost_share(log.gross, net),
        drawdown=drawdown,
        periods=periods,
        barrier=barrier_summary,
        by_symbol=None if log.symbol is None else _group_rows(log.symbol, net, hold),
        by_side=None if log.side is None else _group_rows(log.side, net, hold),
        size_median=None if log.size is None else float(np.median(log.size)),
        exit_times=log.exit_local,
        cumulative=cumulative,
        cumulative_without_best=np.cumsum(np.where(keep, net, 0.0)),
        daily_dates=daily_dates,
        daily_drawdown_pct=checks.drawdown_pct(daily),
    )
