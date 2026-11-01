"""F1 Four verdicts: one sealed archive, checked four ways, and what the verifier prints each time.

Two panels, one above the other, divided by a thin rule.
Panel 1 (arms 1 to 3 of demo/four-arms.sh): the archive, an archive box of three files with a padlock over
their digest, fans into three rows. Each row reads left to right: the archive as the verifier gets it, the
verifier's lens (blue, its glass ground with one bar), and the receipt it prints with the verdict glyph.
Loss ink is only for damage: in row 2 the changed byte is a larger tilted cell with a crack to the sprung
shackle, and the receipt's cross takes the same ink. In row 3 the missing file is a dark dashed slot holding
the query mark the receipt prints, so not-established never reads as failed.
Panel 2 (arm 4) is a time strip, read left to right. First the archive is read by the verifier and its
receipt is printed. Then the same archive (the two drawings are tied by an equals bracket underneath) is
read by the same lens with its glass swapped: the old one-bar glass falls out below, dashed, and the lens
now holds a two-bar glass. It prints a second receipt. One ring binder at the end of the strip takes both
receipts: the first arrives by a long arc over the second reading, the second directly. Kept together.
Words and exit codes come from data/four-arms.toml; the row captions are the alt text, not words on the picture.
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
    + [f"{a['caption']}: {a['verdict']}, exit {a['exit']}." for a in ARMS[:3]]
    + [
        "Below, over time: the same archive is read by the verifier, then by the verifier with its lens glass "
        f"swapped. Both print {ARMS[3]['verdict']}, exit {ARMS[3]['exit']}, and both receipts are kept in one binder."
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
LR, SH = 20, 62  # lens radius, receipt height


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


def _read(f: fk.Fig, x, cy, bars, lr=LR) -> float:
    """The route from an archive's right edge x through a lens with `bars` glass to a receipt's arrow tip.
    Returns the x where the receipt's left edge goes."""
    lx = x + 30 + lr
    sx = lx + lr * 1.6 + 24
    f.line(x + 6, cy, lx - lr - 2, cy, "accent", sw=3)
    fk.lens(f, lx, cy, lr, bars=bars)
    f.line(lx + lr + 2, cy, sx - 12, cy, "accent", sw=3)
    fk.arrow(f, sx - 4, cy, size=7)
    return sx


def _row(f: fk.Fig, k, bx, cy, geo, sgap, stacked, lr=LR, sh=SH) -> float:
    """Panel 1: one archive at bx centred on cy, read by the verifier, which prints a receipt. Returns the right edge."""
    arm = ARMS[k]
    bw, bh = fk.box_size(3, geo, sgap)
    fk.box(f, bx, cy - bh / 2 + 6, geo=geo, sgap=sgap, lock_r=lr * 0.8, **STATE[k])
    sx = _read(f, bx + bw, cy, 0, lr)
    fk.slip(f, sx, cy, sh, arm["glyph"], INK[arm["glyph"]])
    return _verdict(f, arm, sx + round(sh * 0.74, 1) + 26, cy, stacked)


def _swap(f: fk.Fig, x, cy, lr=LR) -> tuple[float, float]:
    """The same route as _read, but the lens's glass has been swapped: the old one-bar glass lies below the
    lens, dashed, with a curved arrow showing it came out; the lens holds a two-bar glass.
    Returns (receipt x, lowest y drawn)."""
    lx = x + 30 + lr
    sx = _read(f, x, cy, 0, lr)
    fk.wrench(f, lx, cy, lr, angle_deg=-75.0)
    return sx, cy + lr * 1.6


def _strip(f: fk.Fig, x0, cy, geo, sgap, right) -> float:
    """Panel 2, wide: the time strip. Returns the lowest y drawn."""
    bw, bh = fk.box_size(3, geo, sgap)
    rw = round(SH * 0.74, 1)
    top = cy - bh / 2 + 6
    # first reading
    fk.box(f, x0, top, geo=geo, sgap=sgap, lock_r=LR * 0.8)
    s1 = _read(f, x0 + bw, cy, 0)
    fk.slip(f, s1, cy, SH, "check", "fg")
    # then: a long dotted arrow on to the second reading of the same archive
    bnw = 16 + 18 + 2 * rw + 14 + 16
    x2 = right - bnw - 8 - (LR * 1.6 + 24 + 30 + LR) - bw  # the second archive, so the binder ends at right
    t0 = s1 + rw + 22
    f.line(t0, cy, x2 - 22, cy, "rule", sw=2.5, dash="2 9")
    fk.arrow(f, x2 - 12, cy, "rule", size=7)
    fk.box(f, x2, top, geo=geo, sgap=sgap, lock_r=LR * 0.8)
    s2, low = _swap(f, x2 + bw, cy)
    # the binder takes both receipts: the second straight on, the first by an arc over the second reading
    bnx = s2 + 8
    bny, bnh = cy - SH / 2 - 14, SH + 28
    fk.binder(f, bnx, bny, bnw, bnh)
    k1 = bnx + 34
    fk.slip(f, k1, cy, SH, "check", "fg")
    fk.slip(f, k1 + rw + 14, cy, SH, "check", "fg")
    ay = cy - LR * 5.9 - 10
    ex = k1 + rw / 2
    f.path(
        f"M{s1 + rw / 2:.1f} {cy - SH / 2 - 6:.1f} Q{s1 + rw / 2:.1f} {ay:.1f} {s1 + rw / 2 + 40:.1f} {ay:.1f} "
        f"L{ex - 40:.1f} {ay:.1f} Q{ex:.1f} {ay:.1f} {ex:.1f} {bny - 14:.1f}",
        stroke="rule",
        sw=2.5,
    )
    fk.arrow(f, ex, bny - 4, "rule", size=7, direction="down")
    # the two drawings are one archive: an equals bracket ties their feet
    by = top + bh + 12
    m1, m2 = x0 + bw / 2, x2 + bw / 2
    mid = (m1 + m2) / 2
    f.path(f"M{m1:.1f} {by:.1f} L{m1:.1f} {by + 14:.1f} L{mid - 18:.1f} {by + 14:.1f}", stroke="rule", sw=2.5)
    f.path(f"M{m2:.1f} {by:.1f} L{m2:.1f} {by + 14:.1f} L{mid + 18:.1f} {by + 14:.1f}", stroke="rule", sw=2.5)
    f.line(mid - 9, by + 9, mid + 9, by + 9, "fg", sw=3.5)
    f.line(mid - 9, by + 19, mid + 9, by + 19, "fg", sw=3.5)
    return max(low, by + 22)


def wide() -> fk.Fig:
    W, pad = 1280, fk.PAD
    geo, sgap = (3, 3, 11, 4, 10), 10
    bw, bh = fk.box_size(3, geo, sgap)
    f = fk.Fig(NAME, "wide", W, 0, TITLE, DESC)
    pitch = bh + 40
    c0 = 30 + bh / 2
    centres = [c0, c0 + pitch, c0 + 2 * pitch]
    sy = centres[1]
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
        right = _row(f, k, rx, cy, geo, sgap, False)
        assert right <= W - pad, (k, right)
    rule_y = centres[-1] + bh / 2 + 30
    f.line(pad, rule_y, W - pad, rule_y, "rule", sw=1.5)
    c2 = rule_y + 140
    low = _strip(f, pad, c2, geo, sgap, W - pad)
    f.height = round(low + 24)
    return f


def narrow() -> fk.Fig:
    W, pad = 720, fk.PAD
    geo, sgap = (3, 3, 9, 4, 8), 8
    bw, bh = fk.box_size(3, geo, sgap)
    f = fk.Fig(NAME, "narrow", W, 0, TITLE, DESC)
    pitch = max(bh, 2 * f.text_size * 1.3) + 46
    c0 = 30 + bh / 2
    centres = [c0, c0 + pitch, c0 + 2 * pitch]
    for k, cy in enumerate(centres):
        right = _row(f, k, pad, cy, geo, sgap, True, 18, 58)
        assert right <= W - pad, (k, right)
    rule_y = centres[-1] + bh / 2 + 30
    f.line(pad, rule_y, W - pad, rule_y, "rule", sw=1.5)
    # panel 2 stacked: the first reading, then below it the same archive read with the swapped glass;
    # one binder at the right takes both receipts
    rw = round(SH * 0.74, 1)
    a = rule_y + 40 + bh / 2
    b = a + bh + 70
    fk.box(f, pad, a - bh / 2 + 6, geo=geo, sgap=sgap, lock_r=LR * 0.8)
    s1 = _read(f, pad + bw, a, 0)
    fk.box(f, pad, b - bh / 2 + 6, geo=geo, sgap=sgap, lock_r=LR * 0.8)
    s2, low = _swap(f, pad + bw, b)
    bnx = max(s1, s2) + 8
    bnw = 16 + 18 + rw + 16
    fk.binder(f, bnx, a - SH / 2 - 14, bnw, b - a + SH + 28)
    for y in (a, b):
        fk.slip(f, bnx + 34, y, SH, "check", "fg")
    assert bnx + bnw + 6 <= W - pad
    f.height = round(max(low, b + SH / 2 + 20) + 24)
    return f


FIGS = (wide, narrow)
