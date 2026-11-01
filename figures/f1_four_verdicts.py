"""F1 Four verdicts: one sealed archive travels to the verifier; each fault is drawn where it strikes
(RULING section 9).

One route carries the archive left to right (top to bottom in the narrow layout) through the verifier's
lens to its verdict: verified, exit 0. The archive's files are tied into a padlock over their digest. A
changed byte and a missing artifact strike the archive on its way to the verifier; each strike drops to
the archive as it then arrives and to the verdict the verifier prints for it. A changed byte breaks the
lock (loss ink: failed); a missing file is a dashed hole in absent ink, and its verdict's question mark
takes the same ink, so not-established never reads as failed. The changed verifier strikes at the lens:
the old lens (rule ink) and the changed one (accent) each read the archive and each drops its receipt
into one folder, side by side: both records are kept. A legend maps each exit code to its verdict.
Words and exit codes come from data/four-arms.toml.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import figkit as fk

HERE = Path(__file__).resolve().parent
NAME = "f1-four-verdicts"
REV = 2
ARMS = tomllib.loads((HERE / "data/four-arms.toml").read_text())["arm"]
INTACT, BYTE, MISSING, CHANGED = ARMS
TITLE = "Four verdicts from one evidence archive"
DESC = (
    "A sealed archive of three files travels to a verifier. Intact, it is verified, exit 0. A byte changed "
    "on the way breaks the seal: failed, exit 2. A required file lost on the way: not-established, exit 3. "
    "A changed verifier: the old verifier (v1) and the changed one (v2) both read the archive and both print "
    "verified, exit 0, and both receipts are filed side by side in one folder: both records are kept. "
    "Exit codes: 0 verified, 2 failed, 3 not-established."
)
INK = {"check": "fg", "cross": "fg", "query": "absent"}   # not-established shares the missing file's ink


def _verdict(f, arm, x, cy, gsize, exit_inline=True):
    """Glyph, verdict word and exit code with the glyph's centre at (x + gsize/2, cy). Returns the right edge."""
    sz = f.text_size
    f.glyph(arm["glyph"], x - gsize * 0.12, cy - gsize / 2, gsize, INK[arm["glyph"]])   # the glyph box pads its stroke
    base = cy + fk.cap_height(sz, "sans", 600) / 2
    wx = x + gsize + 12
    f.text(wx, base, arm["verdict"], "fg", "mono", 500)   # printed as the verifier prints it
    ex = f"exit {arm['exit']}"
    if exit_inline:
        ex_x = wx + fk.text_width(arm["verdict"], sz, "mono", 500) + 14
        f.text(ex_x, base, ex, "muted", "mono", 500)
        return ex_x + fk.text_width(ex, sz, "mono", 500)
    f.text(wx, base + sz * 1.3, ex, "muted", "mono", 500)
    return wx + fk.text_width(arm["verdict"], sz, "mono", 500)


def _verdict_width(f, arm, gsize):
    sz = f.text_size
    return gsize + 12 + fk.text_width(arm["verdict"], sz, "mono", 500) + 14 + fk.text_width(f"exit {arm['exit']}", sz, "mono", 500)


TAGS = ("v1", "v2")


def _kept(f, arm, x, cy, gsize, dy):
    """The changed verifier's two kept records: one printed verdict line per verifier, tagged v1 and v2."""
    sz = f.text_size
    for k, tag in enumerate(TAGS):
        right = _verdict(f, arm, x, cy + k * dy, gsize)
        f.text(right + 18, cy + k * dy + fk.cap_height(sz, "mono", 500) / 2, tag, "muted", "mono", 500)
    return right + 18 + fk.text_width(TAGS[1], sz, "mono", 500)


def _kept_pair(f, x, top, r, rh):
    """The changed-verifier picture: the old lens (v1, rule ink) and the changed lens (v2, accent) side by
    side, each dropping its receipt (outlined in its own ink) into one folder below, where the two receipts
    sit side by side. x is the left edge, top the top of the lenses. Returns (right edge, bottom edge,
    centre x of the changed lens, lens centre y)."""
    sz = f.text_size
    tw = fk.text_width(TAGS[0], sz, "mono", 500) + 8
    cap = fk.cap_height(sz, "mono", 500)
    ly = top + r
    slot = tw + r * 2 + r * 0.9 + 26           # tag, lens, handle and air
    rw = round(rh * 0.78, 1)
    ftop = ly + r + 16
    fh = rh + 30
    centres = []
    for k, (tag, ink) in enumerate(zip(TAGS, ("rule", "accent"), strict=True)):
        sx = x + k * slot
        f.text(sx, ly + cap / 2, tag, "fg", "mono", 500)
        lx = sx + tw + r
        centres.append(lx)
        fk.lens(f, lx, ly, r, stroke=ink)
        ry = ftop + 15 + rh / 2
        f.line(lx, ly + r + 3, lx, ry - rh / 2 - 6, ink, sw=2.5)
        fk.arrow(f, lx, ry - rh / 2 - 2, ink, size=6, direction="down")
        fk.receipt(f, lx - rw / 2, ry, h=rh, ink=ink)
    fx = centres[0] - rw / 2 - 18
    fw = centres[1] + rw / 2 + 18 - fx
    fk.folder(f, fx, ftop, fw, fh)
    return max(x + 2 * slot, fx + fw), ftop + fh, centres[1], ly


def _legend(f, x, y, stacked=False):
    """One line (three in the narrow layout) mapping each exit code the figure shows to its verdict."""
    sz = f.text_size
    seen = {}
    for arm in ARMS:
        seen.setdefault(arm["exit"], arm["verdict"])
    head = "exit code:"
    f.text(x, y, head, "muted", "mono", 500)
    cx = x + fk.text_width(head + " ", sz, "mono", 500)
    for k, (code, word) in enumerate(sorted(seen.items())):
        if stacked and k:
            y += sz * 1.35
            cx = x + fk.text_width(head + " ", sz, "mono", 500)
        f.text(cx, y, str(code), "fg", "mono", 500)
        cx += fk.text_width(f"{code} ", sz, "mono", 500)
        f.text(cx, y, word, "fg", "mono", 500)
        cx += fk.text_width(word, sz, "mono", 500) + fk.text_width("   ", sz, "mono", 500)
    return cx, y


def wide() -> fk.Fig:
    W, pad = 1280, fk.PAD
    geo, sgap = (3, 3, 10, 4, 9), 12
    aw, ah = fk.archive_size(3, geo, sgap)
    f = fk.Fig(NAME, "wide", W, 0, TITLE, DESC)
    gs = 34
    # the route: archive -> strikes -> lens -> verdict
    ty = 34 + ah / 2 + 14
    ax, ay = pad, ty - ah / 2
    vw = _verdict_width(f, INTACT, gs)
    vx = W - pad - vw
    lr = 22
    lx = vx - 30 - lr * 1.6
    f.line(ax + aw, ty, lx - lr, ty, "accent", sw=3)
    fk.lens(f, lx, ty, lr)
    f.line(lx + lr, ty, vx - 22, ty, "accent", sw=3)
    fk.arrow(f, vx - 12, ty)
    fk.archive(f, ax, ay, geo=geo, sgap=sgap, lock_r=16)
    f.text(vx + gs + 12, ty - 30, INTACT["caption"], "fg")
    _verdict(f, INTACT, vx, ty, gs)
    # three columns below; each strike drops to its column
    colw = (W - 2 * pad - 2 * 28) / 3
    cols = [pad + k * (colw + 28) for k in range(3)]
    pic_y = ty + ah / 2 + 86
    bus = ty + ah / 2 + 42
    # the archive as it arrives after each transit fault, and the two verifiers filing their receipts
    fk.archive(f, cols[0], pic_y, mark=(1, (1, 1)), geo=geo, sgap=sgap, broken=True, lock_r=16)
    fk.archive(f, cols[1], pic_y, missing=1, geo=geo, sgap=sgap, lock_r=16)
    right, bottom, v2x, kly = _kept_pair(f, cols[2], pic_y - 6, 16, 40)
    assert right <= cols[2] + colw
    pics = [cols[0] + aw / 2, cols[1] + aw / 2, v2x]
    tops = [pic_y - 16, pic_y - 16, kly - 16 - 8]
    strikes = [ax + aw + 70, cols[1] + aw / 2, lx]
    inks = ["loss", "absent", "loss"]
    for k in range(3):
        sx, px, top = strikes[k], pics[k], tops[k]
        y0 = ty + (lr + 10 if k == 2 else 0)
        if abs(sx - px) < 1:
            d = f"M{sx:.1f} {y0:.1f} L{px:.1f} {top:.1f}"
        else:
            d = f"M{sx:.1f} {y0:.1f} L{sx:.1f} {bus - 10:.1f} Q{sx:.1f} {bus:.1f} {sx + (10 if px > sx else -10):.1f} {bus:.1f} " \
                f"L{px + (-10 if px > sx else 10):.1f} {bus:.1f} Q{px:.1f} {bus:.1f} {px:.1f} {bus + 10:.1f} L{px:.1f} {top:.1f}"
        f.path(d, stroke=inks[k], sw=2.5, dash="6 6")
    for sx, ink in zip(strikes[:2], inks, strict=False):
        fk.strike(f, sx, ty, ink=ink)
    fk.strike(f, lx, ty + lr + 10, r=6)
    cap_y = max(pic_y + ah, bottom) + 44
    for k, arm in enumerate((BYTE, MISSING, CHANGED)):
        f.text(cols[k], cap_y, arm["caption"], "fg")
        if arm is CHANGED:
            assert _kept(f, arm, cols[k], cap_y + 40, gs, 40) <= cols[k] + colw, arm
            continue
        _verdict(f, arm, cols[k], cap_y + 40, gs)
        assert cols[k] + _verdict_width(f, arm, gs) <= cols[k] + colw, arm
    ly_ = cap_y + 80 + 62
    f.rect(pad, ly_ - 40, W - 2 * pad, 2, fill="rule")
    end, _ = _legend(f, pad, ly_)
    assert end <= W - pad
    f.height = round(ly_ + 26)
    return f


def narrow() -> fk.Fig:
    W, pad = 720, fk.PAD
    geo, sgap = (3, 3, 12, 5, 10), 12
    aw, ah = fk.archive_size(3, geo, sgap)
    gs = 40
    blk = ah + 160
    f = fk.Fig(NAME, "narrow", W, 0, TITLE, DESC)
    sz = f.text_size
    sx = pad + 34                     # the spine
    ay = 48
    cx = sx + 72                      # left edge of every block
    y = ay + ah + 50                  # top of the first block
    lr = 26
    blocks = []
    for k in range(3):
        blocks.append(y)
        y += blk
    ptop = blocks[2] + 30             # the two verifiers' lenses
    ly = ptop - 20                    # the spine lens sits just above them
    end_y = y + 200                   # the intact verdict's centre line (below the two kept lines)
    f.path(f"M{sx:.1f} {ay + ah:.1f} L{sx:.1f} {ly - lr:.1f}", stroke="accent", sw=3)
    f.path(f"M{sx:.1f} {ly + lr:.1f} L{sx:.1f} {end_y - 14:.1f} Q{sx:.1f} {end_y:.1f} {sx + 14:.1f} {end_y:.1f} L{cx - 24:.1f} {end_y:.1f}",
           stroke="accent", sw=3)
    fk.arrow(f, cx - 12, end_y, size=11)
    fk.archive(f, pad, ay, geo=geo, sgap=sgap, lock_r=20)
    # transit faults: strike on the spine, drop right to the archive as it arrives
    for k, (kw, ink) in enumerate((({"mark": (1, (1, 1)), "broken": True}, "loss"), ({"missing": 1}, "absent"))):
        by = blocks[k]
        cy = by + ah / 2
        f.line(sx, cy, cx - 10, cy, ink, sw=2.5, dash="6 6")
        fk.strike(f, sx, cy, ink=ink)
        fk.archive(f, cx, by, geo=geo, sgap=sgap, lock_r=20, **kw)
    # the changed verifier strikes at the lens and reaches the changed lens (v2)
    fk.lens(f, sx, ly, lr)
    _, bottom, v2x, kly = _kept_pair(f, cx, ptop, 22, 52)
    f.path(f"M{sx + lr + 12:.1f} {ly:.1f} L{v2x - 10:.1f} {ly:.1f} Q{v2x:.1f} {ly:.1f} {v2x:.1f} {ly + 10:.1f} L{v2x:.1f} {kly - 22 - 8:.1f}",
           stroke="loss", sw=2.5, dash="6 6")
    fk.strike(f, sx + lr + 12, ly, r=6)
    for k, arm in enumerate((BYTE, MISSING, CHANGED)):
        cap = blocks[k] + ah + 52 if k < 2 else max(blocks[k] + ah, bottom) + 52
        f.text(cx, cap, arm["caption"], "fg")
        if arm is CHANGED:
            assert cap + 50 + 52 < end_y - 44 - sz, cap
            assert _kept(f, arm, cx, cap + 50, gs, 52) <= W - pad, arm
            continue
        _verdict(f, arm, cx, cap + 50, gs)
        assert cx + _verdict_width(f, arm, gs) <= W - pad, arm
    f.text(cx, end_y - 44, INTACT["caption"], "fg")
    _verdict(f, INTACT, cx, end_y, gs)
    ly_ = end_y + 96
    f.rect(pad, ly_ - 50, W - 2 * pad, 2, fill="rule")
    end, last = _legend(f, pad, ly_, stacked=True)
    f.height = round(last + 34)
    return f


FIGS = (wide, narrow)
