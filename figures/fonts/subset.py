# /// script
# requires-python = ">=3.11"
# dependencies = ["fonttools==4.60.1"]
# ///
"""Cut the printable-ASCII subsets that figkit embeds from the IBM Plex masters named in SOURCES.toml.

Usage: uv run --script figures/fonts/subset.py <dir holding the three master files>
Each master is checked against its SHA-256 before it is read.
"""

import hashlib
import sys
import tomllib
from pathlib import Path
from typing import Any

from fontTools import subset
from fontTools.ttLib import TTFont

HERE = Path(__file__).resolve().parent
CHARS = "".join(chr(c) for c in range(0x20, 0x7F))


def main(masters: Path) -> None:
    for key, src in tomllib.loads((HERE / "SOURCES.toml").read_text()).items():
        path = masters / src["file"]
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != src["sha256"]:
            raise SystemExit(
                f"{key}: {path} has sha256 {digest}, SOURCES.toml pins {src['sha256']}"
            )
        opts: Any = subset.Options()
        opts.flavor = "woff"
        opts.layout_features = ["kern", "liga", "tnum"]
        opts.name_IDs = [1, 2]
        opts.hinting = False
        font = TTFont(path)
        sub = subset.Subsetter(opts)
        sub.populate(text=CHARS)
        sub.subset(font)
        font.flavor = "woff"
        font.save(HERE / src["subset"])
        print(src["subset"], (HERE / src["subset"]).stat().st_size)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: subset.py <masters dir>")
    main(Path(sys.argv[1]))
