"""Write the two synthetic sample trade logs into samples/.

    uv run python scripts/make_samples.py

The generator is seeded; running it again rewrites identical files.
"""

from __future__ import annotations

from pathlib import Path

from coroner.samples import write_samples

if __name__ == "__main__":
    for path in write_samples(Path(__file__).resolve().parent.parent / "samples"):
        print(f"wrote {path}")
