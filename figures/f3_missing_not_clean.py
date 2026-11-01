"""F3 Missing is not clean: a report with one passage missing (RULING section 9, verdict from probity-verify).

Top: the log reader (an open, empty lens) reads every passage the report holds, hops over the gap and ends
in a check.
Bottom: probity-verify's lens reads the report against the source capture and stops under the gap; its
route runs on to its verdict, in the same column as the log reader's check: contradicted, with the
packet's own reason line in the wide layout.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import figkit as fk

HERE = Path(__file__).resolve().parent
NAME = "f3-missing-not-clean"
REV = 1
CASE = tomllib.loads((HERE / "data/source-coverage.toml").read_text())
N, HOLE = 7, 4
TITLE = "A passage missing from the report is not a clean report"
DESC = (
    "A report of seven passages with one missing. A log reader reads what the report holds, passes over the "
    "gap and ends in a check. probity-verify reads the report against the source capture, stops at the gap "
    f"and returns {CASE['decision']}, reason {CASE['reason']}."
)


def _draw(f, geo, sgap, x_strip, top, col_x, gsize, reason):
    sz = f.text_size
    sw_, sh_ = fk.sheet_size(*geo)
    xs = [x_strip + i * (sw_ + sgap) for i in range(N)]
    for i, x in enumerate(xs):
        fk.sheet(f, x, top, *geo, state="missing" if i == HOLE else "present")
    hx = xs[HOLE] + sw_ / 2
    # the log reader: a dotted route that reads each passage the report holds and hops over the gap; its
    # instrument is an open, empty lens riding the hop
    yu = top - 40
    f.text(fk.PAD, yu - 26 - (sz * 0.3), "log reader", "fg", "sans", 600)
    f.circle(fk.PAD + 6, yu, 6, fill="rule")
    hop = sw_ / 2 + sgap / 2 + 8
    apex = yu - 30
    f.path(f"M{fk.PAD + 6:.1f} {yu:.1f} L{hx - hop:.1f} {yu:.1f} C{hx - hop / 2:.1f} {yu:.1f} {hx - hop / 2:.1f} {apex:.1f} {hx:.1f} {apex:.1f} "
           f"C{hx + hop / 2:.1f} {apex:.1f} {hx + hop / 2:.1f} {yu:.1f} {hx + hop:.1f} {yu:.1f} L{col_x - 14:.1f} {yu:.1f}",
           stroke="rule", sw=2.5, dash="3 6")
    for i, x in enumerate(xs):
        if i != HOLE:
            f.line(x + sw_ / 2, yu, x + sw_ / 2, top - 4, "rule", sw=2.5, dash="3 6")
    f.circle(hx, apex, 13, fill="card", stroke="muted", sw=2.5)
    f.line(hx + 9.5, apex + 9.5, hx + 16, apex + 16, "muted", sw=4)
    f.glyph("check", col_x, yu - gsize / 2, gsize, "muted")
    # probity-verify: a lens on the accent route reads each passage and stops under the gap, showing it;
    # the route runs on from the lens to the verdict, in the same column as the log reader's check
    lr = 20
    yl = top + sh_ + lr + 16
    f.line(fk.PAD + 6, yl, hx - lr, yl, "accent", sw=3)
    f.circle(fk.PAD + 6, yl, 7, fill="accent")
    for x in xs[:HOLE]:
        f.line(x + sw_ / 2, yl, x + sw_ / 2, top + sh_ + 4, "accent", sw=3)
    f.line(hx + lr, yl, col_x - 14, yl, "accent", sw=3)
    fk.lens(f, hx, yl, lr, found="hole")
    f.text(fk.PAD, yl + lr * 1.5 + 14 + fk.cap_height(sz, "mono", 500), CASE["tool"], "fg", "mono", 500)
    f.glyph(CASE["glyph"], col_x, yl - gsize / 2, gsize, "fg")
    base = yl + fk.cap_height(sz, "sans", 600) / 2
    f.text(col_x + gsize + 12, base, CASE["decision"], "fg", "sans", 600)
    if reason:
        f.text(col_x + gsize + 12, base + sz * 1.35, CASE["reason"], "muted", "mono", 500)


def wide() -> fk.Fig:
    f = fk.Fig(NAME, "wide", 1280, 336, TITLE, DESC)
    sz = f.text_size
    colw = 34 + 12 + fk.text_width(CASE["reason"], sz, "mono", 500)
    col_x = 1280 - fk.PAD - colw
    _draw(f, (3, 3, 12, 5, 11), 14, 80, 124, col_x, 34, True)
    return f


def narrow() -> fk.Fig:
    f = fk.Fig(NAME, "narrow", 720, 320, TITLE, DESC)
    sz = f.text_size
    colw = 40 + 12 + fk.text_width(CASE["decision"], sz, "sans", 600)
    col_x = 720 - fk.PAD - colw
    _draw(f, (2, 3, 9, 4, 7), 8, 60, 124, col_x, 40, False)
    return f


FIGS = (wide, narrow)
