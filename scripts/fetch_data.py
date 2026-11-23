"""Coroner needs no downloaded data.

The standard layout for these repositories has a fetch script. This project's
only inputs are the two synthetic logs in samples/, which
scripts/make_samples.py (and scripts/reproduce.py) generate from a fixed seed.
"""

from __future__ import annotations

if __name__ == "__main__":
    print("coroner uses no external data; run scripts/reproduce.py")
