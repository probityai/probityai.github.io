"""F3 Missing is not clean: a record with one passage missing (verdict from probity-verify).

"Record" is probity-verify's own word for the stored report it checks against the source capture
(adapters/source_coverage.py: a selected span found in the source and not in the record returns
contradicted, selected_span_missing_from_record). The picture shows why the two readers disagree:

Top row: the record. Its passages stand over the source passages they came from, so every pairing rung is
straight; where the fifth passage stood, the record's frame is pinched in round the empty place. A tab on its
top edge prints report.txt, the path the packet binds for the record.
Bottom row: the source capture, all seven passages in a frame with viewfinder corners, so it reads as the
capture the record came from and not as a second record; a tab hanging from its foot prints source.html, the
path the packet binds for the capture.
probity-verify pairs every source passage with its record passage, one straight rung per pair, and a rail
runs through the rungs into its lens. The source's fifth passage is ringed in loss ink; its rung climbs in the
same ink and stops at the pinch under a stop bar: the source has the passage, the record has none to pair
with. The record's empty place is ringed in the same ink, dashed: the hole is the record's. A dot marks
where each other rung meets the rail. The lens prints a receipt with a cross in the same ink: contradicted, with the packet's reason line hung under it.
The readers' column at the right: the eye, level with the record, in the trusting reader's own ink (self),
looks left at the record alone through a cone of sight in that ink that covers the whole record, the dark
dashed cut place too, and prints a slip with a check in the same ink: fine. The lens and its contradicted
slip stand directly below it. The only words are what the readers print and the two file paths the packet
binds.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import figkit as fk

HERE = Path(__file__).resolve().parent
NAME = "f3-missing-not-clean"
REV = 3
CASE = tomllib.loads((HERE / "data/source-coverage.toml").read_text())
N, HOLE = 7, 4
FINE = "fine"  # what a reader that trusts the record concludes
TITLE = "A passage missing from the record is not a clean record"
DESC = (
    "Top: a record of seven passages with the fifth cut out and the record closed over the cut. A reader that "
    "trusts the record looks only at the record and says fine. Bottom: the source capture, all seven passages. "
    "probity-verify pairs each source passage with its passage in the record, finds the fifth has none, and "
    f"returns {CASE['decision']}, reason {CASE['reason']}. The two verdicts sit in one column."
)


def _record_frame(f: fk.Fig, x0, x1, y0, y1, hx0, hx1) -> None:
    """The record's frame from x0 to x1, top y0, foot y1, pinched shut between hx0 and hx1 (the place a
    passage was cut out): its top dips and its foot rises to meet in a narrow waist, with no mark in it."""
    r = 8
    mid = (y0 + y1) / 2
    neck = (y1 - y0) * 0.12  # half the waist's height: the frame stays one open piece through the waist
    cx = (hx0 + hx1) / 2
    d = (
        f"M{x0 + r:.1f} {y0:.1f} L{hx0:.1f} {y0:.1f} Q{cx:.1f} {y0:.1f} {cx:.1f} {mid - neck:.1f} "
        f"Q{cx:.1f} {y0:.1f} {hx1:.1f} {y0:.1f} L{x1 - r:.1f} {y0:.1f} Q{x1:.1f} {y0:.1f} {x1:.1f} {y0 + r:.1f} "
        f"L{x1:.1f} {y1 - r:.1f} Q{x1:.1f} {y1:.1f} {x1 - r:.1f} {y1:.1f} L{hx1:.1f} {y1:.1f} "
        f"Q{cx:.1f} {y1:.1f} {cx:.1f} {mid + neck:.1f} Q{cx:.1f} {y1:.1f} {hx0:.1f} {y1:.1f} "
        f"L{x0 + r:.1f} {y1:.1f} Q{x0:.1f} {y1:.1f} {x0:.1f} {y1 - r:.1f} L{x0:.1f} {y0 + r:.1f} "
        f"Q{x0:.1f} {y0:.1f} {x0 + r:.1f} {y0:.1f} Z"
    )
    f.path(d, stroke="rule", sw=2.5)


def _tab(f: fk.Fig, cx, edge, name, below) -> float:
    """A file-name tab centred on cx on a frame's edge at y=edge: standing on top of the frame, or hanging
    from its foot when below. It carries the path the packet binds (product text). Returns its far edge."""
    sz = f.text_size
    cap = fk.cap_height(sz, "mono", 500)
    w = fk.text_width(name, sz, "mono", 500) + 24
    h = cap + 16
    y = edge if below else edge - h
    f.rect(cx - w / 2, y, w, h, fill="tile", stroke="rule", rx=5, sw=2.5)
    f.text(cx, y + h / 2 + cap / 2, name, "fg", "mono", 500, anchor="middle")
    return y + h if below else y


def _draw(f: fk.Fig, geo, sgap, top, gsize, reason_below, lr) -> float:
    """Draw the figure with the record's top at top; returns the bottom of the last thing drawn."""
    sz = f.text_size
    sw_, sh_ = fk.sheet_size(*geo)
    rw = round(gsize * 1.9 * 0.74, 1)  # the receipt's width
    word_w = max(fk.text_width(w, sz, "sans", 600) for w in (FINE, CASE["decision"]))
    col_w = lr * 2.5 + 30 + rw + 16 + word_w
    gx = f.width - fk.PAD - col_w + lr * 1.25  # the readers' glyph column
    mx = gx + lr * 1.25 + 30  # the verdict marks' left edge
    tx = mx + rw + 16
    x0 = fk.PAD + 10
    xs = [x0 + i * (sw_ + sgap) for i in range(N)]
    mid = [x + sw_ / 2 for x in xs]
    cap = fk.cap_height(sz, "sans", 600)
    yr = top  # the record's top
    ys = yr + sh_ + 10 + 2 * (lr + 40)  # the source's top
    under = yr + sh_ + 10  # the record frame's foot
    fw, fh = xs[-1] + sw_ - xs[0] + 20, sh_ + 20
    rx1 = xs[0] - 10 + fw
    assert rx1 + 40 <= gx - lr * 1.25, "the rows run into the readers' column"
    # the eye's sight: a cone in the trusting reader's own ink from the eye over the record row alone, the cut
    # place lit inside it with the rest; drawn first so the record's sheets stand on it
    er = lr * 1.25
    ey = yr - 10 + fh / 2
    bl, br, bt, bb = xs[0] - 16, rx1 + 8, yr - 16, yr - 4 + fh
    f.path(
        f"M{gx - er:.1f} {ey:.1f} L{br:.1f} {bt:.1f} L{bl:.1f} {bt:.1f} L{bl:.1f} {bb:.1f} L{br:.1f} {bb:.1f} Z",
        fill="self",
        opacity=0.22,
    )
    for edge in (bt, bb):
        f.line(gx - er - 4, ey, br, edge, "self", sw=2.5)
    # the record: six passages over the source passages they came from, the fifth place pinched shut
    # where the fifth passage stood, only its dashed empty place is left inside the waist: a passage cut out
    fk.sheet(f, xs[HOLE], yr, *geo, state="missing", loud=True)
    hw5, hh5 = fk.sheet_size(*geo)
    f.rect(xs[HOLE] - 7, yr - 7, hw5 + 14, hh5 + 14, stroke="loss", rx=6, sw=3.5, dash="7 5")
    _record_frame(f, xs[0] - 10, rx1, yr - 10, yr - 10 + fh, xs[HOLE] - sgap / 2, xs[HOLE] + sw_ + sgap / 2)
    f.rect(xs[0] - 10, ys - 10, fw, fh, stroke="rule", rx=8, sw=2.5)
    # the source is a capture: viewfinder corners just outside its frame
    cl, fx0, fy0 = 16, xs[0] - 16, ys - 16
    for cx, cy, dx, dy in (
        (fx0, fy0, 1, 1),
        (fx0 + fw + 12, fy0, -1, 1),
        (fx0, fy0 + fh + 12, 1, -1),
        (fx0 + fw + 12, fy0 + fh + 12, -1, -1),
    ):
        f.path(
            f"M{cx:.1f} {cy + dy * cl:.1f} L{cx:.1f} {cy:.1f} L{cx + dx * cl:.1f} {cy:.1f}",
            stroke="fg",
            sw=3,
        )
    for i, x in enumerate(xs):
        fk.sheet(f, x, ys, *geo)
        if i != HOLE:
            fk.sheet(f, x, yr, *geo)
    # the source's fifth passage, the one the record lacks, is ringed in loss ink: it is there in the source
    sw5, sh5 = fk.sheet_size(*geo)
    f.rect(xs[HOLE] - 7, ys - 7, sw5 + 14, sh5 + 14, stroke="loss", rx=6, sw=3.5)
    # the record's tab and the source's tab name the two files the packet binds
    tcx = (xs[0] - 10 + rx1) / 2
    _tab(f, tcx, yr - 10, CASE["record_path"], below=False)
    src_foot = _tab(f, tcx, ys - 10 + fh, CASE["source_path"], below=True)
    # the eye stands in the readers' column, level with the record, and prints a slip with a check in its
    # own ink: fine
    fk.eye(f, gx, ey, er, ink="self")
    f.line(gx + er + 2, ey, mx - 12, ey, "self", sw=3)
    fk.arrow(f, mx - 4, ey, "self", size=7)
    fk.slip(f, mx, ey, gsize * 1.9, "check", "self")
    f.text(tx, ey + cap / 2, FINE, "fg", "sans", 600)
    # probity-verify pairs each source passage with its record passage, one straight rung per pair
    for i, x in enumerate(mid):
        if i == HOLE:
            # the rung climbs from the ringed source passage and finds no passage: it stops at the pinch
            # under a stop bar, all in loss ink
            stop = under + 14
            f.line(x, ys - 9, x, stop, "loss", sw=4)
            f.line(x - 26, stop, x + 26, stop, "loss", sw=7)
        else:
            f.line(x, ys - 12, x, under + 2, "accent", sw=3)
    # a rail runs through every rung and on into the lens: the lens reads the pairs the rungs make
    yv = (under + ys - 10) / 2
    f.line(mid[0], yv, gx - lr - 14, yv, "accent", sw=3)
    for i, x in enumerate(mid):
        if i != HOLE:
            f.circle(x, yv, 5, fill="accent")
    fk.arrow(f, gx - lr - 4, yv, size=7)
    fk.lens(f, gx, yv, lr)
    f.line(gx + lr + 2, yv, mx - 12, yv, "accent", sw=3)
    fk.arrow(f, mx - 4, yv, size=7)
    fk.slip(f, mx, yv, gsize * 1.9, CASE["glyph"], "loss")
    f.text(tx, yv + cap / 2, CASE["decision"], "fg", "sans", 600)
    if reason_below:
        ry = src_foot + 14 + sz
        f.text(fk.PAD - 1.5, ry, CASE["reason"], "muted", "mono", 500)
        return ry + sz * 0.6
    ry = yv + gsize * 0.95 + 14 + sz
    rx = f.width - fk.PAD - fk.text_width(CASE["reason"], sz, "mono", 500)
    assert rx > rx1 + 16, "the reason runs into the source row"
    f.text(rx, ry, CASE["reason"], "muted", "mono", 500)
    return max(ry + sz * 0.4, src_foot)


def wide() -> fk.Fig:
    f = fk.Fig(NAME, "wide", 1280, 0, TITLE, DESC)
    f.height = round(_draw(f, (3, 3, 12, 5, 11), 34, 76, 34, False, 18) + 26)
    return f


def narrow() -> fk.Fig:
    f = fk.Fig(NAME, "narrow", 720, 0, TITLE, DESC)
    # one cell column per page: seven portrait pages leave room for the verdict column in 720 units
    f.height = round(_draw(f, (1, 3, 12, 4, 7), 10, 86, 40, True, 20) + 30)
    return f


FIGS = (wide, narrow)
