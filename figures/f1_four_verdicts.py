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
TITLE = "Four verdicts from one evidence archive"
# the alt text: each row's caption with what the verifier prints for it, from data/four-arms.toml
DESC = " ".join(
    ["One sealed archive of three files, checked four ways."]
    + [f"{a['caption']}: {a['verdict']}, exit {a['exit']}." for a in ARMS]
    + [
        "The intact archive is read by the verifier and, the same archive, by the changed verifier; each prints its own receipt, and both receipts are kept in one binder."
    ]
)
INK = {
    "check": "fg",
    "cross": "loss",
    "query": "fg",
}  # the cross takes the changed byte's ink: that byte is why the verifier refused
STATE = (
    {},
    {"mark": (1, (2, 0)), "broken": True},
    {"missing": 1, "loud": True},
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
    """One archive at bx centred on cy, read by a verifier that prints a receipt with its verdict.
    Row 0 is the intact archive, and it is read twice: by the verifier (blue lens, at cy) and, from the same
    archive, by the changed verifier (the same lens in dark ink with cross hairs, at cy + split). An arrow
    runs from the old lens down into the changed one. Each lens prints its own receipt, and both receipts
    are filed in one ring binder. Returns the row's right edge."""
    arm = ARMS[k]
    bw, bh = fk.box_size(3, geo, sgap)
    fk.box(f, bx, cy - bh / 2 + 6, geo=geo, sgap=sgap, lock_r=lr * 0.8, **STATE[k])
    x = bx + bw
    lx = x + 30 + lr
    rw = round(sh * 0.74, 1)
    if k != 0:
        sx = lx + lr * 1.6 + 24
        f.line(x + 6, cy, lx - lr - 2, cy, "accent", sw=3)
        fk.lens(f, lx, cy, lr)
        f.line(lx + lr + 2, cy, sx - 12, cy, "accent", sw=3)
        fk.arrow(f, sx - 4, cy, size=7)
        fk.slip(f, sx, cy, sh, arm["glyph"], INK[arm["glyph"]])
        return _verdict(f, arm, sx + rw + 26, cy, stacked)
    changed = ARMS[3]
    y2 = cy + split
    # the same archive feeds both verifiers: one line straight on, one dropping to the changed verifier
    f.line(x + 6, cy, lx - lr - 2, cy, "accent", sw=3)
    f.path(
        f"M{x + 6:.1f} {cy:.1f} L{x + 12:.1f} {cy:.1f} Q{x + 20:.1f} {cy:.1f} {x + 20:.1f} {cy + 8:.1f} "
        f"L{x + 20:.1f} {y2 - 8:.1f} Q{x + 20:.1f} {y2:.1f} {x + 28:.1f} {y2:.1f} L{lx - lr - 2:.1f} {y2:.1f}",
        stroke="fg",
        sw=3,
    )
    fk.lens(f, lx, cy, lr)
    fk.lens(f, lx, y2, lr, stroke="fg", reticle=True)
    # the old verifier becomes the changed one
    ax = lx
    f.line(ax, cy + lr + 6, ax, y2 - lr - 12, "fg", sw=3)
    fk.arrow(f, ax, y2 - lr - 3, "fg", size=6, direction="down")
    # one ring binder holds both receipts, each fed by its own lens
    bnx = lx + lr * 1.6 + 30
    bnw = rw + 2 * 16 + 18
    bny = cy - sh / 2 - 12
    bnh = split + sh + 24
    fk.binder(f, bnx, bny, bnw, bnh)
    sx = bnx + 34
    for y, ink, a in ((cy, "accent", arm), (y2, "fg", changed)):
        f.line(lx + lr + 2, y, bnx - 10, y, ink, sw=3)
        fk.arrow(f, bnx - 2, y, ink, size=7)
        fk.slip(f, sx, y, sh, a["glyph"], INK[a["glyph"]], ink=ink)
    vx = bnx + bnw + 6 + 24
    if stacked:
        return max(_verdict(f, arm, vx, cy, True), _verdict(f, changed, vx, y2, True))
    return max(_verdict(f, arm, vx, cy, False), _verdict(f, changed, vx, y2, False))


def wide() -> fk.Fig:
    W, pad = 1280, fk.PAD
    geo, sgap = (3, 3, 11, 4, 10), 10
    bw, bh = fk.box_size(3, geo, sgap)
    f = fk.Fig(NAME, "wide", W, 0, TITLE, DESC)
    pitch, split = bh + 52, 96
    c0 = 36 + bh / 2
    centres = [c0, c0 + split + pitch, c0 + split + 2 * pitch]
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
    f.height = round(centres[-1] + bh / 2 + 34)
    return f


def narrow() -> fk.Fig:
    W, pad = 720, fk.PAD
    geo, sgap = (3, 3, 9, 4, 8), 8
    _, bh = fk.box_size(3, geo, sgap)
    f = fk.Fig(NAME, "narrow", W, 0, TITLE, DESC)
    split = 100
    pitch = max(bh, 2 * f.text_size * 1.3) + 46
    c0 = 30 + bh / 2
    centres = [c0, c0 + split + pitch, c0 + split + 2 * pitch]
    for k, cy in enumerate(centres):
        right = _row(f, k, pad, cy, geo, sgap, 18, 58, True, split)
        assert right <= W - pad, (k, right)
    f.height = round(centres[-1] + bh / 2 + 34)
    return f


FIGS = (wide, narrow)
