"""Running reproduce twice gives identical files."""

from __future__ import annotations

import csv
import importlib.util
from pathlib import Path
from types import ModuleType

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
        reproduce.run(out / "results", out / "samples", fast=True)
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


def test_committed_tables_match_a_full_run_of_the_deterministic_parts() -> None:
    # The sample-comparison table holds seeded numbers only; the committed copy
    # must be what the code produces now.
    reproduce = load_script()
    from coroner.analysis import analyse
    from coroner.trades import load_trades

    with (ROOT / "results" / "summary.csv").open(encoding="utf-8", newline="") as handle:
        committed = list(csv.reader(handle))
    assert committed[0] == ["", "broad", "concentrated"]
    for column, name in ((1, "broad"), (2, "concentrated")):
        rows = reproduce.summary_rows(analyse(load_trades(ROOT / "samples" / f"{name}.csv")))
        assert rows == [(line[0], line[column]) for line in committed[1:]]
