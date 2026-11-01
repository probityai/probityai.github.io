# /// script
# requires-python = ">=3.11"
# dependencies = ["fonttools==4.60.1"]
# ///
"""Checks every published figure file. Exit 0 only when all pass.

Usage: uv run --script figures/check.py [--base REF]

1. Freshness: the current revision rebuilt from source equals the committed files byte for byte.
2. Append-only: with --base, no file under a revision directory that exists at REF changed or vanished.
3. Per SVG: width and height equal the viewBox; every text is at least its layout's size; every painted
   element carries its colour as a presentation attribute (so a host that strips <style> still shows a
   legible light card); a title and a desc are present; no relative or external image reference.
4. Contrast: every token on the card and on the tile reaches 4.5:1 for text roles and 3:1 for marks.
"""

from __future__ import annotations

import argparse
import filecmp
import re
import subprocess
import sys
import tempfile
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
NS = "{http://www.w3.org/2000/svg}"
TEXT_ROLES = ("fg", "muted", "accent")
MARK_ROLES = ("rule", "byte", "loss", "absent", "self")


def _lum(h: str) -> float:
    c = [int(h.lstrip("#")[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    c = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contrast(a: str, b: str) -> float:
    la, lb = _lum(a), _lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def check_contrast(tokens: dict) -> list[str]:
    errs = []
    for theme in ("light", "dark"):
        t = tokens[theme]
        for bg in ("card", "tile"):
            for role in TEXT_ROLES + MARK_ROLES:
                need = 4.5 if role in TEXT_ROLES else 3.0
                got = contrast(t[role], t[bg])
                if got < need:
                    errs.append(f"contrast {theme} {role} on {bg}: {got:.2f} < {need}")
    return errs


def check_svg(path: Path, floor: int) -> list[str]:
    errs = []
    root = ET.parse(path).getroot()
    vb = root.get("viewBox", "").split()
    if len(vb) != 4 or root.get("width") != vb[2] or root.get("height") != vb[3]:
        errs.append(f"{path}: width/height {root.get('width')}x{root.get('height')} differ from viewBox {vb}")
    if root.find(f"{NS}title") is None or root.find(f"{NS}desc") is None:
        errs.append(f"{path}: missing title or desc")
    for el in root.iter():
        tag = el.tag.removeprefix(NS)
        if tag == "image" or el.get("href") or el.get("{http://www.w3.org/1999/xlink}href"):
            errs.append(f"{path}: image reference found")
        if tag == "text" and float(el.get("font-size", "0")) < floor:
            errs.append(f"{path}: text {el.text!r} at {el.get('font-size')} under {floor}")
        cls = el.get("class")
        if cls:
            for c in cls.split():
                prop = {"f": "fill", "s": "stroke"}[c[0]]
                if not el.get(prop) or el.get(prop) == "none":
                    errs.append(f"{path}: <{tag} class={c}> has no {prop} attribute to fall back on")
    return errs


def check_fresh() -> list[str]:
    errs = []
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([sys.executable, str(HERE / "build.py"), "--out", tmp], check=True, stdout=subprocess.DEVNULL)
        built = sorted(p.relative_to(tmp) for p in Path(tmp).rglob("*") if p.is_file() and "_mute" not in p.parts)
        for rel in built:
            committed = HERE / rel
            if not committed.exists():
                errs.append(f"fresh: {rel} is built but not committed")
            elif not filecmp.cmp(committed, Path(tmp) / rel, shallow=False):
                errs.append(f"fresh: {rel} differs from its rebuild (run figures/build.py)")
        revdirs = {rel.parent for rel in built}
        for d in revdirs:
            for p in (HERE / d).iterdir():
                if p.relative_to(HERE) not in built:
                    errs.append(f"fresh: {p.relative_to(HERE)} is committed but not built")
    return errs


def check_append_only(base: str) -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--name-status", f"{base}...HEAD", "--", "figures/"],
        cwd=HERE.parent, check=True, capture_output=True, text=True,
    ).stdout
    errs = []
    for line in out.splitlines():
        status, path = line.split("\t", 1)
        m = re.match(r"figures/(f\d+-[a-z-]+)/(\d+)/", path)
        if not m or status.startswith("A"):
            continue
        errs.append(f"append-only: {path} ({status}) is in a published revision; raise REV instead")
    return errs


def main() -> int:
    ap = argparse.ArgumentParser(description="Check the published figures.")
    ap.add_argument("--base", help="git ref the branch starts from; enables the append-only check")
    args = ap.parse_args()
    tokens = tomllib.loads((HERE / "tokens.toml").read_text())
    errs = check_contrast(tokens) + check_fresh()
    svgs = sorted(p for p in HERE.glob("f*-*/*/*.svg"))
    for p in svgs:
        floor = tokens["type"]["text_" + p.name.split("-")[0]]
        errs += check_svg(p, floor)
    if args.base:
        errs += check_append_only(args.base)
    for e in errs:
        print("FAIL", e)
    print(f"checked {len(svgs)} SVG files: {len(errs)} failures")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
