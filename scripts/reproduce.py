"""Rebuild everything in results/ from nothing.

    uv run python scripts/reproduce.py          full run
    uv run python scripts/reproduce.py --fast   fewer paths and draws, for CI

It regenerates the two sample logs, writes a report for each, draws the
headline chart, and writes two tables: the samples side by side, and the
barrier simulator against its closed forms. Seeds are fixed, so two runs give
identical files.
"""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

import numpy as np

from coroner import barrier, charts
from coroner.analysis import Analysis, Settings, analyse
from coroner.report import build_report, write_report
from coroner.samples import write_samples
from coroner.trades import load_trades

ROOT = Path(__file__).resolve().parent.parent


def _pct(x: float) -> str:
    return "n/a" if math.isnan(x) else f"{100 * x:.1f}%"


def summary_rows(a: Analysis) -> list[tuple[str, str]]:
    """The numbers the README quotes, as (name, formatted value)."""
    b = a.barrier
    flagged = [r for r in a.time_of_day if r.short_hold]
    rows = [
        ("Trades", f"{a.n}"),
        ("Net total", f"{a.net.total:.2f}"),
        ("Mean per trade", f"{a.net.mean:.2f}"),
        ("Std dev per trade", f"{a.net.sd:.2f}"),
        ("t-statistic", f"{a.net.t_stat:.2f}"),
        (f"Share of profit in best {a.leave_n.removed}", _pct(a.leave_n.share)),
        (f"Total without best {a.leave_n.removed}", f"{a.leave_n.rest.total:.2f}"),
        (f"t-statistic without best {a.leave_n.removed}", f"{a.leave_n.rest.t_stat:.2f}"),
        (f"Total without best 5% ({a.leave_5pct.removed})", f"{a.leave_5pct.rest.total:.2f}"),
        ("Best trades to remove to reach zero", f"{a.to_zero}"),
        ("First half total", f"{a.halves.first.total:.2f}"),
        ("Second half total", f"{a.halves.second.total:.2f}"),
        ("Permutation p, time of day", f"{a.perm_time_of_day.p_value:.4f}"),
        ("Permutation p, weekday", f"{a.perm_weekday.p_value:.4f}"),
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
        (f"i.i.d. without best {a.leave_n.removed}", b.iid_without_best),
    ):
        if r is not None:
            rows.append(
                (
                    f"Target / loss limit / neither, {label}",
                    f"{_pct(r.p_target)} / {_pct(r.p_loss)} / {_pct(r.p_neither)}",
                )
            )
    return rows


def barrier_check(paths: int) -> list[dict[str, str]]:
    """Simulate walks with known answers and compare."""
    rows: list[dict[str, str]] = []

    def add(case: str, source: str, exact: float, result: barrier.BarrierResult) -> None:
        se = math.sqrt(exact * (1 - exact) / result.paths)
        rows.append(
            {
                "case": case,
                "closed_form": source,
                "exact": f"{exact:.4f}",
                "simulated": f"{result.p_target:.4f}",
                "difference": f"{result.p_target - exact:+.4f}",
                "std_error": f"{se:.4f}",
                "z": f"{(result.p_target - exact) / se:+.2f}",
                "neither": f"{result.p_neither:.4f}",
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
            np.asarray(values), b, a, horizon, paths, "iid", seed=100 + seed
        )
        add(case, "gambler's ruin", barrier.gamblers_ruin_probability(p, b, a), result)

    # Gaussian steps against the Brownian closed form. Halving the step size
    # (same drift and variance per unit time) shrinks the overshoot at the barrier.
    for seed, (sigma, horizon) in enumerate(((0.5, 6000), (0.25, 24000))):
        mu = 0.02 * sigma**2  # keeps 2 mu / sigma^2 = 0.04
        rng = np.random.default_rng(200 + seed)
        hit_target = hit_loss = done = 0
        batch = max(1, 4_000_000 // horizon)
        while done < paths:
            size = min(batch, paths - done)
            part = barrier.first_barrier(rng.normal(mu, sigma, size=(size, horizon)), 15.0, 10.0)
            hit_target += part.hit_target
            hit_loss += part.hit_loss
            done += size
        add(
            f"Gaussian steps sd={sigma:g}, 2mu/sd^2=0.04, target 15, limit 10",
            "Brownian motion",
            barrier.brownian_hit_probability(mu, sigma, 15.0, 10.0),
            barrier.BarrierResult(paths, hit_target, hit_loss),
        )
    return rows


def _write_table(path: Path, header: list[str], rows: list[list[str]]) -> None:
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


def run(out_dir: Path, samples_dir: Path, fast: bool = False) -> None:
    """Write samples into ``samples_dir`` and every result into ``out_dir``."""
    out_dir.mkdir(parents=True, exist_ok=True)
    settings = Settings(paths=1000, draws=200) if fast else Settings()
    analyses: list[tuple[str, Analysis]] = []
    for path in write_samples(samples_dir):
        analysis = analyse(load_trades(path), settings)
        write_report(build_report(analysis, path.name), out_dir / path.stem)
        analyses.append((path.stem, analysis))
        print(f"wrote {out_dir / path.stem}")

    titles = {
        "broad": "broad.csv: a broad small edge",
        "concentrated": "concentrated.csv: ten trades",
    }
    (out_dir / "headline.png").write_bytes(
        charts.headline_chart([(titles[name], a) for name, a in analyses])
    )

    columns = [summary_rows(a) for _, a in analyses]
    _write_table(
        out_dir / "summary",
        ["", *(name for name, _ in analyses)],
        [[left[0], left[1], right[1]] for left, right in zip(*columns, strict=True)],
    )

    check = barrier_check(2000 if fast else 20_000)
    header = list(check[0])
    _write_table(out_dir / "barrier_check", header, [[row[h] for h in header] for row in check])
    print(f"wrote {out_dir / 'headline.png'}, summary and barrier_check tables")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fast", action="store_true", help="fewer paths and draws")
    parser.add_argument("--out", type=Path, default=ROOT / "results", help="output directory")
    args = parser.parse_args()
    run(args.out, ROOT / "samples", fast=args.fast)
