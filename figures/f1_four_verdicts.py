"""F1 Four verdicts: one sealed archive, checked four ways, and what the verifier prints each time.

At the left (wide layout) stands the archive: an archive box of three files with a padlock over their digest.
It is copied into four rows, one per arm of demo/four-arms.sh, and every row reads the same way, left to
right: the archive as the verifier gets it, the verifier's lens, the receipt it prints with the verdict
glyph on it, and the verdict word and exit code it prints. Loss ink marks the one thing changed in a row:
the byte (row 2, whose padlock is snapped open) or the verifier (row 4, a double-rimmed lens). A missing
file is a dashed slot in absent ink, and its question mark takes the same ink, so not-established never
reads as failed. Row 4 reads the untouched archive twice, with the old verifier and the changed one, and
both receipts are kept side by side in one tray. Words and exit codes come from data/four-arms.toml; the
row captions are the alt text, not words on the picture.
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
DESC = (
    "One sealed archive of three files, checked four ways. Intact: verified, exit 0. One byte changed, which "
    "breaks the seal: failed, exit 2. A required file missing: not-established, exit 3. The same archive "
    "read by the old verifier and by a changed verifier: both print verified, exit 0, and both receipts are "
    "kept."
)
INK = {
    "check": "fg",
    "cross": "fg",
    "query": "absent",
}  # not-established shares the missing file's ink
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
    # the same archive read by the old verifier (above) and the changed one (below); both receipts kept
    right = 0.0
    for d, v_ink, double in ((-1, "accent", False), (1, "loss", True)):
        y = cy + d * split
        f.path(
            f"M{x + 6:.1f} {cy:.1f} L{x + 14:.1f} {cy:.1f} Q{x + 22:.1f} {cy:.1f} {x + 22:.1f} {cy + d * 8:.1f} "
            f"L{x + 22:.1f} {y - d * 8:.1f} Q{x + 22:.1f} {y:.1f} {x + 30:.1f} {y:.1f} L{lx - lr - 2:.1f} {y:.1f}",
            stroke=v_ink,
            sw=3,
        )
        fk.lens(f, lx, y, lr, stroke=v_ink, double=double)
        f.line(lx + lr + 2, y, sx - 12, y, v_ink, sw=3)
        fk.arrow(f, sx - 4, y, v_ink, size=7)
        fk.slip(f, sx, y, sh, arm["glyph"], ink, ink=v_ink)
        right = max(right, _verdict(f, arm, tx, y, stacked))
    # the tray both receipts sit in: kept together
    tw = sh * 0.74
    t0, t1 = cy - split - sh / 2 - 8, cy + split + sh / 2 + 8
    f.path(
        f"M{sx - 9:.1f} {t0:.1f} L{sx - 9:.1f} {t1 - 6:.1f} Q{sx - 9:.1f} {t1:.1f} {sx - 3:.1f} {t1:.1f} "
        f"L{sx + tw + 3:.1f} {t1:.1f} Q{sx + tw + 9:.1f} {t1:.1f} {sx + tw + 9:.1f} {t1 - 6:.1f} L{sx + tw + 9:.1f} {t0:.1f}",
        stroke="fg",
        sw=3,
    )
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
