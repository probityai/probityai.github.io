"""F3 Missing is not clean: a record with one passage missing (RULING section 9, verdict from probity-verify).

"Record" is probity-verify's own word for the stored report it checks against the source capture
(adapters/source_coverage.py: a selected span found in the source and not in the record returns
contradicted, selected_span_missing_from_record). The frame and the gloss both say "record", so the reason
line and the picture name one object; the upper reader is named by what it does: it trusts the record.

Top: that reader's solid track starts at a dot as heavy as probity-verify's and drops (dotted) to every
passage the record holds; from the passage before the gap it leaves on the heaviest stroke in the figure, an
arc that lands, arrowhead first, on the passage after it, never touching the empty slot, and runs on to the
verdict column: check, "fine".
Bottom: probity-verify's lens sits under the gap, its tick reaching up into the empty page, and its route
ends in a stop bar there. Its verdict sits in the same column as the upper reader's, straight under it:
cross, "contradicted", then a plain gloss and the packet's own reason line. Two readers, two verdicts, side
by side in one column. The gap is a full dashed page in absent ink. The seven passages sit in one frame named
"record": one record.
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
GLOSS = "this passage is missing from the record"
READER = (
    "reader that trusts the record"  # reads what the record holds, never the source
)
FINE = "fine"  # the trusting reader's verdict, in the verdict column above probity-verify's
FRAME = "record"
TITLE = "A passage missing from the record is not a clean record"
DESC = (
    "A record of seven passages with one missing. A reader that trusts the record reads what it holds, jumps over the "
    "gap without reading it and says fine. probity-verify reads the record against the source capture, halts at the "
    f"gap and returns {CASE['decision']}: {GLOSS}, reason {CASE['reason']}. The two verdicts sit in one column."
)


def _draw(f, geo, sgap, top, width, gsize, reason_below, lr=20):
    sz = f.text_size
    x_strip = fk.PAD + fk.text_width(FRAME, sz, "sans", 600) + 30
    sw_, sh_ = fk.sheet_size(*geo)
    xs = [x_strip + i * (sw_ + sgap) for i in range(N)]
    # the verdict column: both verdicts start at vx, one over the other; the gloss and reason line hang
    # flush under the column (wide) or under the probity-verify label (narrow), so the column is as wide as
    # the longest line it holds
    words = [FINE, CASE["decision"]]
    col_w = gsize + 12 + max(fk.text_width(w, sz, "sans", 600) for w in words)
    if not reason_below:
        col_w = max(
            col_w,
            fk.text_width(GLOSS, sz),
            fk.text_width(CASE["reason"], sz, "mono", 500),
        )
    vx = width - fk.PAD - col_w
    tx = vx + gsize + 12
    assert xs[-1] + sw_ + 36 <= vx, "the record strip runs into the verdict column"
    # one frame round the seven passages: they are one record
    f.rect(
        xs[0] - 10,
        top - 10,
        xs[-1] + sw_ - xs[0] + 20,
        sh_ + 20,
        stroke="rule",
        rx=8,
        sw=2,
    )
    f.text(
        fk.PAD,
        top + sh_ / 2 + fk.cap_height(sz, "sans", 600) / 2,
        FRAME,
        "muted",
        "sans",
        600,
    )
    for i, x in enumerate(xs):
        if i != HOLE:
            fk.sheet(f, x, top, *geo)
    hx = xs[HOLE] + sw_ / 2
    # the gap: a full dashed page in absent ink, the same size and fold as the passages it sits among
    fk.sheet(f, xs[HOLE], top, *geo, state="missing")
    # the trusting reader: a dotted track from a start dot as heavy as probity-verify's, dropping to each
    # passage the record holds; from the drop of the passage before the gap it hops on a solid arc to the
    # drop of the passage after it, so its line never touches the empty slot, and runs on to its verdict
    yu = top - 40
    x0, x1 = xs[HOLE - 1] + sw_ / 2, xs[HOLE + 1] + sw_ / 2
    peak = 44
    lift = peak / 0.75  # a cubic's peak is 0.75 of its control lift
    # the label sits over the track; where it reaches the hop (narrow) it rises clear of the arc's peak
    ly = yu - 30 - sz * 0.3
    if fk.PAD + fk.text_width(READER, sz, "sans", 600) > x0 - 8:
        ly = min(ly, yu - peak - 16)
    f.text(fk.PAD, ly, READER, "fg", "sans", 600)
    f.circle(fk.PAD + 6, yu, 7, fill="fg")
    f.line(fk.PAD + 6, yu, x0, yu, "fg", sw=3)
    f.line(x1, yu, vx - 14, yu, "fg", sw=3)
    f.path(
        f"M{x0:.1f} {yu:.1f} C{x0 + 6:.1f} {yu - lift:.1f} {x1 - 6:.1f} {yu - lift:.1f} {x1:.1f} {yu - 10:.1f}",
        stroke="fg",
        sw=5.5,
    )
    f.path(
        f"M{x1:.1f} {yu + 1:.1f} L{x1 - 10:.1f} {yu - 17:.1f} L{x1 + 10:.1f} {yu - 17:.1f} Z",
        fill="fg",
        stroke="fg",
        sw=1.5,
    )
    for i, x in enumerate(xs):
        if i != HOLE:
            f.line(x + sw_ / 2, yu, x + sw_ / 2, top - 4, "muted", sw=3, dash="3 7")
    cap = fk.cap_height(sz, "sans", 600)
    f.glyph("check", vx, yu - gsize / 2, gsize, "fg")
    f.text(tx, yu + cap / 2, FINE, "fg", "sans", 600)
    # probity-verify: a lens on the accent route reads each passage and stops under the gap, showing it;
    # a stop bar ends the route there, and its verdict stands in the column under the trusting reader's
    yl = top + sh_ + 10 + lr + 16
    f.line(fk.PAD + 6, yl, hx - lr, yl, "accent", sw=3)
    f.circle(fk.PAD + 6, yl, 7, fill="accent")
    for x in xs[:HOLE]:
        f.line(x + sw_ / 2, yl, x + sw_ / 2, top + sh_ + 14, "accent", sw=3)
    f.line(
        hx, yl - lr, hx, top + sh_ - 14, "accent", sw=3
    )  # the verifier's tick up into the empty page
    fk.lens(f, hx, yl, lr, found="hole")
    label_y = (
        yl + max(26, lr * 1.5 + 14) + fk.cap_height(sz, "mono", 500)
    )  # clear of the lens handle
    f.text(fk.PAD, label_y, CASE["tool"], "fg", "mono", 500)
    bx = hx + lr + 14
    f.line(bx, yl - lr, bx, yl + lr, "loss", sw=5)
    f.glyph(CASE["glyph"], vx, yl - gsize / 2, gsize, "fg")
    base = yl + cap / 2
    f.text(tx, base, CASE["decision"], "fg", "sans", 600)
    # below (narrow): the reason identifier is 673 units in a 720 card, so it starts 1.5 units inside the pad
    rx_ = fk.PAD - 1.5 if reason_below else vx
    ry = label_y + sz * 1.5 if reason_below else base + sz * 1.35
    f.text(rx_, ry, GLOSS, "fg")
    f.text(rx_, ry + sz * 1.35, CASE["reason"], "muted", "mono", 500)
    return max(
        tx + max(fk.text_width(w, sz, "sans", 600) for w in words),
        rx_
        + max(fk.text_width(CASE["reason"], sz, "mono", 500), fk.text_width(GLOSS, sz)),
    )


def wide() -> fk.Fig:
    f = fk.Fig(NAME, "wide", 1280, 360, TITLE, DESC)
    assert _draw(f, (3, 3, 12, 5, 11), 14, 134, 1280, 34, False) <= 1280 - fk.PAD
    return f


def narrow() -> fk.Fig:
    f = fk.Fig(NAME, "narrow", 720, 516, TITLE, DESC)
    # one cell column per page: seven portrait pages leave room for the verdict column in 720 units
    assert _draw(f, (1, 3, 12, 4, 7), 10, 186, 720, 40, True, lr=26) <= 720 - fk.PAD
    return f


FIGS = (wide, narrow)
