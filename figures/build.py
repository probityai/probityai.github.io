# /// script
# requires-python = ">=3.11"
# dependencies = ["fonttools==4.60.1"]
# ///
"""Build every figure's current revision into figures/<name>/<rev>/.

Usage: uv run --script figures/build.py [--out DIR]
With --out the files go to DIR instead (figures/check.py builds into a scratch directory and compares).
A published revision is never rewritten: change a figure by raising its REV.
"""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import figkit as fk  # noqa: E402

MODULES = ("f1_four_verdicts", "f3_missing_not_clean")


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the current revision of every figure.")
    ap.add_argument("--out", type=Path, default=HERE)
    args = ap.parse_args()
    for name in MODULES:
        mod = importlib.import_module(name)
        for p in fk.write([make() for make in mod.FIGS], args.out, mod.REV):
            print(p.relative_to(args.out))


if __name__ == "__main__":
    main()
