"""F3 Missing is not clean: a report with one passage missing (RULING section 9, verdict from probity-verify).

Top: the log reader's dotted track starts at a dot as heavy as probity-verify's and drops to every passage
the report holds; from the passage before the gap it leaves on a solid arc that lands, arrowhead first, on
the passage after it, never touching the empty slot, and under that arc, over the gap, it says check, "fine".
Its track ends in the same verdict: check, "fine".
Bottom: probity-verify's lens sits under the gap, its tick reaching up into the empty page, and its route
ends in a stop bar there; its verdict follows at once: contradicted, a plain gloss, and the packet's own
reason line. The gap is a full dashed page in absent ink. The seven passages sit in one frame named
"report": one report.
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
GLOSS = "this passage is missing from the report"
FINE = "fine"            # the log reader's verdict, said over the gap it skipped and again at its end
FRAME = "report"
TITLE = "A passage missing from the report is not a clean report"
DESC = (
    "A report of seven passages with one missing. A log reader reads what the report holds, jumps over the "
    "gap without reading it and, right over the gap, says fine. probity-verify reads the report against the source capture, "
    f"halts at the gap and returns {CASE['decision']}: {GLOSS}, reason {CASE['reason']}."
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
    # the gap: a full dashed page in absent ink, the same size and fold as the passages it sits among
    fk.sheet(f, xs[HOLE], top, *geo, state="missing")
    # the log reader: a dotted track from a start dot as heavy as probity-verify's, dropping to each passage
    # the report holds; from the drop of the passage before the gap it hops on a solid arc to the drop of the
    # passage after it, so its line never touches the empty slot. Under the arc, over the gap: check, fine.
    yu = top - 40
    f.text(fk.PAD, yu - 30 - sz * 0.3, "log reader", "fg", "sans", 600)
    f.circle(fk.PAD + 6, yu, 7, fill="muted")
    x0, x1 = xs[HOLE - 1] + sw_ / 2, xs[HOLE + 1] + sw_ / 2
    # under the arc, over the gap: check and "fine" side by side, or the check stacked over the word when
    # the hop is too narrow for both on one line (the narrow layout)
    g = gsize * 0.7
    cap = fk.cap_height(sz, "sans", 600)
    fine_w = fk.text_width(FINE, sz, "sans", 600)
    fy = yu - 12
    stacked = x1 - x0 < g + 6 + fine_w + 48
    if stacked:
        g = gsize * 0.55
    inner = fy - cap - 6 - g if stacked else fy - max(cap, g)   # the top of what sits under the arc
    lift = (yu - inner + (40 if stacked else 24)) / 0.75                            # a cubic's peak is 0.75 of its control lift
    f.line(fk.PAD + 6, yu, x0, yu, "muted", sw=3, dash="3 7")
    f.line(x1, yu, col_x - 14, yu, "muted", sw=3, dash="3 7")
    f.path(f"M{x0:.1f} {yu:.1f} C{x0 + 6:.1f} {yu - lift:.1f} {x1 - 6:.1f} {yu - lift:.1f} {x1:.1f} {yu - 6:.1f}", stroke="fg", sw=3.5)
    f.path(f"M{x1:.1f} {yu:.1f} L{x1 - 7:.1f} {yu - 13:.1f} L{x1 + 7:.1f} {yu - 13:.1f} Z", fill="fg", stroke="fg", sw=1.5)
    for i, x in enumerate(xs):
        if i != HOLE:
            f.line(x + sw_ / 2, yu, x + sw_ / 2, top - 4, "muted", sw=3, dash="3 7")
    if stacked:
        f.glyph("check", hx - g / 2, inner, g, "fg")
        f.text(hx - fine_w / 2, fy, FINE, "fg", "sans", 600)
    else:
        fw = g + 6 + fine_w
        f.glyph("check", hx - fw / 2, fy - g, g, "fg")
        f.text(hx - fw / 2 + g + 6, fy, FINE, "fg", "sans", 600)
    # the log reader's verdict at the end of its track: check, fine
    f.glyph("check", col_x, yu - gsize / 2, gsize, "fg")
    f.text(col_x + gsize + 8, yu + cap / 2, FINE, "fg", "sans", 600)
    # probity-verify: a lens on the accent route reads each passage and stops under the gap, showing it;
    # the route runs on from the lens to the verdict, in the same column as the log reader's check
    yl = top + sh_ + 10 + lr + 16
    f.line(fk.PAD + 6, yl, hx - lr, yl, "accent", sw=3)
    f.circle(fk.PAD + 6, yl, 7, fill="accent")
    for x in xs[:HOLE]:
        f.line(x + sw_ / 2, yl, x + sw_ / 2, top + sh_ + 14, "accent", sw=3)
    f.line(hx, yl - lr, hx, top + sh_ - 14, "accent", sw=3)   # the verifier's tick up into the empty page
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
    f.text(rx_, ry, GLOSS, "fg")
    f.text(rx_, ry + sz * 1.35, CASE["reason"], "muted", "mono", 500)
    return max(col_x + gsize + 8 + fine_w,
               tx + fk.text_width(CASE["decision"], sz, "sans", 600),
               rx_ + max(fk.text_width(CASE["reason"], sz, "mono", 500), fk.text_width(GLOSS, sz)))


def wide() -> fk.Fig:
    f = fk.Fig(NAME, "wide", 1280, 360, TITLE, DESC)
    sz = f.text_size
    col_x = 1280 - fk.PAD - 34 - 8 - fk.text_width(FINE, f.text_size, "sans", 600)
    assert _draw(f, (3, 3, 12, 5, 11), 14, 134, col_x, 34, False) <= 1280 - fk.PAD
    return f


def narrow() -> fk.Fig:
    f = fk.Fig(NAME, "narrow", 720, 516, TITLE, DESC)
    col_x = 720 - fk.PAD - 40 - 8 - fk.text_width(FINE, f.text_size, "sans", 600)
    assert _draw(f, (2, 3, 10, 4, 7), 16, 186, col_x, 40, True, lr=26) <= 720 - fk.PAD
    return f


FIGS = (wide, narrow)
