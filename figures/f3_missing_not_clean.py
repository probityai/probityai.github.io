"""F3 Missing is not clean: a record with one passage missing (verdict from probity-verify).

"Record" is probity-verify's own word for the stored report it checks against the source capture
(adapters/source_coverage.py: a selected span found in the source and not in the record returns
contradicted, selected_span_missing_from_record). The picture shows why the two readers disagree:

Top row: the record, seven passage slots in one frame, the fifth an empty dashed slot. An eye reads the
record alone: its line runs along the top and looks down at every passage the record holds. Nothing in the
record tells it a passage is gone, so its line runs straight past the empty slot to a check: fine.
Bottom row: the source capture, all seven passages in one frame. probity-verify's lens runs between the two
rows and pairs every source passage with its record passage, one rung per pair. At the fifth the rung from
the source finds no passage above it: the rung turns to loss ink and ends in a cross inside the empty slot.
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
    """Draw the figure with the record's top at top; returns the bottom of the last thing drawn."""
    sz = f.text_size
    gx = fk.PAD + lr + 2  # the readers' glyph column
    x0 = gx + lr * 2 + 22
    sw_, sh_ = fk.sheet_size(*geo)
    xs = [x0 + i * (sw_ + sgap) for i in range(N)]
    mid = [x + sw_ / 2 for x in xs]
    words = [FINE, CASE["decision"]]
    col_w = gsize + 12 + max(fk.text_width(w, sz, "sans", 600) for w in words)
    if not reason_below:
        col_w = max(col_w, fk.text_width(CASE["reason"], sz, "mono", 500))
    vx = f.width - fk.PAD - col_w
    tx = vx + gsize + 12
    assert xs[-1] + sw_ + 30 <= vx, "the rows run into the verdict column"
    cap = fk.cap_height(sz, "sans", 600)
    yr = top  # the record's top
    ys = yr + sh_ + 10 + 2 * (lr + 20)  # the source's top
    yv = (yr + sh_ + 10 + ys - 10) / 2  # probity-verify's line, between the two frames
    yu = yr - 10 - lr - 14  # the eye's line, above the record
    for y in (yr, ys):
        f.rect(
            xs[0] - 10,
            y - 10,
            xs[-1] + sw_ - xs[0] + 20,
            sh_ + 20,
            stroke="rule",
            rx=8,
            sw=2.5,
        )
    for i, x in enumerate(xs):
        fk.sheet(f, x, ys, *geo)
        fk.sheet(f, x, yr, *geo, state="missing" if i == HOLE else "present")
    # the eye reads the record alone: down to each passage it holds, straight past the empty slot
    for i, x in enumerate(mid):
        if i != HOLE:
            f.line(x, yu + 4, x, yr - 14, "fg", sw=2.5, dash="2 6")
    fk.eye(f, gx, yu, lr)
    f.line(gx + lr + 6, yu, vx - 16, yu, "fg", sw=3)
    f.glyph("check", vx, yu - gsize / 2, gsize, "fg")
    f.text(tx, yu + cap / 2, FINE, "fg", "sans", 600)
    # probity-verify pairs each source passage with its record passage, one rung per pair
    for i, x in enumerate(mid):
        if i == HOLE:
            f.line(x, ys - 12, x, yv, "accent", sw=3)
            f.line(x, yv, x, yr + sh_ - 4, "loss", sw=3.5)
            g = sw_ * 0.62
            f.glyph("cross", x - g / 2, yr + sh_ / 2 - g / 2 - 4, g, "loss", sw=5)
        else:
            f.line(x, ys - 12, x, yr + sh_ + 12, "accent", sw=3)
    f.line(gx + lr + 4, yv, vx - 16, yv, "accent", sw=3)
    fk.lens(f, gx, yv, lr * 0.85)
    f.glyph(CASE["glyph"], vx, yv - gsize / 2, gsize, "fg")
    f.text(tx, yv + cap / 2, CASE["decision"], "fg", "sans", 600)
    if reason_below:
        ry = ys + sh_ + 10 + sz * 1.9
        f.text(fk.PAD - 1.5, ry, CASE["reason"], "muted", "mono", 500)
        return ry + sz * 0.6
    ry = yv + cap / 2 + sz * 1.45
    f.text(vx, ry, CASE["reason"], "muted", "mono", 500)
    return max(ry, ys + sh_ + 10)


def wide() -> fk.Fig:
    f = fk.Fig(NAME, "wide", 1280, 0, TITLE, DESC)
    f.height = round(_draw(f, (3, 3, 12, 5, 11), 14, 92, 34, False, 18) + 26)
    return f


def narrow() -> fk.Fig:
    f = fk.Fig(NAME, "narrow", 720, 0, TITLE, DESC)
    # one cell column per page: seven portrait pages leave room for the verdict column in 720 units
    f.height = round(_draw(f, (1, 3, 12, 4, 7), 10, 100, 40, True, 20) + 30)
    return f


FIGS = (wide, narrow)
