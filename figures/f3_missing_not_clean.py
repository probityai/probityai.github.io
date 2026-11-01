"""F3 Missing is not clean: a report with one passage missing (RULING section 9, verdict from probity-verify).

Top: the log reader (an open, empty lens) reads every passage the report holds, hops over the gap and ends
in a check.
Bottom: probity-verify's lens reads the report against the source capture and halts under the gap: its
route ends in a stop bar there, and its verdict follows at once: contradicted, the packet's own reason
line, and a plain gloss of that reason. The seven passages sit in one frame: one report.
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
TITLE = "A passage missing from the report is not a clean report"
DESC = (
    "A report of seven passages with one missing. A log reader reads what the report holds, passes over the "
    "gap and ends in a check. probity-verify reads the report against the source capture, halts at the gap "
    f"and returns {CASE['decision']}, reason {CASE['reason']}: {GLOSS}."
)


def _draw(f, geo, sgap, x_strip, top, col_x, gsize, reason_below, hop_r=13, lr=20):
    sz = f.text_size
    sw_, sh_ = fk.sheet_size(*geo)
    xs = [x_strip + i * (sw_ + sgap) for i in range(N)]
    # one frame round the seven passages: they are one report
    f.rect(xs[0] - 10, top - 10, xs[-1] + sw_ - xs[0] + 20, sh_ + 20, stroke="rule", rx=8, sw=2)
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
    # the log reader: a dotted route that reads each passage the report holds and hops over the gap; its
    # instrument is an open, empty lens riding the hop
    yu = top - 40
    f.text(fk.PAD, yu - 26 - (sz * 0.3), "log reader", "fg", "sans", 600)
    f.circle(fk.PAD + 6, yu, 6, fill="rule")
    hop = sw_ / 2 + sgap / 2 + 8
    apex = yu - 17 - hop_r
    f.path(f"M{fk.PAD + 6:.1f} {yu:.1f} L{hx - hop:.1f} {yu:.1f} C{hx - hop / 2:.1f} {yu:.1f} {hx - hop / 2:.1f} {apex:.1f} {hx:.1f} {apex:.1f} "
           f"C{hx + hop / 2:.1f} {apex:.1f} {hx + hop / 2:.1f} {yu:.1f} {hx + hop:.1f} {yu:.1f} L{col_x - 14:.1f} {yu:.1f}",
           stroke="rule", sw=2.5, dash="3 6")
    for i, x in enumerate(xs):
        if i != HOLE:
            f.line(x + sw_ / 2, yu, x + sw_ / 2, top - 4, "rule", sw=2.5, dash="3 6")
    f.circle(hx, apex, hop_r, fill="card", stroke="muted", sw=2.5)
    f.line(hx + hop_r * 0.73, apex + hop_r * 0.73, hx + hop_r * 1.25, apex + hop_r * 1.25, "muted", sw=4)
    f.glyph("check", col_x, yu - gsize / 2, gsize, "muted")
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
    return max(tx + fk.text_width(CASE["decision"], sz, "sans", 600),
               rx_ + max(fk.text_width(CASE["reason"], sz, "mono", 500), fk.text_width(GLOSS, sz)))


def wide() -> fk.Fig:
    f = fk.Fig(NAME, "wide", 1280, 350, TITLE, DESC)
    sz = f.text_size
    col_x = 1280 - fk.PAD - 34
    assert _draw(f, (3, 3, 12, 5, 11), 14, 80, 124, col_x, 34, False) <= 1280 - fk.PAD
    return f


def narrow() -> fk.Fig:
    f = fk.Fig(NAME, "narrow", 720, 470, TITLE, DESC)
    col_x = 720 - fk.PAD - 40
    assert _draw(f, (2, 3, 9, 4, 7), 8, 60, 140, col_x, 40, True, hop_r=18, lr=26) <= 720 - fk.PAD
    return f


FIGS = (wide, narrow)
