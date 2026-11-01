"""F1 Four verdicts: one sealed archive travels to the verifier; each fault is drawn where it strikes
(RULING section 9).

One route carries the archive left to right (top to bottom in the narrow layout) through the verifier's
lens to its verdict: verified, exit 0. A changed byte and a missing artifact strike the archive on its
way to the verifier; each strike drops to the archive as it then arrives and to the verdict the verifier
prints for it. The changed verifier strikes at the lens: the old lens (rule ink) and the changed one
(accent) each read the archive and each keeps a receipt. Words and exit codes come from data/four-arms.toml.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import figkit as fk

HERE = Path(__file__).resolve().parent
NAME = "f1-four-verdicts"
REV = 1
ARMS = tomllib.loads((HERE / "data/four-arms.toml").read_text())["arm"]
INTACT, BYTE, MISSING, CHANGED = ARMS
TITLE = "Four verdicts from one evidence archive"
DESC = (
    "A sealed archive of three files travels to a verifier. Intact, it is verified, exit 0. A byte changed "
    "on the way breaks the seal: failed, exit 2. A required file lost on the way: not-established, exit 3. "
    "A changed verifier: the old and the changed verifier both read the archive and both say verified, "
    "exit 0, and both receipts are kept."
)


def _verdict(f, arm, x, cy, gsize, exit_inline=True):
    """Glyph, verdict word and exit code with the glyph's centre at (x + gsize/2, cy). Returns the right edge."""
    sz = f.text_size
    f.glyph(arm["glyph"], x, cy - gsize / 2, gsize, "fg")
    base = cy + fk.cap_height(sz, "sans", 600) / 2
    wx = x + gsize + 12
    f.text(wx, base, arm["verdict"], "fg", "sans", 600)
    ex = f"exit {arm['exit']}"
    if exit_inline:
        ex_x = wx + fk.text_width(arm["verdict"], sz, "sans", 600) + 14
        f.text(ex_x, base, ex, "muted", "mono", 500)
        return ex_x + fk.text_width(ex, sz, "mono", 500)
    f.text(wx, base + sz * 1.3, ex, "muted", "mono", 500)
    return wx + fk.text_width(arm["verdict"], sz, "sans", 600)


def _verdict_width(f, arm, gsize):
    sz = f.text_size
    return gsize + 12 + fk.text_width(arm["verdict"], sz, "sans", 600) + 14 + fk.text_width(f"exit {arm['exit']}", sz, "mono", 500)


def _two_readers(f, x, cy, r, dy, rh):
    """The changed-verifier picture: the old lens (rule) above the changed lens (accent), each followed by
    its receipt. x is the left edge; returns the right edge."""
    right = x
    for sgn, ink in ((-1, "rule"), (1, "accent")):
        y = cy + sgn * dy
        lx = x + r
        fk.lens(f, lx, y, r, stroke=ink)
        right = fk.receipt(f, lx + r * 1.5 + 18, y, h=rh)
    return right


def wide() -> fk.Fig:
    W, pad = 1280, fk.PAD
    geo, sgap = (3, 3, 10, 4, 9), 12
    aw, ah = fk.archive_size(3, geo, sgap)
    f = fk.Fig(NAME, "wide", W, 438, TITLE, DESC)
    sz = f.text_size
    gs = 34
    # the route: archive -> strikes -> lens -> verdict
    ty = 30 + ah / 2 + 6
    ax, ay = pad, ty - ah / 2
    vw = _verdict_width(f, INTACT, gs)
    vx = W - pad - vw
    lr = 22
    lx = vx - 30 - lr * 1.6
    f.line(ax + aw, ty, lx - lr, ty, "accent", sw=3)
    fk.lens(f, lx, ty, lr)
    f.line(lx + lr, ty, vx - 12, ty, "accent", sw=3)
    fk.archive(f, ax, ay, geo=geo, sgap=sgap)
    f.text(vx + gs + 12, ty - 30, INTACT["caption"], "fg")
    _verdict(f, INTACT, vx, ty, gs)
    # three columns below; each strike drops to its column
    colw = (W - 2 * pad - 2 * 28) / 3
    cols = [pad + k * (colw + 28) for k in range(3)]
    pic_y = ty + ah / 2 + 86
    bus = ty + ah / 2 + 42
    rr, rdy = 18, 26
    pics = [cols[0] + aw / 2, cols[1] + aw / 2, cols[2] + rr]
    strikes = [ax + aw + 70, cols[1] + aw / 2, lx]
    for k in range(3):
        sx, px = strikes[k], pics[k]
        top = pic_y - 16 if k < 2 else pic_y + ah / 2 - rdy - rr - 6
        y0 = ty + (lr + 10 if k == 2 else 0)
        if abs(sx - px) < 1:
            d = f"M{sx:.1f} {y0:.1f} L{px:.1f} {top:.1f}"
        else:
            d = f"M{sx:.1f} {y0:.1f} L{sx:.1f} {bus - 10:.1f} Q{sx:.1f} {bus:.1f} {sx + (10 if px > sx else -10):.1f} {bus:.1f} " \
                f"L{px + (-10 if px > sx else 10):.1f} {bus:.1f} Q{px:.1f} {bus:.1f} {px:.1f} {bus + 10:.1f} L{px:.1f} {top:.1f}"
        f.path(d, stroke="loss", sw=2.5, dash="6 6")
    for sx in strikes[:2]:
        fk.strike(f, sx, ty)
    fk.strike(f, lx, ty + lr + 10, r=6)
    # the archive as it arrives after each transit fault
    fk.archive(f, cols[0], pic_y, mark=(1, (1, 1)), geo=geo, sgap=sgap, broken=True)
    fk.archive(f, cols[1], pic_y, missing=1, geo=geo, sgap=sgap)
    _two_readers(f, cols[2], pic_y + ah / 2, rr, rdy, 34)
    cap_y = pic_y + ah + 44
    for k, arm in enumerate((BYTE, MISSING, CHANGED)):
        f.text(cols[k], cap_y, arm["caption"], "fg")
        _verdict(f, arm, cols[k], cap_y + 40, gs)
        assert cols[k] + _verdict_width(f, arm, gs) <= cols[k] + colw, arm
    return f


def narrow() -> fk.Fig:
    W, pad = 720, fk.PAD
    geo, sgap = (3, 3, 12, 5, 10), 12
    aw, ah = fk.archive_size(3, geo, sgap)
    gs = 40
    blk = ah + 160
    H = 36 + ah + 50 + 3 * blk + 150
    f = fk.Fig(NAME, "narrow", W, H, TITLE, DESC)
    sz = f.text_size
    sx = pad + 34                     # the spine
    ay = 36
    cx = sx + 72                      # left edge of every block
    y = ay + ah + 50                  # top of the first block
    lr = 26
    blocks = []
    for k in range(3):
        blocks.append(y)
        y += blk
    ly = blocks[2] + ah / 2           # the lens sits beside the changed-verifier picture
    end_y = y + 84                    # the intact verdict's centre line
    f.path(f"M{sx:.1f} {ay + ah:.1f} L{sx:.1f} {ly - lr:.1f}", stroke="accent", sw=3)
    f.path(f"M{sx:.1f} {ly + lr:.1f} L{sx:.1f} {end_y - 14:.1f} Q{sx:.1f} {end_y:.1f} {sx + 14:.1f} {end_y:.1f} L{cx - 12:.1f} {end_y:.1f}",
           stroke="accent", sw=3)
    fk.archive(f, pad, ay, geo=geo, sgap=sgap, seal_r=13)
    # transit faults: strike on the spine, drop right to the archive as it arrives
    for k, kw in enumerate(({"mark": (1, (1, 1)), "broken": True}, {"missing": 1})):
        by = blocks[k]
        cy = by + ah / 2
        f.line(sx, cy, cx - 10, cy, "loss", sw=2.5, dash="6 6")
        fk.strike(f, sx, cy)
        fk.archive(f, cx, by, geo=geo, sgap=sgap, seal_r=13, **kw)
    # the changed verifier strikes at the lens
    fk.lens(f, sx, ly, lr)
    f.line(sx + lr + 12, ly, cx - 10, ly, "loss", sw=2.5, dash="6 6")
    fk.strike(f, sx + lr + 12, ly, r=6)
    _two_readers(f, cx, ly, 22, 32, 40)
    for k, arm in enumerate((BYTE, MISSING, CHANGED)):
        cap = blocks[k] + ah + 52
        f.text(cx, cap, arm["caption"], "fg")
        _verdict(f, arm, cx, cap + 50, gs)
        assert cx + _verdict_width(f, arm, gs) <= W - pad, arm
    f.text(cx, end_y - 44, INTACT["caption"], "fg")
    _verdict(f, INTACT, cx, end_y, gs)
    return f


FIGS = (wide, narrow)
