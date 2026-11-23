from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

import pytest

WriteCsv = Callable[..., Path]


@pytest.fixture
def write_csv(tmp_path: Path) -> WriteCsv:
    """Write a small trade log and return its path."""

    def _write(
        rows: Sequence[Sequence[str]],
        header: Sequence[str] = ("entry_time", "exit_time", "gross", "net"),
        name: str = "trades.csv",
    ) -> Path:
        path = tmp_path / name
        lines = [",".join(header)] + [",".join(row) for row in rows]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    return _write
