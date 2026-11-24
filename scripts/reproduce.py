"""Rebuild everything in results/.

    uv run python scripts/fetch_data.py         download the Ken French files into data/
    uv run python scripts/reproduce.py          full run
    uv run python scripts/reproduce.py --fast   fewer paths and draws, for CI

With the Ken French files in data/, the three real trade logs in logs/ are
rebuilt from them first. Without data/, the committed logs are used as they
are. Then a report is written for each real log and for each of the two
synthetic logs in samples/, with the headline chart, the summary tables and the
barrier-simulator check. Seeds are fixed, so two runs give identical files.
"""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

import numpy as np

from coroner import barrier, charts, strategies
from coroner.analysis import Analysis, Settings, analyse
from coroner.report import build_report, write_report
from coroner.samples import write_samples
from coroner.trades import load_trades

ROOT = Path(__file__).resolve().parent.parent
REAL_LOGS = ("market_ma200", "industry_ma200", "industry_reversal")
REAL_TITLES = {
    "market_ma200": "US market, 200-day average",
    "industry_ma200": "Ten industries, 200-day average",
    "industry_reversal": "Ten industries, 5-day reversal",
}
SYNTHETIC_TITLES = {
    "broad": "broad.csv (synthetic)",
    "concentrated": "concentrated.csv (synthetic)",
}
# Biased +-1 walks are cheap, so they get many paths; the Gaussian rows take
# thousands of steps per path and get fewer.
WALK_PATHS = 1_000_000
GAUSSIAN_PATHS = 100_000


def _pct(x: float) -> str:
    if math.isinf(x):
        return "total not positive"
    return "n/a" if math.isnan(x) else f"{100 * x:.1f}%"


def _p(x: float) -> str:
    return "n/a" if math.isnan(x) else f"{x:.4f}"


def summary_rows(a: Analysis) -> list[tuple[str, str]]:
    """The numbers the README quotes, as (name, formatted value)."""
    b = a.barrier
    flagged = [r for r in a.time_of_day if r.short_hold]
    k = a.leave_n.removed
    rows = [
        ("Trades", f"{a.n}"),
        ("First entry", str(a.first_entry.astype("datetime64[D]"))),
        ("Last exit", str(a.last_exit.astype("datetime64[D]"))),
        ("Net total", f"{a.net.total:.2f}"),
        ("Mean per trade", f"{a.net.mean:.2f}"),
        ("Std dev per trade", f"{a.net.sd:.2f}"),
        ("t-statistic", f"{a.net.t_stat:.2f}"),
    ]
    rows += [
        (f"t-statistic, clustered by {c.period} (clusters)", f"{c.t_stat:.2f} ({c.clusters})")
        for c in a.clustered
    ]
    rows += [
        (f"Share of profit in best {k}", _pct(a.leave_n.share)),
        (f"Total without best {k}", f"{a.leave_n.rest.total:.2f}"),
        (f"t-statistic without best {k}", f"{a.leave_n.rest.t_stat:.2f}"),
        (
            "Total without best 5% (trades removed)",
            f"{a.leave_5pct.rest.total:.2f} ({a.leave_5pct.removed})",
        ),
        ("Best trades to remove to reach zero", f"{a.to_zero}"),
    ]
    for label, null in (("Normal", a.null_normal), ("reflected", a.null_symmetric)):
        if null is None:
            continue
        rows += [
            (
                f"{label} null: best-{k} share median / 95th pct / p",
                f"{_pct(null.share_median)} / {_pct(null.share_p95)} / {null.share_p:.4f}",
            ),
            (
                f"{label} null: trades to zero median / 5th pct / p",
                f"{null.to_zero_median:.0f} / {null.to_zero_p05:.0f} / {null.to_zero_p:.4f}",
            ),
        ]
    rows += [
        ("First half total", f"{a.halves.first.total:.2f}"),
        ("Second half total", f"{a.halves.second.total:.2f}"),
        ("Permutation p, time of day", _p(a.perm_time_of_day.p_value)),
        ("Permutation p, weekday", _p(a.perm_weekday.p_value)),
        (
            "Short-hold buckets",
            "; ".join(
                f"{r.label} ({r.n} trades, median {r.median_hold_minutes:.1f} min, "
                f"{_pct(r.share)} of profit)"
                for r in flagged
            )
            or "none",
        ),
        ("Cost share of gross", "n/a" if a.cost.share is None else _pct(a.cost.share)),
        ("Ulcer index (%)", f"{a.drawdown.ulcer_index:.3f}"),
        ("Martin ratio", f"{a.drawdown.martin_ratio:.2f}"),
        ("Maximum drawdown", f"{a.drawdown.max_drawdown:.2f}"),
        ("Recovery factor", f"{a.drawdown.recovery_factor:.2f}"),
    ]
    rows += [(f"Positive {p.name.lower()}", f"{p.positive} of {p.total}") for p in a.periods]
    for label, r in (
        ("i.i.d.", b.iid),
        ("stationary", b.stationary),
        (f"i.i.d. without best {k}", b.iid_without_best),
    ):
        if r is not None:
            rows.append(
                (
                    f"Target / loss limit / neither, {label}",
                    f"{_pct(r.p_target)} / {_pct(r.p_loss)} / {_pct(r.p_neither)}",
                )
            )
    return rows


def barrier_check(walk_paths: int, gaussian_paths: int) -> list[dict[str, str]]:
    """Simulate walks with known answers and compare."""
    rows: list[dict[str, str]] = []

    def add(case: str, source: str, exact: float, result: barrier.BarrierResult) -> None:
        se = math.sqrt(exact * (1 - exact) / result.paths)
        rows.append(
            {
                "case": case,
                "closed_form": source,
                "exact": f"{exact:.5f}",
                "simulated": f"{result.p_target:.5f}",
                "difference": f"{result.p_target - exact:+.5f}",
                "std_error": f"{se:.5f}",
                "z": f"{(result.p_target - exact) / se:+.2f}",
                "neither": f"{result.p_neither:.5f}",
                "paths": f"{result.paths}",
            }
        )

    walks = [
        ("fair +-1 walk, target 15, limit 10", [1.0, -1.0], 0.5, 15, 10, 3000),
        ("+-1 walk p=0.55, target 10, limit 10", [1.0] * 11 + [-1.0] * 9, 0.55, 10, 10, 1500),
        ("+-1 walk p=0.45, target 10, limit 10", [1.0] * 9 + [-1.0] * 11, 0.45, 10, 10, 1500),
    ]
    for seed, (case, values, p, b, a, horizon) in enumerate(walks):
        result = barrier.barrier_odds(
            np.asarray(values), b, a, horizon, walk_paths, "iid", seed=100 + seed
        )
        add(case, "gambler's ruin", barrier.gamblers_ruin_probability(p, b, a), result)

    # Gaussian steps against the Brownian closed form. Halving the step size
    # (same drift and variance per unit time) shrinks the overshoot at the barrier.
    for seed, (sigma, horizon) in enumerate(((0.5, 6000), (0.25, 24000))):
        mu = 0.02 * sigma**2  # keeps 2 mu / sigma^2 = 0.04
        rng = np.random.default_rng(200 + seed)
        hit_target = hit_loss = done = 0
        batch = max(1, 4_000_000 // horizon)
        while done < gaussian_paths:
            size = min(batch, gaussian_paths - done)
            part = barrier.first_barrier(rng.normal(mu, sigma, size=(size, horizon)), 15.0, 10.0)
            hit_target += part.hit_target
            hit_loss += part.hit_loss
            done += size
        add(
            f"Gaussian steps sd={sigma:g}, 2mu/sd^2=0.04, target 15, limit 10",
            "Brownian motion",
            barrier.brownian_hit_probability(mu, sigma, 15.0, 10.0),
            barrier.BarrierResult(gaussian_paths, hit_target, hit_loss),
        )
    return rows


def _write_table(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix(".csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)
    lines = [
        "| " + " | ".join(header) + " |",
        "|" + "|".join([":--"] + ["--:"] * (len(header) - 1)) + "|",
    ]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    path.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def _summary(path: Path, analyses: list[tuple[str, Analysis]]) -> None:
    columns = [summary_rows(a) for _, a in analyses]
    _write_table(
        path,
        ["", *(name for name, _ in analyses)],
        [[cells[0][0], *(cell[1] for cell in cells)] for cells in zip(*columns, strict=True)],
    )


def _reports(paths: list[Path], out_dir: Path, settings: Settings) -> list[tuple[str, Analysis]]:
    analyses = []
    for path in paths:
        analysis = analyse(load_trades(path), settings)
        write_report(build_report(analysis, path.name), out_dir / path.stem)
        analyses.append((path.stem, analysis))
        print(f"wrote {out_dir / path.stem}")
    return analyses


def run(
    out_dir: Path,
    samples_dir: Path,
    logs_dir: Path,
    data_dir: Path | None = None,
    fast: bool = False,
) -> None:
    """Write every result into ``out_dir``.

    With ``data_dir``, the real logs are rebuilt from it into ``logs_dir`` first;
    otherwise they are read from ``logs_dir``. The synthetic samples are always
    rewritten into ``samples_dir``.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    settings = Settings(paths=1000, draws=200) if fast else Settings()

    if data_dir is not None:
        for name, trades in strategies.build_logs(data_dir).items():
            strategies.write_log(trades, logs_dir / f"{name}.csv")
            print(f"wrote {logs_dir / name}.csv ({len(trades)} trades)")
        _write_table(
            out_dir / "data_used",
            ["file", "sha256", "first date", "last date"],
            [list(row) for row in strategies.data_summary(data_dir)],
        )

    real = _reports([logs_dir / f"{name}.csv" for name in REAL_LOGS], out_dir / "real", settings)
    (out_dir / "headline.png").write_bytes(
        charts.headline_chart([(REAL_TITLES[name], a) for name, a in real])
    )
    _summary(out_dir / "summary", real)

    synthetic = _reports(list(write_samples(samples_dir)), out_dir / "synthetic", settings)
    (out_dir / "synthetic" / "headline.png").write_bytes(
        charts.headline_chart([(SYNTHETIC_TITLES[name], a) for name, a in synthetic])
    )
    _summary(out_dir / "synthetic" / "summary", synthetic)

    check = barrier_check(*((2000, 2000) if fast else (WALK_PATHS, GAUSSIAN_PATHS)))
    header = list(check[0])
    _write_table(out_dir / "barrier_check", header, [[row[h] for h in header] for row in check])
    print(f"wrote {out_dir / 'headline.png'}, summary and barrier_check tables")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fast", action="store_true", help="fewer paths and draws")
    parser.add_argument("--out", type=Path, default=ROOT / "results", help="output directory")
    args = parser.parse_args()
    data = ROOT / "data"
    have_data = all(
        (data / name).is_file() for name in (strategies.FACTORS_ZIP, strategies.INDUSTRY_ZIP)
    )
    if not have_data:
        print("data/ has no Ken French files; using the committed logs in logs/")
    run(args.out, ROOT / "samples", ROOT / "logs", data if have_data else None, fast=args.fast)
