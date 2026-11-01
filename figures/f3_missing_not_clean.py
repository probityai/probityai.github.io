"""F3 Missing is not clean: a report with one passage missing (RULING section 9, verdict from probity-verify).

Top: the log reader's dotted route drops to every passage the report holds; at the gap it leaves the page
on a tall solid arc that lands, arrowhead first, on the next passage: it jumps the hole without looking,
and its route ends in a check and "fine".
Bottom: probity-verify's lens reads the report against the source capture and halts under the gap: its
route ends in a stop bar there, and its verdict follows at once: contradicted, the packet's own reason
line, and a plain gloss of that reason. The seven passages sit in one frame named "report": one report.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import figkit as fk

HERE = Path(__file__).resolve().parent
NAME = "f3-missing-not-clean"
REV = 2
CASE = tomllib.loads((HERE / "data/source-coverage.toml").read_text())
N, HOLE = 7, 4
GLOSS = "the selected passage is not in the report"
FINE = "fine"            # the log reader's verdict, in its own muted ink
FRAME = "report"
TITLE = "A passage missing from the report is not a clean report"
DESC = (
    "A report of seven passages with one missing. A log reader reads what the report holds, jumps over the "
    "gap without reading it and ends in a check: fine. probity-verify reads the report against the source capture, halts at the gap "
    f"and returns {CASE['decision']}, reason {CASE['reason']}: {GLOSS}."
)


def _draw(f, geo, sgap, top, col_x, gsize, reason_below, lr=20):
    sz = f.text_size
    x_strip = fk.PAD + fk.text_width(FRAME, sz, "sans", 600) + 30
    sw_, sh_ = fk.sheet_size(*geo)
    xs = [x_strip + i * (sw_ + sgap) for i in range(N)]
    # one frame round the seven passages: they are one report
    f.rect(xs[0] - 10, top - 10, xs[-1] + sw_ - xs[0] + 20, sh_ + 20, stroke="rule", rx=8, sw=2)
    f.text(fk.PAD, top + sh_ / 2 + fk.cap_height(sz, "sans", 600) / 2, FRAME, "muted", "sans", 600)
    for i, x in enumerate(xs):
        if i != HOLE:
            fk.sheet(f, x, top, *geo)
    hx = xs[HOLE] + sw_ / 2
    # the gap: an empty slot marked only by dashed corner brackets, never a sheet outline
    k = sw_ * 0.28
    for cx_, sx in ((xs[HOLE], 1), (xs[HOLE] + sw_, -1)):
        for cy_, sy in ((top, 1), (top + sh_, -1)):
            f.path(f"M{cx_:.1f} {cy_ + sy * k:.1f} L{cx_:.1f} {cy_:.1f} L{cx_ + sx * k:.1f} {cy_:.1f}",
                   stroke="loss", sw=3)
    # the log reader: a dotted route that drops to each passage the report holds; at the gap it jumps on a
    # tall solid arc that lands, arrowhead first, past the hole. Nothing drops into the gap.
    yu = top - 40
    f.text(fk.PAD, yu - 30 - sz * 0.3, "log reader", "fg", "sans", 600)
    f.circle(fk.PAD + 6, yu, 6, fill="rule")
    hop = sw_ / 2 + sgap / 2 + 4
    lift = 30 + sz * 0.15
    x0, x1 = hx - hop, hx + hop
    f.line(fk.PAD + 6, yu, x0, yu, "rule", sw=2.5, dash="3 6")
    f.line(x1 + 8, yu, col_x - 14, yu, "rule", sw=2.5, dash="3 6")
    f.path(f"M{x0:.1f} {yu:.1f} C{x0 + hop * 0.15:.1f} {yu - lift * 1.3:.1f} {x1 - hop * 0.15:.1f} {yu - lift * 1.3:.1f} {x1:.1f} {yu - 4:.1f}",
           stroke="fg", sw=3.5)
    f.path(f"M{x1 + 3:.1f} {yu + 2:.1f} L{x1 - 9:.1f} {yu - 4:.1f} L{x1 + 1:.1f} {yu - 13:.1f} Z", fill="fg", stroke="fg", sw=1.5)
    for i, x in enumerate(xs):
        if i != HOLE:
            f.line(x + sw_ / 2, yu, x + sw_ / 2, top - 4, "rule", sw=2.5, dash="3 6")
    f.glyph("check", col_x, yu - gsize / 2, gsize, "muted")
    f.text(col_x + gsize + 8, yu + fk.cap_height(sz, "sans", 600) / 2, FINE, "muted", "sans", 600)
    # probity-verify: a lens on the accent route reads each passage and stops under the gap, showing it;
    # the route runs on from the lens to the verdict, in the same column as the log reader's check
    yl = top + sh_ + 10 + lr + 16
    f.line(fk.PAD + 6, yl, hx - lr, yl, "accent", sw=3)
    f.circle(fk.PAD + 6, yl, 7, fill="accent")
    for x in xs[:HOLE]:
        f.line(x + sw_ / 2, yl, x + sw_ / 2, top + sh_ + 14, "accent", sw=3)
    fk.lens(f, hx, yl, lr, found="hole")
    label_y = yl + max(26, lr * 1.5 + 14) + fk.cap_height(sz, "mono", 500)   # clear of the lens handle
    f.text(fk.PAD, label_y, CASE["tool"], "fg", "mono", 500)
    # the route halts at the gap: a stop bar right of the lens, the verdict straight after it
    bx = hx + lr + 14
    f.line(bx, yl - lr, bx, yl + lr, "loss", sw=5)
    gx = bx + 16
    f.glyph(CASE["glyph"], gx, yl - gsize / 2, gsize, "fg")
    base = yl + fk.cap_height(sz, "sans", 600) / 2
    tx = gx + gsize + 12
    f.text(tx, base, CASE["decision"], "fg", "sans", 600)
    # below (narrow): the reason identifier is 673 units in a 720 card, so it starts 1.5 units inside the pad
    rx_ = fk.PAD - 1.5 if reason_below else tx
    ry = label_y + sz * 1.5 if reason_below else base + sz * 1.35
    f.text(rx_, ry, CASE["reason"], "muted", "mono", 500)
    f.text(rx_, ry + sz * 1.35, GLOSS, "fg")
    return max(col_x + gsize + 8 + fk.text_width(FINE, sz, "sans", 600),
               tx + fk.text_width(CASE["decision"], sz, "sans", 600),
               rx_ + max(fk.text_width(CASE["reason"], sz, "mono", 500), fk.text_width(GLOSS, sz)))


def wide() -> fk.Fig:
    f = fk.Fig(NAME, "wide", 1280, 360, TITLE, DESC)
    sz = f.text_size
    col_x = 1280 - fk.PAD - 34 - 8 - fk.text_width(FINE, f.text_size, "sans", 600)
    assert _draw(f, (3, 3, 12, 5, 11), 14, 134, col_x, 34, False) <= 1280 - fk.PAD
    return f


def narrow() -> fk.Fig:
    f = fk.Fig(NAME, "narrow", 720, 486, TITLE, DESC)
    col_x = 720 - fk.PAD - 40 - 8 - fk.text_width(FINE, f.text_size, "sans", 600)
    assert _draw(f, (2, 3, 9, 4, 7), 8, 156, col_x, 40, True, lr=26) <= 720 - fk.PAD
    return f


FIGS = (wide, narrow)
