"""Running reproduce twice gives identical files."""

from __future__ import annotations

import csv
import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parent.parent


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("reproduce", ROOT / "scripts" / "reproduce.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def snapshot(directory: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(directory)): path.read_bytes()
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def test_reproduce_twice_is_identical(tmp_path: Path) -> None:
    reproduce = load_script()
    runs = []
    for name in ("one", "two"):
        out = tmp_path / name
        reproduce.run(out / "results", out / "samples", ROOT / "logs", fast=True)
        runs.append(snapshot(out))
    assert runs[0] == runs[1]
    expected = {
        "summary.csv",
        "summary.md",
        "barrier_check.csv",
        "barrier_check.md",
        "headline.png",
        "report.md",
        "report.html",
    }
    assert expected <= {Path(name).name for name in runs[0]}


def _committed(path: Path) -> list[list[str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.reader(handle))


def test_committed_tables_match_a_full_run_of_the_deterministic_parts() -> None:
    # The summary tables hold seeded numbers only; the committed copies must be
    # what the code produces now from the committed logs.
    reproduce = load_script()
    from coroner.analysis import analyse
    from coroner.trades import load_trades

    for table, directory, names in (
        (ROOT / "results" / "summary.csv", ROOT / "logs", reproduce.REAL_LOGS),
        (
            ROOT / "results" / "synthetic" / "summary.csv",
            ROOT / "samples",
            ("broad", "concentrated"),
        ),
    ):
        committed = _committed(table)
        assert committed[0] == ["", *names]
        for column, name in enumerate(names, start=1):
            rows = reproduce.summary_rows(analyse(load_trades(directory / f"{name}.csv")))
            assert rows == [(line[0], line[column]) for line in committed[1:]]


DATA = ROOT / "data"


@pytest.mark.skipif(
    not (DATA / "10_Industry_Portfolios_daily_CSV.zip").is_file(),
    reason="Ken French files not downloaded (scripts/fetch_data.py)",
)
def test_committed_logs_match_the_downloaded_data(tmp_path: Path) -> None:
    # Fails after the library revises its history; rerun reproduce then.
    from coroner import strategies

    for name, trades in strategies.build_logs(DATA).items():
        strategies.write_log(trades, tmp_path / f"{name}.csv")
        assert (tmp_path / f"{name}.csv").read_bytes() == (
            ROOT / "logs" / f"{name}.csv"
        ).read_bytes()
