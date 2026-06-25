"""
Module `paths`

Central filesystem locations for the `cma` package.

`DATA_DIR` points at the top-level `data/` folder (a sibling of `src/`), so data
files are always found by absolute path regardless of the current working
directory. This file lives at ``<repo>/src/cma/paths.py``; ``parents[2]`` is the
repo root.
"""
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
