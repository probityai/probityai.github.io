"""F1 Four verdicts: one sealed archive, checked four ways, and what the verifier prints each time.

Two panels, one above the other, divided by a thin rule.
Panel 1 (arms 1 to 3 of demo/four-arms.sh): the archive, an archive box of three files with a padlock over
their digest, fans into three rows. Each row reads left to right: the archive as the verifier gets it, the
verifier's lens (blue, its glass ground with one bar), and the receipt it prints with the verdict glyph.
Loss ink is only for damage: in row 2 the changed byte is one byte cell in loss ink and the padlock's
shackle springs open in the same ink, and the receipt's cross takes it too. In row 3 the missing file is a dark dashed empty
place, so not-established never reads as failed.
Panel 2 (arm 4) uses the same grammar: the same archive fans into two readings, the upper by the version 1
lens, the lower by the version 2 lens (the same instrument made stronger, as the stricter verifier is). Each
reading's route runs into one open file folder, and both receipts stand in it: kept together. Each lens has
the verifier id its record carries printed beside it.
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
        f"Below: the same archive is read by verifier {ARMS[3]['verifier_ids'][0]} and by the changed verifier "
        f"{ARMS[3]['verifier_ids'][1]}. Both print {ARMS[3]['verdict']}, exit {ARMS[3]['exit']}, and both "
        "receipts are kept in one folder."
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


def _read(f: fk.Fig, x, cy, bars, lr=LR, version=0) -> float:
    """The route from an archive's right edge x through a lens with `bars` glass to a receipt's arrow tip.
    Returns the x where the receipt's left edge goes."""
    lx = x + 30 + lr
    sx = lx + lr * 1.6 + 24
    f.line(x + 6, cy, lx - lr * (1.3 if version > 1 else 1.0) - 2, cy, "accent", sw=3)
    rim = lr * (1.3 if version > 1 else 1.0)  # a later version is drawn larger (fk.lens_version)
    if version:
        fk.lens_version(f, lx, cy, lr, version)
    else:
        fk.lens(f, lx, cy, lr, bars=bars)
    f.line(lx + rim + 2, cy, sx - 12, cy, "accent", sw=3)
    fk.arrow(f, sx - 4, cy, size=7)
    return sx


def _row(f: fk.Fig, k, bx, cy, geo, sgap, stacked, lr=LR, sh=SH) -> float:
    """Panel 1: one archive at bx centred on cy, read by the verifier, which prints a receipt. Returns the right edge."""
    arm = ARMS[k]
    bw, bh = fk.box_size(3, geo, sgap)
    fk.box(f, bx, cy - bh / 2 + 6, geo=geo, sgap=sgap, lock_r=lr * 0.8, **STATE[k])
    sx = _read(f, bx + bw, cy, 0, lr, version=1)
    fk.slip(f, sx, cy, sh, arm["glyph"], INK[arm["glyph"]])
    return _verdict(f, arm, sx + round(sh * 0.74, 1) + 26, cy, stacked)


def _pair(f: Fig, x0, cy, geo, sgap, pitch, lr=LR, fan=96, ids="right") -> float:
    """Panel 2: one archive at x0 centred on cy fans, as in panel 1, into two readings: the version 1 lens on
    the upper row, the version 2 lens (the same instrument made stronger) on the lower row. Both routes run
    into one open file folder, and both receipts stand in it. The verifier id each reading's record carries
    (product text from data/four-arms.toml) is printed above the upper lens and below the lower one; where
    the line is too short (ids="outside") the ids start at the archive and the folder sits at the right edge.
    Returns the lowest y drawn."""
    bw, bh = fk.box_size(3, geo, sgap)
    rw = round(SH * 0.74, 1)
    fk.box(f, x0, cy - bh / 2 + 6, geo=geo, sgap=sgap, lock_r=lr * 0.8)
    rows = (cy - pitch / 2, cy + pitch / 2)
    rx = x0 + bw + fan
    fx = x0 + bw + 10
    for ry in rows:
        f.path(
            f"M{fx:.1f} {cy:.1f} C{fx + 50:.1f} {cy:.1f} {rx - 70:.1f} {ry:.1f} {rx - 16:.1f} {ry:.1f}",
            stroke="rule",
            sw=2.5,
        )
        fk.arrow(f, rx - 6, ry, "rule", size=7)
    ends = []
    for k, ry in enumerate(rows):
        f.line(rx - 4, ry, rx + 6, ry, "accent", sw=3)
        ends.append(_read(f, rx, ry, 0, lr, version=k + 1))
    # the receipts' place: one open folder; both routes run into it and both receipts stand in it
    sh2 = SH + 10
    rw = round(sh2 * 0.74, 1)
    g = 12
    fw = 2 * rw + 3 * g
    px = max(ends) + 34
    if ids == "outside":
        px = f.width - fk.PAD - fw - 6
    top = cy - sh2 / 2
    fh = sh2 + 18
    for e, ry, ty in zip(ends, rows, (cy - 12, cy + 12)):
        x1 = px - 12
        f.path(
            f"M{e - 12:.1f} {ry:.1f} C{(e + x1) / 2:.1f} {ry:.1f} {(e + x1) / 2:.1f} {ty:.1f} {x1:.1f} {ty:.1f}",
            stroke="accent",
            sw=3,
        )
        fk.arrow(f, px - 4, ty, size=7)
    fk.folder_back(f, px, top - 8, fw, fh)
    for k in range(2):
        fk.slip(f, px + g + k * (rw + g), cy, sh2, "check", "fg")
    fk.folder_front(f, px, top - 8, fw, fh, fh - 8 - sh2 * 0.87)  # below the checks: only the feet hide
    # the verifier id each reading's record carries, by its own lens: above the upper, below the lower
    sz = f.text_size
    cap = fk.cap_height(sz, "mono", 500)
    v1, v2 = ARMS[3]["verifier_ids"]
    tx = x0 if ids == "outside" else rx - 4
    y1 = rows[0] - lr * 1.3 - 16
    y2 = rows[1] + lr * 1.3 + 16 + cap
    f.text(tx, y1, v1, "fg", "mono", 500)
    f.text(tx, y2, v2, "fg", "mono", 500)
    for vid in (v1, v2):
        assert tx + fk.text_width(vid, sz, "mono", 500) <= f.width - fk.PAD, vid
    low = max(y2 + sz * 0.3, top - 8 + fh) + 20
    return low


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
    pitch2 = SH + 40
    c2 = rule_y + 30 + pitch2 / 2 + SH / 2 + 14
    low = _pair(f, pad, c2, geo, sgap, pitch2, fan=96 + bw)
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
    # panel 2: the same archive fans into the version 1 and version 2 readings, one folder keeps both
    pitch2 = bh + 2 * f.text_size + 40
    c2 = rule_y + 30 + f.text_size + 18 + 18 * 1.3 + pitch2 / 2
    low = _pair(f, pad, c2, geo, sgap, pitch2, 18, fan=70, ids="outside")
    f.height = round(low + 24)
    return f


FIGS = (wide, narrow)
