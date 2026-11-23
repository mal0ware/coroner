"""Command line: ``coroner report trades.csv``."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from coroner import __version__
from coroner.analysis import Settings, analyse
from coroner.report import build_report, write_report
from coroner.trades import TradeLogError, load_trades


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="coroner", description="Reads a trade log and reports what the profit rests on."
    )
    parser.add_argument("--version", action="version", version=f"coroner {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    report = commands.add_parser(
        "report",
        help="write a markdown and an HTML report for a trade log",
        description=(
            "Reads a CSV with the columns entry_time, exit_time, gross, net (optional: "
            "symbol, side, size) and writes report.md, report.html and figures/ into the "
            "output directory."
        ),
    )
    d = Settings()
    report.add_argument("trades", type=Path, help="CSV file of trades")
    report.add_argument("--out", type=Path, help="output directory (default: <file stem>-report)")
    report.add_argument("--tz", help="convert timezone-aware timestamps to this IANA zone")
    report.add_argument(
        "--capital", type=float, default=d.capital, help=f"starting equity (default {d.capital:g})"
    )
    report.add_argument(
        "--best-n",
        type=int,
        default=d.best_n,
        help=f"best trades to leave out (default {d.best_n})",
    )
    report.add_argument(
        "--bucket-minutes",
        type=int,
        default=d.bucket_minutes,
        help=f"width of time-of-day buckets (default {d.bucket_minutes})",
    )
    report.add_argument(
        "--short-hold-minutes",
        type=float,
        default=d.short_hold_minutes,
        help=f"flag buckets whose median hold is below this (default {d.short_hold_minutes:g})",
    )
    report.add_argument(
        "--min-bucket-trades",
        type=int,
        default=d.min_bucket_trades,
        help=f"trades a bucket needs before it can be flagged (default {d.min_bucket_trades})",
    )
    report.add_argument("--target", type=float, help="profit target (default 10%% of capital)")
    report.add_argument(
        "--loss-limit",
        type=float,
        help="loss limit, as a positive amount (default 10%% of capital)",
    )
    report.add_argument("--horizon", type=int, help="trades per resampled path (default: all)")
    report.add_argument(
        "--paths", type=int, default=d.paths, help=f"resampled paths (default {d.paths})"
    )
    report.add_argument(
        "--draws", type=int, default=d.draws, help=f"permutation draws (default {d.draws})"
    )
    report.add_argument(
        "--block",
        type=float,
        default=d.mean_block,
        help=f"mean block length of the stationary bootstrap, in trades (default {d.mean_block:g})",
    )
    report.add_argument(
        "--risk-free",
        type=float,
        default=d.risk_free_pct,
        help="risk-free rate in percent a year, for the Martin ratio (default 0)",
    )
    report.add_argument("--seed", type=int, default=d.seed, help=f"random seed (default {d.seed})")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point. Returns 0 on success and 2 when the input cannot be used."""
    args = _parser().parse_args(argv)
    settings = Settings(
        capital=args.capital,
        best_n=args.best_n,
        bucket_minutes=args.bucket_minutes,
        short_hold_minutes=args.short_hold_minutes,
        min_bucket_trades=args.min_bucket_trades,
        target=args.target,
        loss_limit=args.loss_limit,
        horizon=args.horizon,
        paths=args.paths,
        draws=args.draws,
        mean_block=args.block,
        risk_free_pct=args.risk_free,
        seed=args.seed,
    )
    try:
        settings.validate()
        log = load_trades(args.trades, tz=args.tz)
    except (TradeLogError, ValueError) as exc:
        print(f"coroner: error: {exc}", file=sys.stderr)
        return 2
    report = build_report(analyse(log, settings), args.trades.name)
    out_dir = args.out if args.out is not None else Path(f"{args.trades.stem}-report")
    md_path, html_path = write_report(report, out_dir)
    print(" ".join(report.verdict))
    print(f"\nwrote {md_path}\nwrote {html_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
