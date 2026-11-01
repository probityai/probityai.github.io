"""F1 Four verdicts: one sealed archive, checked four ways, and what the verifier prints each time.

At the left (wide layout) stands the archive: an archive box of three files with a padlock over their digest.
It is copied into four rows, one per arm of demo/four-arms.sh, and every row reads the same way, left to
right: the archive as the verifier gets it, the verifier's lens, the receipt it prints with the verdict
glyph on it, and the verdict word and exit code it prints. Loss ink marks the one thing changed in a row.
In row 2 it is one byte cell, the same size as its neighbours, and the padlock snapped open. In row 4 it is
the verifier: an arrow in loss ink runs from the old lens down into the changed one, the same lens drawn in
loss ink with a second ring in its rim. A missing file (row 3) is only the grey dashed place where it would
stand, so not-established never reads as a bad file or as failed. Row 4 reads the untouched archive twice,
with the old verifier and the changed one; both lines merge into one arrow, and both receipts, whole with
their torn feet, stand side by side in one open tray: kept together. Words and exit codes come from
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
    # the same archive read by the old verifier (above) and by the changed verifier (below): an arrow in
    # loss ink runs from the old lens down into the changed one, which is the same lens in loss ink with a
    # second ring in its rim. Both lines merge into one arrow, and both receipts stand in one open tray.
    sz = f.text_size
    rw = round(sh * 0.74, 1)
    tm, tg = 10, 10  # the tray's margin round its receipts; the gap between them
    tx0 = sx + 22
    tray_w = 2 * tm + 2 * rw + tg
    rxs = (tx0 + tm, tx0 + tm + rw + tg)  # the two receipts' left edges
    mx = tx0 - 30  # where the two lines meet
    rcy = cy - 4  # the receipts' centre
    for k2, (d, v_ink) in enumerate(((-1, "accent"), (1, "loss"))):
        y = cy + d * split
        f.path(
            f"M{x + 6:.1f} {cy:.1f} L{x + 14:.1f} {cy:.1f} Q{x + 22:.1f} {cy:.1f} {x + 22:.1f} {cy + d * 8:.1f} "
            f"L{x + 22:.1f} {y - d * 8:.1f} Q{x + 22:.1f} {y:.1f} {x + 30:.1f} {y:.1f} L{lx - lr - 2:.1f} {y:.1f}",
            stroke=v_ink,
            sw=3,
        )
        fk.lens(f, lx, y, lr, stroke=v_ink, double=d == 1)
        # both lines run on and merge into one arrow into the tray
        f.path(
            f"M{lx + lr + 2:.1f} {y:.1f} L{mx - 22:.1f} {y:.1f} Q{mx:.1f} {y:.1f} {mx:.1f} {cy - d * 2:.1f}",
            stroke=v_ink,
            sw=3,
        )
    f.line(mx, cy, tx0 - 12, cy, "fg", sw=3)
    fk.arrow(f, tx0 - 4, cy, "fg", size=7)
    # the old lens becomes the changed one
    ax = lx - lr * 0.15
    f.line(ax, cy - split + lr + 5, ax, cy + split - lr - 14, "loss", sw=3)
    fk.arrow(f, ax, cy + split - lr - 5, "loss", size=6, direction="down")
    # the open tray under both receipts: a shallow base with low sides, the receipts whole above it
    base = rcy + sh / 2 + 7
    for k2, r_ink in ((0, "accent"), (1, "loss")):
        fk.slip(f, rxs[k2], rcy, sh, arm["glyph"], ink, ink=r_ink)
    f.path(
        f"M{tx0:.1f} {base - 16:.1f} L{tx0:.1f} {base:.1f} L{tx0 + tray_w:.1f} {base:.1f} L{tx0 + tray_w:.1f} {base - 16:.1f}",
        stroke="rule",
        sw=3,
        join="round",
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
