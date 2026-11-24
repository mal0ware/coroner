"""Download the two Ken French daily files the real trade logs are built from.

    uv run python scripts/fetch_data.py

The files go into data/, which git ignores. They are free and need no key:

- F-F_Research_Data_Factors_daily_CSV.zip  (Mkt-RF and RF, for the US market)
- 10_Industry_Portfolios_daily_CSV.zip     (ten value-weighted industry portfolios)

The library rebuilds its files from each CRSP release, so the SHA-256 of each file is
printed and written to results/data_used.md by scripts/reproduce.py.
"""

from __future__ import annotations

import hashlib
import urllib.request
from pathlib import Path

BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
FILES = (
    "F-F_Research_Data_Factors_daily_CSV.zip",
    "10_Industry_Portfolios_daily_CSV.zip",
)
DATA = Path(__file__).resolve().parent.parent / "data"


def fetch(name: str, directory: Path) -> Path:
    """Download one file into ``directory`` and return its path."""
    request = urllib.request.Request(BASE + name, headers={"User-Agent": "research-script/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = response.read()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_bytes(payload)
    return path


if __name__ == "__main__":
    for name in FILES:
        path = fetch(name, DATA)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        print(f"wrote {path} ({path.stat().st_size:,} bytes, sha256 {digest})")
