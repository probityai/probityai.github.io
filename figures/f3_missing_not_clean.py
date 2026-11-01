"""F3 Missing is not clean: a record with one passage missing (verdict from probity-verify).

"Record" is probity-verify's own word for the stored report it checks against the source capture
(adapters/source_coverage.py: a selected span found in the source and not in the record returns
contradicted, selected_span_missing_from_record). The picture shows why the two readers disagree:

Top row: the record, seven passage slots in one frame, the fifth only the grey dashed place where a passage
would stand. An eye reads the record alone: its line runs along the top and looks down, one arrow each, at
every place in the record, the empty one too. Nothing in the record tells it a passage is gone, so its line
runs on to a check: fine.
Bottom row: the source capture, all seven passages in a frame with viewfinder corners, so it reads as the
capture the record came from and not as a second record. probity-verify's lens runs between the two rows,
nearer the source, and pairs every source passage with its record passage, one rung per pair. At the fifth
the rung from the source finds no passage above it: it turns to loss ink and breaks off well short of the
empty place, with a cross on its broken end.
The lens's line ends at a cross, contradicted, over the packet's reason line. The two verdicts sit in one
column. The only words are what the readers print.
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
    "Top: a record of seven passages with the fifth missing. A reader that trusts the record looks only at "
    "the record, passes the gap and says fine. Bottom: the source capture, all seven passages. probity-verify "
    "pairs each source passage with its passage in the record, finds the fifth has none, and returns "
    f"{CASE['decision']}, reason {CASE['reason']}. The two verdicts sit in one column."
)


def _draw(f: fk.Fig, geo, sgap, top, gsize, reason_below, lr) -> float:
    """Draw the figure with the record's top at top; returns the bottom of the last thing drawn.
    The two readers stand in one column at the right, each beside its verdict: the eye, whose belief is a
    check in a thought cloud, and probity-verify's lens, whose verdict is a plain cross."""
    sz = f.text_size
    sw_, sh_ = fk.sheet_size(*geo)
    words = [FINE, CASE["decision"]]
    word_w = max(fk.text_width(w, sz, "sans", 600) for w in words)
    if not reason_below:
        word_w = max(word_w, fk.text_width(CASE["reason"], sz, "mono", 500) - gsize * 2.4)
    cw, ch = gsize * 2.3, gsize * 1.7  # the thought cloud
    col_w = lr * 2 + 26 + cw + 14 + word_w
    gx = f.width - fk.PAD - col_w + lr  # the readers' glyph column
    gcx = gx + lr + 26 + cw / 2  # the verdict marks' centre column
    tx = gcx + cw / 2 + 14
    x0 = fk.PAD + 10
    xs = [x0 + i * (sw_ + sgap) for i in range(N)]
    mid = [x + sw_ / 2 for x in xs]
    assert xs[-1] + sw_ + 40 <= gx - lr, "the rows run into the readers' column"
    cap = fk.cap_height(sz, "sans", 600)
    yr = top  # the record's top
    ys = yr + sh_ + 10 + 2 * (lr + 40)  # the source's top, far enough below for the broken rung
    under = yr + sh_ + 10  # the record frame's foot
    yv = under + 0.62 * (ys - 10 - under)  # probity-verify's line, nearer the source
    yu = yr - 10 - 22  # the eye's sight line, just above the record
    fw, fh = xs[-1] + sw_ - xs[0] + 20, sh_ + 20
    for y in (yr, ys):
        f.rect(xs[0] - 10, y - 10, fw, fh, stroke="rule", rx=8, sw=2.5)
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
        fk.sheet(f, x, yr, *geo, state="missing" if i == HOLE else "present")
    # the eye reads the record alone: one unbroken sight line sweeps the whole record, over the empty place
    # as over every other, and nothing there stops it; what it concludes is a check in its thought cloud
    fk.eye(f, gx, yu, lr * 1.25)
    f.line(gx - lr - 8, yu, xs[0] + 4, yu, "fg", sw=3, dash="2 9")
    fk.arrow(f, xs[0] - 6, yu, "fg", size=7, direction="left")
    cy_ = yu - ch * 0.42
    fk.thought(f, gcx, cy_, cw, ch, (gx + lr * 0.9, yu - lr * 0.5))
    g = gsize * 0.9
    f.glyph("check", gcx - g / 2, cy_ - g / 2, g, "fg")
    f.text(tx, yu + cap / 2, FINE, "fg", "sans", 600)
    # probity-verify pairs each source passage with its record passage, one rung per pair
    for i, x in enumerate(mid):
        if i == HOLE:
            # the rung rises from the source passage, finds nothing above it, and breaks off short of the
            # empty slot: the cross sits on the broken end, never inside the slot
            gap = yv - under
            gg = min(gap * 0.36, 22)
            end = yv - gap * 0.46
            f.line(x, ys - 12, x, yv, "accent", sw=3)
            f.line(x, yv, x, end, "loss", sw=3.5)
            f.glyph("cross", x - gg / 2, end - gg - 3, gg, "loss", sw=4)
        else:
            f.line(x, ys - 12, x, yr + sh_ + 12, "accent", sw=3)
    f.line(xs[0] - 4, yv, gx - lr - 4, yv, "accent", sw=3)
    fk.lens(f, gx, yv, lr * 0.85)
    f.glyph(CASE["glyph"], gcx - gsize / 2, yv - gsize / 2, gsize, "fg")
    f.text(tx, yv + cap / 2, CASE["decision"], "fg", "sans", 600)
    if reason_below:
        ry = ys + sh_ + 16 + sz * 1.9
        f.text(fk.PAD - 1.5, ry, CASE["reason"], "muted", "mono", 500)
        return ry + sz * 0.6
    ry = yv + cap / 2 + sz * 1.45
    f.text(gcx - gsize / 2, ry, CASE["reason"], "muted", "mono", 500)
    return max(ry, ys + sh_ + 16)


def wide() -> fk.Fig:
    f = fk.Fig(NAME, "wide", 1280, 0, TITLE, DESC)
    f.height = round(_draw(f, (3, 3, 12, 5, 11), 14, 118, 34, False, 18) + 26)
    return f


def narrow() -> fk.Fig:
    f = fk.Fig(NAME, "narrow", 720, 0, TITLE, DESC)
    # one cell column per page: seven portrait pages leave room for the verdict column in 720 units
    f.height = round(_draw(f, (1, 3, 12, 4, 7), 10, 124, 40, True, 20) + 30)
    return f


FIGS = (wide, narrow)
