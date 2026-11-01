"""F3 Missing is not clean: a record with one passage missing (verdict from probity-verify).

"Record" is probity-verify's own word for the stored report it checks against the source capture
(adapters/source_coverage.py: a selected span found in the source and not in the record returns
contradicted, selected_span_missing_from_record). The picture shows why the two readers disagree:

Top row: the record. Its passages stand over the source passages they came from, so every pairing rung is
straight; where the fifth passage stood, the record's frame is pinched shut and stitched across, so the
record still reads as one closed piece. An eye at the right looks at the record alone: a translucent cone of
sight from the eye covers the whole record, the stitched pinch with the rest, and above the eye its belief is
a check in a thought cloud: fine.
Bottom row: the source capture, all seven passages in a frame with viewfinder corners, so it reads as the
capture the record came from and not as a second record. probity-verify's lens runs between the two rows
and pairs every source passage with its record passage, one straight rung per pair. The fifth rung climbs
from the source and stops at the pinch under a plum stop bar: there is no passage to pair with.
The lens prints a receipt with a cross in loss ink, contradicted, over the packet's reason line. The two
readers and their verdicts sit in one column at the right. The only words are what the readers print.
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
    passage was cut out): its top dips and its foot rises to meet in a narrow waist, stitched across."""
    r = 8
    mid = (y0 + y1) / 2
    neck = 7  # half the waist's height
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
    # stitches across the waist: the cut was sewn shut
    for k in range(-2, 3):
        y = mid + k * 9
        f.line(cx - 9, y - 3, cx + 9, y + 3, "fg", sw=2.5)


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
    yv = under + 0.55 * (ys - 10 - under)  # probity-verify's line
    fw, fh = xs[-1] + sw_ - xs[0] + 20, sh_ + 20
    rx1 = xs[0] - 10 + fw
    assert rx1 + 40 <= gx - lr * 1.25, "the rows run into the readers' column"
    # the record: six passages over the source passages they came from, the fifth place pinched shut
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
    # the eye at the right looks at the record alone: a cone of sight covers the whole record, the stitched
    # pinch with the rest; its belief is a check in the thought cloud above it
    ey = yr - 10 + fh / 2
    er = lr * 1.25
    f.path(
        f"M{gx - er - 4:.1f} {ey:.1f} L{xs[0] - 14:.1f} {yr - 16:.1f} L{xs[0] - 14:.1f} {yr - 4 + fh:.1f} Z",
        fill="rule",
        opacity=0.16,
    )
    f.path(
        f"M{xs[0] - 14:.1f} {yr - 16:.1f} L{gx - er - 4:.1f} {ey:.1f} L{xs[0] - 14:.1f} {yr - 4 + fh:.1f}",
        stroke="rule",
        sw=2,
        dash="2 7",
    )
    fk.eye(f, gx, ey, er)
    cw, ch = gsize * 2.3, gsize * 1.7
    ccx, ccy = mx + rw / 2, ey - er - ch * 0.35
    fk.thought(f, ccx, ccy, cw, ch, (gx + er * 0.5, ey - er * 0.6))
    g = gsize * 0.9
    f.glyph("check", ccx - g / 2, ccy - g / 2, g, "fg")
    f.text(tx + cw / 2 - rw / 2, ccy + cap / 2, FINE, "fg", "sans", 600)
    # probity-verify pairs each source passage with its record passage, one straight rung per pair
    for i, x in enumerate(mid):
        if i == HOLE:
            # the rung climbs from the source and finds no passage: it stops at the pinch under a stop bar
            stop = under + 14
            f.line(x, ys - 12, x, stop + 10, "accent", sw=3)
            f.line(x, stop + 10, x, stop, "absent", sw=3.5)
            f.line(x - 14, stop, x + 14, stop, "absent", sw=4)
        else:
            f.line(x, ys - 12, x, under + 2, "accent", sw=3)
    f.line(xs[0] - 4, yv, gx - lr - 4, yv, "accent", sw=3)
    fk.lens(f, gx, yv, lr)
    f.line(gx + lr + 2, yv, mx - 12, yv, "accent", sw=3)
    fk.arrow(f, mx - 4, yv, size=7)
    fk.slip(f, mx, yv, gsize * 1.9, CASE["glyph"], "loss")
    f.text(tx, yv + cap / 2, CASE["decision"], "fg", "sans", 600)
    if reason_below:
        ry = ys + sh_ + 16 + sz * 1.9
        f.text(fk.PAD - 1.5, ry, CASE["reason"], "muted", "mono", 500)
        return ry + sz * 0.6
    ry = ys + sh_ + 16 + sz * 1.6
    rx = f.width - fk.PAD - fk.text_width(CASE["reason"], sz, "mono", 500)
    f.text(rx, ry, CASE["reason"], "muted", "mono", 500)
    return ry + sz * 0.4


def wide() -> fk.Fig:
    f = fk.Fig(NAME, "wide", 1280, 0, TITLE, DESC)
    f.height = round(_draw(f, (3, 3, 12, 5, 11), 14, 56, 34, False, 18) + 26)
    return f


def narrow() -> fk.Fig:
    f = fk.Fig(NAME, "narrow", 720, 0, TITLE, DESC)
    # one cell column per page: seven portrait pages leave room for the verdict column in 720 units
    f.height = round(_draw(f, (1, 3, 12, 4, 7), 10, 70, 40, True, 20) + 30)
    return f


FIGS = (wide, narrow)
