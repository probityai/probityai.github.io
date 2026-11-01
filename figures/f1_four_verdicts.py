"""F1 Four verdicts: one sealed archive under four conditions gives four verdicts (RULING section 9).

Rows: intact, one byte changed, one required artifact missing, the same archive through a changed checker.
The verifier's route is accent in every row. A refused row ends in a T-bar at the gate, with nothing drawn
on to the verdict. The changed-checker row forks before two gates (the changed one notched), never rejoins,
and ends in two single checks beside one verdict word. Words and exit codes come from data/four-arms.toml.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import figkit as fk

HERE = Path(__file__).resolve().parent
NAME = "f1-four-verdicts"
REV = 1
ARMS = tomllib.loads((HERE / "data/four-arms.toml").read_text())["arm"]
TITLE = "Four verdicts from one evidence archive"
DESC = (
    "The same sealed archive of three files passes a verifier four times. Intact archive: verified, exit 0. "
    "One byte changed: the seal is broken and the verifier stops it: failed, exit 2. A required file "
    "missing: the verifier stops it: not-established, exit 3. A changed verifier: the route forks through "
    "the old and the changed verifier and both say verified, exit 0, and both records are kept."
)


def _row(f, i, arm, cy, ax, geo, gx, vx, layout):
    sz = f.text_size
    sw_, sh_ = fk.sheet_size(*geo)
    ah = 24 + sh_
    aw, _ = fk.archive(
        f, ax, cy - ah / 2,
        missing=1 if i == 2 else None,
        mark=(1, (2, 1)) if i == 1 else None,
        geo=geo, sgap=14 if layout == "wide" else 10,
        broken=(i == 1),
    )
    x0 = ax + aw
    gsize = 40 if layout == "wide" else 46
    gy = cy - gsize / 2
    if i in (1, 2):
        # stopped at the gate: route runs to a T-bar in front of the first post
        f.line(x0, cy, gx - 14, cy, "accent", sw=3)
        f.line(gx - 12, cy - 15, gx - 12, cy + 15, "loss", sw=4)
        fk.gate(f, gx, cy, h=56, stroke="accent")
        f.glyph(arm["glyph"], vx, gy, gsize, "fg")
    elif i == 3:
        dy = 30 if layout == "wide" else 34
        fx = x0 + (gx - x0) * 0.35
        f.line(x0, cy, fx, cy, "accent", sw=3)
        for k, sgn in enumerate((-1, 1)):
            y = cy + sgn * dy
            f.path(f"M{fx:.1f} {cy:.1f} C{fx + 18:.1f} {cy:.1f} {fx + 6:.1f} {y:.1f} {fx + 26:.1f} {y:.1f} L{vx - 14:.1f} {y:.1f}",
                   stroke="accent", sw=3)
            fk.gate(f, gx, y, h=40, stroke="accent", notched=(k == 1))
            f.glyph("check", vx, y - gsize / 2 + (2 if k else -2), gsize * 0.85, "fg")
    else:
        f.line(x0, cy, vx - 14, cy, "accent", sw=3)
        fk.gate(f, gx, cy, h=56, stroke="accent")
        f.glyph(arm["glyph"], vx, gy, gsize, "fg")
    base = cy + fk.cap_height(sz, "sans", 600) / 2
    wx = vx + gsize + 12
    f.text(wx, base, arm["verdict"], "fg", "sans", 600)
    ex = f"exit {arm['exit']}"
    if layout == "wide":
        f.text(wx + fk.text_width(arm["verdict"], sz, "sans", 600) + 12, base, ex, "muted", "mono", 500)
    else:
        f.text(wx, base + sz * 1.25, ex, "muted", "mono", 500)


def wide() -> fk.Fig:
    W, sz, pad = 1280, 26, fk.PAD
    pitch = 132
    f = fk.Fig(NAME, "wide", W, 2 * pad + pitch * 4 - 20, TITLE, DESC)
    capw = max(fk.text_width(a["caption"], sz) for a in ARMS)
    wordw = max(fk.text_width(a["verdict"], sz, "sans", 600) + 12 + fk.text_width(f"exit {a['exit']}", sz, "mono", 500) for a in ARMS)
    vx = W - pad - wordw - 34 - 12
    ax = pad + capw + 32
    gx = vx - 70
    for i, a in enumerate(ARMS):
        cy = pad + i * pitch + (pitch - 20) / 2
        f.text(pad, cy + fk.cap_height(sz) / 2, a["caption"], "fg")
        _row(f, i, a, cy, ax, (4, 3, 12, 5, 11), gx, vx, "wide")
    return f


def narrow() -> fk.Fig:
    W, sz, pad = 720, 34, fk.PAD
    pitch = 196
    f = fk.Fig(NAME, "narrow", W, 2 * pad + pitch * 4 - 24, TITLE, DESC)
    wordw = max(fk.text_width(a["verdict"], sz, "sans", 600) for a in ARMS)
    vx = W - pad - wordw - 40 - 12
    gx = vx - 52
    for i, a in enumerate(ARMS):
        y0 = pad + i * pitch
        f.text(pad, y0 + fk.cap_height(sz), a["caption"], "fg")
        cy = y0 + 104
        _row(f, i, a, cy, pad, (3, 3, 11, 4, 9), gx, vx, "narrow")
    return f


FIGS = (wide, narrow)
