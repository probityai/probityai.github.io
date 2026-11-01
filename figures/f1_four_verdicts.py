"""F1 Four verdicts: one sealed archive, checked four ways, and what the verifier prints each time.

At the left (wide layout) stands the archive: an archive box of three files with a padlock over their digest.
It is copied into four rows, one per arm of demo/four-arms.sh, and every row reads the same way, left to
right: the archive as the verifier gets it, the verifier's lens, the receipt it prints with the verdict
glyph on it, and the verdict word and exit code it prints. Loss ink marks the one thing changed in a row.
In row 2 it is one byte cell, the same size as its neighbours, and the padlock snapped open. In row 4 it is
the verifier: the same lens with a spanner gripping its rim. A missing file (row 3) is only the grey dashed
place where it would stand, so not-established never reads as a bad file or as failed. Row 4 reads the
untouched archive twice, with the old verifier and the adjusted one; both lines merge into one arrow and
both receipts are filed side by side in one tray drawn like the archive box. Words and exit codes come from
data/four-arms.toml; the row captions are the alt text, not words on the picture.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import figkit as fk

HERE = Path(__file__).resolve().parent
NAME = "f1-four-verdicts"
REV = 3
ARMS = tomllib.loads((HERE / "data/four-arms.toml").read_text())["arm"]
INTACT, BYTE, MISSING, CHANGED = ARMS
TITLE = "Four verdicts from one evidence archive"
# the alt text: each row's caption with what the verifier prints for it, from data/four-arms.toml
DESC = " ".join(
    ["One sealed archive of three files, checked four ways."]
    + [f"{a['caption']}: {a['verdict']}, exit {a['exit']}." for a in ARMS]
    + [
        "The last row reads the same archive with the old verifier and the changed one; both receipts are kept."
    ]
)
INK = {
    "check": "fg",
    "cross": "fg",
    "query": "fg",
}  # one ink for every verdict glyph: the mark's shape carries the verdict
STATE = (
    {},
    {"mark": (1, (1, 0)), "broken": True},
    {"missing": 1},
    {},
)


def _verdict(f: fk.Fig, arm, x, cy, stacked: bool) -> float:
    """The verdict word and exit code as the verifier prints them, from x, centred on cy. Returns the right edge."""
    sz = f.text_size
    cap = fk.cap_height(sz, "mono", 500)
    ex = f"exit {arm['exit']}"
    if stacked:
        f.text(x, cy - sz * 0.2, arm["verdict"], "fg", "mono", 500)
        f.text(x, cy - sz * 0.2 + sz * 1.2, ex, "muted", "mono", 500)
        return x + fk.text_width(arm["verdict"], sz, "mono", 500)
    f.text(x, cy + cap / 2, arm["verdict"], "fg", "mono", 500)
    ex_x = x + fk.text_width(arm["verdict"] + " ", sz, "mono", 500)
    f.text(ex_x, cy + cap / 2, ex, "muted", "mono", 500)
    return ex_x + fk.text_width(ex, sz, "mono", 500)


def _row(f: fk.Fig, k, bx, cy, geo, sgap, lr, sh, stacked, split) -> float:
    """One arm: the archive box centred on cy at bx, the lens, the receipt and the printed verdict.
    split is the vertical offset of row 4's two verifiers. Returns the row's right edge."""
    arm = ARMS[k]
    bw, bh = fk.box_size(3, geo, sgap)
    top = cy - bh / 2 + 6
    fk.box(f, bx, top, geo=geo, sgap=sgap, lock_r=lr * 0.8, **STATE[k])
    x = bx + bw
    lx = x + 30 + lr
    sx = lx + lr * 1.6 + 24
    tx = sx + sh * 0.74 + 26
    ink = INK[arm["glyph"]]
    if arm is not CHANGED:
        f.line(x + 6, cy, lx - lr - 2, cy, "accent", sw=3)
        fk.lens(f, lx, cy, lr)
        f.line(lx + lr + 2, cy, sx - 12, cy, "accent", sw=3)
        fk.arrow(f, sx - 4, cy, size=7)
        fk.slip(f, sx, cy, sh, arm["glyph"], ink)
        return _verdict(f, arm, tx, cy, stacked)
    # the same archive read by the old verifier (above) and the same verifier adjusted (below, a spanner on
    # it); both lines merge into one arrow, and both receipts are filed side by side in one tray
    sz = f.text_size
    rw = round(sh * 0.74, 1)
    tm, tg = 9, 8  # the tray's margin round its receipts; the gap between them
    tx0 = (
        sx + 22
    )  # the tray sits a step further right, so the merging lines clear the lens handles
    tray_w = 2 * tm + 2 * rw + tg
    mx = tx0 - 30  # where the two lines meet
    for d, v_ink in ((-1, "accent"), (1, "loss")):
        y = cy + d * split
        f.path(
            f"M{x + 6:.1f} {cy:.1f} L{x + 14:.1f} {cy:.1f} Q{x + 22:.1f} {cy:.1f} {x + 22:.1f} {cy + d * 8:.1f} "
            f"L{x + 22:.1f} {y - d * 8:.1f} Q{x + 22:.1f} {y:.1f} {x + 30:.1f} {y:.1f} L{lx - lr - 2:.1f} {y:.1f}",
            stroke=v_ink,
            sw=3,
        )
        fk.lens(f, lx, y, lr, stroke=v_ink)
        f.path(
            f"M{lx + lr + 2:.1f} {y:.1f} L{mx - 22:.1f} {y:.1f} Q{mx:.1f} {y:.1f} {mx:.1f} {cy - d * 2:.1f}",
            stroke=v_ink,
            sw=3,
        )
    # the spanner grips the changed verifier's rim at its lower left; the rim shows through the jaw
    yb = cy + split
    fk.wrench(f, lx - lr * 0.7071, yb + lr * 0.7071, s=lr * 2.1)
    f.circle(lx, yb, lr, stroke="loss", sw=4)
    f.line(mx, cy, tx0 - 12, cy, "fg", sw=3)
    fk.arrow(f, tx0 - 4, cy, "fg", size=7)
    # the tray: a back wall behind the receipts, a front panel over their feet with a hand hole
    top = cy - sh / 2
    panel = cy + sh / 2 - 12
    foot = cy + sh / 2 + 8
    f.path(
        f"M{tx0:.1f} {panel:.1f} L{tx0:.1f} {top + sh * 0.35:.1f} L{tx0 + tray_w:.1f} {top + sh * 0.35:.1f} "
        f"L{tx0 + tray_w:.1f} {panel:.1f}",
        stroke="rule",
        sw=2.5,
        join="round",
    )
    for k2, r_ink in ((0, "accent"), (1, "loss")):
        fk.slip(f, tx0 + tm + k2 * (rw + tg), cy - 4, sh, arm["glyph"], ink, ink=r_ink)
    f.rect(tx0, panel, tray_w, foot - panel, fill="tile", stroke="rule", rx=5, sw=2.5)
    hw = min(40, tray_w * 0.3)
    f.rect(
        tx0 + tray_w / 2 - hw / 2,
        (panel + foot) / 2 - 4,
        hw,
        8,
        fill="card",
        stroke="rule",
        rx=4,
        sw=2,
    )
    vx = tx0 + tray_w + 26
    if (
        stacked
    ):  # narrow: one block, since both receipts print the same verdict and exit code
        return _verdict(f, arm, vx, cy, True)
    right = 0.0
    for d in (-1, 1):
        right = max(right, _verdict(f, arm, vx, cy + d * sz * 0.75, False))
    return right


def wide() -> fk.Fig:
    W, pad = 1280, fk.PAD
    geo, sgap = (3, 3, 11, 4, 10), 10
    bw, bh = fk.box_size(3, geo, sgap)
    f = fk.Fig(NAME, "wide", W, 0, TITLE, DESC)
    pitch, split = bh + 52, 44
    c0 = 36 + bh / 2
    centres = [c0 + k * pitch for k in range(3)] + [c0 + 3 * pitch + split]
    # the one archive, at the left, copied into every row
    sy = (centres[0] + centres[-1]) / 2
    fk.box(f, pad, sy - bh / 2 + 6, geo=geo, sgap=sgap, lock_r=16)
    rx = pad + bw + 96
    fx = pad + bw + 10
    for cy in centres:
        f.path(
            f"M{fx:.1f} {sy:.1f} C{fx + 50:.1f} {sy:.1f} {rx - 70:.1f} {cy:.1f} {rx - 16:.1f} {cy:.1f}",
            stroke="rule",
            sw=2.5,
        )
        fk.arrow(f, rx - 6, cy, "rule", size=7)
    for k, cy in enumerate(centres):
        right = _row(f, k, rx, cy, geo, sgap, 20, 62, False, split)
        assert right <= W - pad, (k, right)
    f.height = round(centres[-1] + split + 62 / 2 + 8 + 28)
    return f


def narrow() -> fk.Fig:
    W, pad = 720, fk.PAD
    geo, sgap = (3, 3, 9, 4, 8), 8
    _, bh = fk.box_size(3, geo, sgap)
    f = fk.Fig(NAME, "narrow", W, 0, TITLE, DESC)
    split = 50
    pitch = max(bh, 2 * f.text_size * 1.3) + 46
    c0 = 30 + bh / 2
    centres = [c0 + k * pitch for k in range(3)] + [c0 + 3 * pitch + split]
    for k, cy in enumerate(centres):
        right = _row(f, k, pad, cy, geo, sgap, 18, 58, True, split)
        assert right <= W - pad, (k, right)
    f.height = round(centres[-1] + split + 58 / 2 + 8 + 28)
    return f


FIGS = (wide, narrow)
