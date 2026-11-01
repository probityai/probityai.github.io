"""figkit: one figure source, self-theming SVGs for every surface of the probityai org.

Each figure is drawn once in user units and written as three files per layout (wide, narrow):

- ``<layout>-auto.svg``: light colours as presentation attributes, a ``prefers-color-scheme: dark``
  override in ``<style>``. It follows the reader's scheme where the host lets it, and stays a legible
  light card where a host strips ``<style>``.
- ``<layout>-light.svg`` and ``<layout>-dark.svg``: one theme each, attributes only, for hosts that
  always show one image (PyPI, npm) and for the site's explicit theme switch.

Every figure sits on an opaque card, so a wrong theme guess still reads (RULING section 6). Text is live
IBM Plex, subset to the glyphs a figure uses and embedded as WOFF data URIs (section 4). The figure code
names roles, never hex values; tokens.toml holds the hex values for both themes.
"""

from __future__ import annotations

import base64
import io
import json
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from fontTools import subset
from fontTools.ttLib import TTFont

HERE = Path(__file__).resolve().parent
TOKENS = tomllib.loads((HERE / "tokens.toml").read_text())
ROLES = tuple(TOKENS["light"])
FONT_FILES = {
    ("sans", 400): HERE / "fonts/plex-sans-400.woff",
    ("sans", 600): HERE / "fonts/plex-sans-600.woff",
    ("mono", 500): HERE / "fonts/plex-mono-500.woff",
}
FAMILY = {
    "sans": "fk-sans, IBM Plex Sans, Inter, sans-serif",
    "mono": "fk-mono, IBM Plex Mono, monospace",
}
FACE = {"sans": "fk-sans", "mono": "fk-mono"}
THEMES = ("auto", "light", "dark")
PAD = 24
_FONTS: dict[tuple[str, int], TTFont] = {}

# Verdict glyphs in a 24-unit box, stroked with round caps. A double check is not a verdict glyph:
# it reads as a read receipt (RULING section 9).
GLYPHS = {
    "check": "M4 12.5 L9.5 18 L20 6",
    "cross": "M6 6 L18 18 M18 6 L6 18",
    "query": "M8.5 8.5 C8.5 5 15.5 5 15.5 8.5 C15.5 11 12 11.5 12 14.5 M12 19 L12 19.2",
}


def _font(key: tuple[str, int]) -> TTFont:
    if key not in _FONTS:
        _FONTS[key] = TTFont(FONT_FILES[key], recalcTimestamp=False)
    return _FONTS[key]


def text_width(s: str, size: float, font: str = "sans", weight: int = 400) -> float:
    """Advance width of s in user units, from the font's own hmtx table (no kerning)."""
    f = _font((font, weight))
    cmap: Any = f.getBestCmap()
    hmtx: Any = f["hmtx"]
    head: Any = f["head"]
    return sum(hmtx[cmap[ord(c)]][0] for c in s) * size / head.unitsPerEm


def cap_height(size: float, font: str = "sans", weight: int = 400) -> float:
    f = _font((font, weight))
    os2: Any = f["OS/2"]
    head: Any = f["head"]
    return os2.sCapHeight * size / head.unitsPerEm


def _woff_b64(key: tuple[str, int], chars: set[str]) -> str:
    opts: Any = subset.Options()
    opts.flavor = "woff"
    opts.layout_features = ["kern", "liga", "tnum"]
    opts.name_IDs = [1, 2]  # Chrome's font sanitizer rejects an empty name table
    opts.hinting = False
    font = TTFont(FONT_FILES[key], recalcTimestamp=False)
    sub = subset.Subsetter(opts)
    sub.populate(text="".join(sorted(chars)) + " ")
    sub.subset(font)
    buf = io.BytesIO()
    font.flavor = "woff"
    font.save(buf)
    return base64.b64encode(buf.getvalue()).decode()


@dataclass
class Fig:
    """A figure in one layout. Elements are stored as (tag, attrs, paint, body) and painted per theme."""

    name: str
    layout: str
    width: float
    height: float
    title: str
    desc: str
    els: list[tuple[str, dict[str, str], dict[str, str], str]] = field(
        default_factory=list
    )
    chars: dict[tuple[str, int], set[str]] = field(default_factory=dict)
    sizes: list[float] = field(default_factory=list)
    words: list[str] = field(default_factory=list)

    @property
    def text_size(self) -> int:
        return int(TOKENS["type"]["text_" + self.layout])

    def _add(
        self,
        tag: str,
        attrs: dict[str, object],
        fill: str | None,
        stroke: str | None,
        body: str = "",
    ) -> None:
        for role in (fill, stroke):
            if role is not None and role not in ROLES:
                raise ValueError(f"unknown colour role {role!r}")
        paint = {}
        paint["fill"] = fill or "none"
        if stroke:
            paint["stroke"] = stroke
        self.els.append((tag, {k: _fmt(v) for k, v in attrs.items()}, paint, body))

    def rect(
        self,
        x,
        y,
        w,
        h,
        fill=None,
        stroke=None,
        rx: float = 0,
        sw: float = 2,
        dash=None,
    ):
        a = {"x": x, "y": y, "width": w, "height": h, "rx": rx}
        if stroke:
            a["stroke-width"] = sw
        if dash:
            a["stroke-dasharray"] = dash
        self._add("rect", a, fill, stroke)

    def circle(self, cx, cy, r, fill=None, stroke=None, sw: float = 2, dash=None):
        a = {"cx": cx, "cy": cy, "r": r}
        if stroke:
            a["stroke-width"] = sw
        if dash:
            a["stroke-dasharray"] = dash
        self._add("circle", a, fill, stroke)

    def line(self, x1, y1, x2, y2, stroke, sw: float = 2, dash=None):
        a = {
            "x1": x1,
            "y1": y1,
            "x2": x2,
            "y2": y2,
            "stroke-width": sw,
            "stroke-linecap": "round",
        }
        if dash:
            a["stroke-dasharray"] = dash
        self._add("line", a, None, stroke)

    def path(
        self,
        d,
        fill=None,
        stroke=None,
        sw: float = 2,
        dash=None,
        join="round",
        opacity=None,
    ):
        a = {"d": d}
        if opacity is not None:
            a["opacity"] = opacity
        if stroke:
            a.update(
                {"stroke-width": sw, "stroke-linecap": "round", "stroke-linejoin": join}
            )
        if dash:
            a["stroke-dasharray"] = dash
        self._add("path", a, fill, stroke)

    def glyph(self, kind, x, y, size, stroke="fg", sw=None):
        """A verdict glyph with its top-left corner at (x, y); sw is the rendered stroke width."""
        k = size / 24
        sw = sw if sw is not None else max(3.0, size * 0.1)
        self._add(
            "path",
            {
                "transform": f"translate({_fmt(x)} {_fmt(y)}) scale({k:.4f})",
                "d": GLYPHS[kind],
                "stroke-width": sw / k,
                "stroke-linecap": "round",
                "stroke-linejoin": "round",
            },
            None,
            stroke,
        )

    def text(
        self, x, y, s, fill="fg", font="sans", weight=400, anchor="start", size=None
    ):
        size = size or self.text_size
        if size < self.text_size:
            raise ValueError(
                f"{self.name}/{self.layout}: {s!r} at {size} is under {self.text_size}"
            )
        if fill == "accent":
            raise ValueError(
                "accent is for marks only (the verifier and its route), never text"
            )
        if fill == "muted" and weight < 500:
            raise ValueError("muted text is weight 500 or more")
        bad = [c for c in s if not 0x20 <= ord(c) < 0x7F]
        if bad:
            raise ValueError(f"{s!r}: characters outside the embedded subset: {bad}")
        self.chars.setdefault((font, weight), set()).update(s)
        self.sizes.append(size)
        self.words.append(s)
        self._add(
            "text",
            {
                "x": x,
                "y": y,
                "font-family": FAMILY[font],
                "font-size": size,
                "font-weight": weight,
                "text-anchor": anchor,
            },
            fill,
            None,
            escape(s),
        )

    def render(self, theme: str, words: bool = True) -> str:
        base = TOKENS["dark" if theme == "dark" else "light"]
        css = []
        if words:
            for (font, weight), chars in sorted(self.chars.items()):
                css.append(
                    f"@font-face{{font-family:{FACE[font]};font-weight:{weight};"
                    f"src:url(data:font/woff;base64,{_woff_b64((font, weight), chars)}) format('woff')}}"
                )
        used: set[tuple[str, str]] = set()
        body = []
        r = 6 if self.layout == "wide" else 12
        card = (
            "rect",
            {
                "x": "0",
                "y": "0",
                "width": _fmt(self.width),
                "height": _fmt(self.height),
                "rx": str(r),
            },
            {"fill": "card"},
            "",
        )
        for tag, attrs, paint, text in [card, *self.els]:
            if tag == "text" and not words:
                continue
            a = dict(attrs)
            classes = []
            for prop, role in paint.items():
                if role == "none":
                    a[prop] = "none"
                    continue
                a[prop] = base[role]
                classes.append(f"{prop[0]}-{role}")
                used.add((prop, role))
            if theme == "auto" and classes:
                a["class"] = " ".join(classes)
            attr = " ".join(f'{k}="{v}"' for k, v in a.items())
            body.append(f"<{tag} {attr}>{text}</{tag}>" if text else f"<{tag} {attr}/>")
        if theme == "auto":
            dark = TOKENS["dark"]
            rules = "".join(
                f".{p[0]}-{role}{{{p}:{dark[role]}}}" for p, role in sorted(used)
            )
            css.append(f"@media (prefers-color-scheme:dark){{{rules}}}")
        style = f"<style>{''.join(css)}</style>" if css else ""
        head = (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.width:.0f} {self.height:.0f}" '
            f'width="{self.width:.0f}" height="{self.height:.0f}" role="img" aria-labelledby="t d">'
            f'<title id="t">{escape(self.title)}</title><desc id="d">{escape(self.desc)}</desc>{style}'
        )
        return head + "".join(body) + "</svg>\n"

    def meta(self) -> dict:
        return {
            "name": self.name,
            "layout": self.layout,
            "width": self.width,
            "height": self.height,
            "text_size": self.text_size,
            "alt": self.desc,
            "words": self.words,
        }


def _fmt(v: object) -> str:
    if isinstance(v, float):
        s = f"{v:.1f}"
        return s.removesuffix(".0")
    return str(v)


def write(figs: list[Fig], root: Path, rev: int) -> list[Path]:
    """Write figures/<name>/<rev>/<layout>-<theme>.svg plus meta.json, and a word-stripped copy of the
    light variant under figures/_mute/ for the mute test."""
    paths = []
    for fig in figs:
        out = root / fig.name / str(rev)
        out.mkdir(parents=True, exist_ok=True)
        for theme in THEMES:
            p = out / f"{fig.layout}-{theme}.svg"
            p.write_text(fig.render(theme))
            paths.append(p)
        (out / f"{fig.layout}.meta.json").write_text(
            json.dumps(fig.meta(), indent=1) + "\n"
        )
        mute = root / "_mute"
        mute.mkdir(exist_ok=True)
        (mute / f"{fig.name}-{fig.layout}.svg").write_text(
            fig.render("light", words=False)
        )
    return paths


# --- Shared motifs -------------------------------------------------------------------------------------
# A file is a dog-eared sheet holding a grid of byte cells. An evidence archive is an archive box: its files
# stand in it side by side, the box's front panel covers their lower half, and a padlock whose body carries
# a digest mark (#) sits on the panel's top edge: a signature over the files' digest. A verifier is a lens;
# what it prints is a till receipt (straight top, torn zigzag foot) with the verdict glyph on it. A reader
# that only looks is an eye.

CELL, GAP, SPAD, EAR = 12, 5, 11, 12


def sheet_size(cols=4, rows=3, cell=CELL, gap=GAP, pad=SPAD):
    return cols * cell + (cols - 1) * gap + 2 * pad, rows * cell + (
        rows - 1
    ) * gap + 2 * pad + EAR / 2


def _eared(x, y, w, h, ear):
    return f"M{x:.1f} {y:.1f} L{x + w - ear:.1f} {y:.1f} L{x + w:.1f} {y + ear:.1f} L{x + w:.1f} {y + h:.1f} L{x:.1f} {y + h:.1f} Z"


def sheet(
    f: Fig,
    x,
    y,
    cols=4,
    rows=3,
    cell=CELL,
    gap=GAP,
    pad=SPAD,
    state="present",
    mark=None,
    loud=False,
    mark_k=0.7,
):
    """A file sheet. state "missing" draws only the empty place a sheet would stand in: a thin dashed
    outline in rule ink with nothing inside. It carries no signal colour, because a coloured slot reads as a
    bad sheet rather than an absent one. mark (col, row) is the one byte cell drawn in loss ink at the same
    size as its neighbours: one changed byte, not a different kind of object."""
    w, h = sheet_size(cols, rows, cell, gap, pad)
    outline = _eared(x, y, w, h, EAR)
    if state == "missing":
        if loud:
            # the empty place in dark ink and nothing inside: a mark inside it read as a file of its own
            f.path(outline, fill="tile", stroke="fg", sw=4, dash="8 6")
        else:
            f.path(outline, stroke="rule", sw=2.5, dash="6 6")
        return w, h
    f.path(outline, fill="tile", stroke="rule", sw=2, join="round")
    f.path(
        f"M{x + w - EAR:.1f} {y:.1f} L{x + w - EAR:.1f} {y + EAR:.1f} L{x + w:.1f} {y + EAR:.1f}",
        stroke="rule",
        sw=2,
    )
    top = y + pad + EAR / 2
    for r in range(rows):
        for c in range(cols):
            cx, cy = x + pad + c * (cell + gap), top + r * (cell + gap)
            if mark == (c, r):
                continue
            f.rect(cx, cy, cell, cell, fill="byte", rx=2)
    if mark is not None:
        # the changed byte: one grid cell in loss ink, larger than its neighbours (mark_k is half its side,
        # in cells)
        c, r = mark
        ccx = x + pad + c * (cell + gap) + cell / 2
        ccy = top + r * (cell + gap) + cell / 2
        k = cell * mark_k
        f.rect(ccx - k, ccy - k, 2 * k, 2 * k, fill="loss", rx=2)
    return w, h


def lock(f: Fig, cx, cy, r: float = 12, broken=False):
    """The archive's signature: a padlock centred on (cx, cy) whose solid body carries a digest mark (#)
    knocked out in the card colour, so it reads as a lock over a digest, not an award. r is half the body
    width. broken swings the shackle open off its right post, in loss ink: the seal no longer holds."""
    bw, bh = 2 * r, 1.6 * r
    bx, by = cx - r, cy - bh * 0.3
    sr = r * 0.62  # shackle radius
    sw = max(3.0, r * 0.32)
    if broken:
        f.path(
            f"M{cx + sr:.1f} {by:.1f} L{cx + sr:.1f} {by - sr * 0.9:.1f} A{sr:.1f} {sr:.1f} 0 0 0 {cx - sr * 0.9:.1f} {by - sr * 2.1:.1f}",
            stroke="loss",
            sw=sw,
        )
    else:
        f.path(
            f"M{cx - sr:.1f} {by:.1f} L{cx - sr:.1f} {by - sr * 0.6:.1f} A{sr:.1f} {sr:.1f} 0 0 1 {cx + sr:.1f} {by - sr * 0.6:.1f} L{cx + sr:.1f} {by:.1f}",
            stroke="fg",
            sw=sw,
        )
    f.rect(bx, by, bw, bh, fill="fg", rx=r * 0.25)
    hw, hs = r * 0.62, max(1.6, r * 0.13)
    hy = by + bh / 2
    for d in (-1, 1):
        f.line(
            cx + d * hw * 0.28 + hw * 0.08,
            hy - hw * 0.55,
            cx + d * hw * 0.28 - hw * 0.08,
            hy + hw * 0.55,
            "card",
            sw=hs,
        )
        f.line(
            cx - hw * 0.5,
            hy + d * hw * 0.22,
            cx + hw * 0.5,
            hy + d * hw * 0.22,
            "card",
            sw=hs,
        )


BOX_M, BOX_FOOT = (
    12,
    16,
)  # the box's side margin round its files; the panel's depth under them


def box_size(n=3, geo=(4, 3, CELL, GAP, SPAD), sgap=14):
    """(width, height) of an archive box of n files, from the files' tops to the box's foot."""
    sw_, sh_ = sheet_size(*geo)
    return 2 * BOX_M + n * sw_ + (n - 1) * sgap, sh_ + BOX_FOOT


def box(
    f: Fig,
    x,
    y,
    n=3,
    missing=None,
    mark=None,
    geo=(4, 3, CELL, GAP, SPAD),
    sgap=14,
    broken=False,
    lock_r=14,
    loud=False,
    mark_k=0.7,
):
    """An archive box with its top-left at (x, y), the files' tops: n files stand in it, the front panel
    covers their lower half, and the padlock sits on the panel's top edge. missing is the index of a file
    that is not there (a dashed slot); mark is (index, (col, row)) for a changed byte, drawn in the files'
    top row so it shows over the panel. With a mark on a broken box, a thin arrow in loss ink arcs from the
    changed byte over the files to the sprung shackle: that byte is what opened the seal. Returns (width,
    height)."""
    sw_, sh_ = sheet_size(*geo)
    w, h = box_size(n, geo, sgap)
    panel = y + sh_ * 0.55
    # the back wall, lower than the files so they stand up out of the box
    f.path(
        f"M{x:.1f} {panel:.1f} L{x:.1f} {y + sh_ * 0.3:.1f} L{x + w:.1f} {y + sh_ * 0.3:.1f} L{x + w:.1f} {panel:.1f}",
        stroke="rule",
        sw=2.5,
        join="round",
    )
    for i in range(n):
        sheet(
            f,
            x + BOX_M + i * (sw_ + sgap),
            y,
            *geo,
            state="missing" if missing == i else "present",
            mark=mark[1] if mark and mark[0] == i else None,
            loud=loud,
            mark_k=mark_k,
        )
    f.rect(x, panel, w, y + h - panel, fill="tile", stroke="rule", rx=5, sw=2.5)
    # the box's hand hole, low on the panel
    hw = min(46, w * 0.22)
    hy = panel + (y + h - panel) * 0.62
    f.rect(x + w / 2 - hw / 2, hy - 5, hw, 10, fill="card", stroke="rule", rx=5, sw=2)
    lock(f, x + w - BOX_M - lock_r, panel, r=lock_r, broken=broken)
    if mark is not None and broken:
        i, (c, r) = mark
        cols, _rows, cell, gap, pad = geo
        ccx = x + BOX_M + i * (sw_ + sgap) + pad + c * (cell + gap) + cell / 2
        k = cell * mark_k
        top = y + pad + EAR / 2 + r * (cell + gap) + cell / 2 - k
        lcx = x + w - BOX_M - lock_r
        sr = lock_r * 0.62
        ty = panel - 1.6 * lock_r * 0.3 - sr * 2.1 - 6
        tx = lcx - sr * 0.9
        peak = y - 22
        f.path(
            f"M{ccx:.1f} {top - 3:.1f} C{ccx:.1f} {peak:.1f} {tx:.1f} {peak:.1f} {tx:.1f} {ty - 12:.1f}",
            stroke="loss",
            sw=3,
        )
        arrow(f, tx, ty, "loss", size=6, direction="down")
    return w, h


def glass(f: Fig, cx, cy, r, bars, stroke="accent", dash=None):
    """A lens's glass: a disc with `bars` level bars across it. The bars are the glass's grind, so a lens
    whose glass was swapped shows a different count while its rim and handle stay the same."""
    f.circle(cx, cy, r, fill="card", stroke=stroke, sw=4 if dash is None else 2.5, dash=dash)
    offs = {1: (0.0,), 2: (-0.28, 0.28), 3: (-0.4, 0.0, 0.4)}[bars]
    for o in offs:
        half = r * 0.62 * (1 - abs(o) * 0.6)
        f.line(cx - half, cy + o * r, cx + half, cy + o * r, stroke, sw=3, dash=dash)


def lens(f: Fig, cx, cy, r=20, stroke="accent", double=False, reticle=False, bars=0):
    """A verifier: a magnifying lens, handle down-right. double rings the rim twice: a different verifier.
    reticle draws fine cross hairs in the glass: the same lens made stricter. bars grinds the glass with
    that many level bars (see glass)."""
    f.line(cx + r * 0.72, cy + r * 0.72, cx + r * 1.5, cy + r * 1.5, stroke, sw=6)
    if bars:
        glass(f, cx, cy, r, bars, stroke)
        return
    f.circle(cx, cy, r, fill="card", stroke=stroke, sw=4)
    if double:
        f.circle(cx, cy, r * 0.6, stroke=stroke, sw=3)
    if reticle:
        # cross hairs with an open centre and a small aiming ring
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            f.line(cx + dx * r * 0.3, cy + dy * r * 0.3, cx + dx * r * 0.85, cy + dy * r * 0.85, stroke, sw=2.4)
        f.circle(cx, cy, r * 0.18, fill=stroke)


def lens_version(f: Fig, cx, cy, r=20, version=1, stroke="accent"):
    """A verifier at a given version. Version 1 is the plain round lens. A later version is the same kind of
    instrument made stronger, as a stricter verifier is: a larger lens with a second glass set inside the rim.
    It stays a magnifier at a glance (a square rim and handle notches were read as a crossed-out square)."""
    if version == 1:
        lens(f, cx, cy, r, stroke=stroke)
        return
    R = r * 1.3
    f.line(cx + R * 0.72, cy + R * 0.72, cx + R * 1.5, cy + R * 1.5, stroke, sw=7)
    f.circle(cx, cy, R, fill="card", stroke=stroke, sw=5)
    f.circle(cx, cy, R * 0.62, fill="tile", stroke=stroke, sw=3)


def wrench(f: Fig, cx, cy, r, angle_deg=-135.0, ink="fg"):
    """An open-ended wrench clamped on the rim of the lens of radius r centred on (cx, cy), from the side at
    angle_deg: its jaw grips the rim and its handle points away. The lens is being changed."""
    import math

    a = math.radians(angle_deg)
    ux, uy = math.cos(a), math.sin(a)
    jx, jy = cx + ux * r * 1.12, cy + uy * r * 1.12  # the jaw's centre, just outside the rim
    jr = r * 0.62

    def jaw(x, y, toward):
        # a C open in the direction toward
        p0 = (x + jr * math.cos(toward + 0.9), y + jr * math.sin(toward + 0.9))
        p1 = (x + jr * math.cos(toward - 0.9), y + jr * math.sin(toward - 0.9))
        f.path(f"M{p0[0]:.1f} {p0[1]:.1f} A{jr:.1f} {jr:.1f} 0 1 1 {p1[0]:.1f} {p1[1]:.1f}", stroke=ink, sw=7)

    jaw(jx, jy, a + math.pi)
    far = r * 3.6
    kx, ky = jx + ux * far, jy + uy * far
    h0 = (jx + ux * jr, jy + uy * jr)
    h1 = (kx - ux * jr, ky - uy * jr)
    f.line(h0[0], h0[1], h1[0], h1[1], ink, sw=9)
    jaw(kx, ky, a)  # the wrench's other end, open away


def slip(f: Fig, x, cy, h, glyph, gink="fg", ink="rule"):
    """What a verifier prints: a till receipt with its left edge at x, centred on cy, a straight top and a
    torn zigzag foot, two printed lines and the verdict glyph. Returns the right edge."""
    w = round(h * 0.74, 1)
    y = cy - h / 2
    teeth = 4
    tw = w / teeth
    foot = " ".join(
        f"L{x + w - (k + 0.5) * tw:.1f} {y + h - 6:.1f} L{x + w - (k + 1) * tw:.1f} {y + h:.1f}"
        for k in range(teeth)
    )
    f.path(
        f"M{x:.1f} {y:.1f} L{x + w:.1f} {y:.1f} L{x + w:.1f} {y + h:.1f} {foot} Z",
        fill="tile",
        stroke=ink,
        sw=2.5,
    )
    for k, right in ((0, w - 7), (1, w * 0.6)):
        f.line(x + 7, y + 9 + k * 7, x + right, y + 9 + k * 7, "rule", sw=2.5)
    g = w * 0.62
    f.glyph(
        glyph,
        x + (w - g) / 2,
        y + 22 + (h - 28 - g) / 2,
        g,
        gink,
        sw=max(3.0, g * 0.13),
    )
    return x + w


def folder_back(f: Fig, x, y, w, h, ink="rule"):
    """Where records are kept: an open file folder seen from the front, x, y its back panel's top-left (under
    the tab), w by h. Draw its back with this call, then what it holds, then folder_front, so the front flap
    covers the lower part of what stands in it."""
    tw, th = w * 0.38, 14
    f.path(
        f"M{x:.1f} {y + h:.1f} L{x:.1f} {y + 5:.1f} Q{x:.1f} {y:.1f} {x + 5:.1f} {y:.1f} "
        f"L{x + 8:.1f} {y:.1f} L{x + 14:.1f} {y - th:.1f} L{x + tw:.1f} {y - th:.1f} L{x + tw + 6:.1f} {y:.1f} "
        f"L{x + w - 5:.1f} {y:.1f} Q{x + w:.1f} {y:.1f} {x + w:.1f} {y + 5:.1f} L{x + w:.1f} {y + h:.1f} Z",
        fill="tile",
        stroke=ink,
        sw=2.5,
    )


def folder_front(f: Fig, x, y, w, h, flap, ink="rule"):
    """The folder's front flap: the lower `flap` of the back panel at (x, y, w, h), drawn over what it holds."""
    f.rect(x - 3, y + h - flap, w + 6, flap, fill="tile", stroke=ink, rx=5, sw=2.5)


def thought(f: Fig, cx, cy, w, h, toward, ink="fg"):
    """A thought cloud centred on (cx, cy), w by h, with a trail of shrinking bubbles running to the point
    toward (the thinker). What is drawn inside it after this call is what the thinker believes."""
    import math

    n = 9
    pts = []
    for k in range(n):
        a = 2 * math.pi * k / n
        pts.append((cx + w / 2 * math.cos(a), cy + h / 2 * math.sin(a)))
    d = f"M{pts[0][0]:.1f} {pts[0][1]:.1f} "
    bump = min(w, h) * 0.26
    for k in range(n):
        p0, p1 = pts[k], pts[(k + 1) % n]
        d += f"A{bump:.1f} {bump:.1f} 0 0 1 {p1[0]:.1f} {p1[1]:.1f} "
    f.path(d + "Z", fill="tile", stroke=ink, sw=2.5)
    tx, ty = toward
    dx, dy = tx - cx, ty - cy
    dist = math.hypot(dx, dy)
    a = math.atan2(dy, dx)
    edge = math.hypot(w / 2 * math.cos(a), h / 2 * math.sin(a)) + bump * 0.35
    for k, rr in enumerate((6, 4.5, 3)):
        t = (edge + (dist - edge) * (0.2 + 0.32 * k)) / dist
        f.circle(cx + dx * t, cy + dy * t, rr, fill="tile", stroke=ink, sw=2)


def eye(f: Fig, cx, cy, r=18, ink="fg"):
    """A reader that only looks: an open eye, an almond outline round a solid iris."""
    f.path(
        f"M{cx - r:.1f} {cy:.1f} Q{cx:.1f} {cy - r * 1.05:.1f} {cx + r:.1f} {cy:.1f} Q{cx:.1f} {cy + r * 1.05:.1f} {cx - r:.1f} {cy:.1f} Z",
        fill="tile",
        stroke=ink,
        sw=3,
    )
    f.circle(cx, cy, r * 0.36, fill=ink)


def arrow(f: Fig, x, y, ink="accent", size=9, direction="right"):
    """A solid arrowhead with its tip at (x, y), pointing right, left, up or down."""
    if direction == "left":
        d = f"M{x:.1f} {y:.1f} L{x + size * 1.2:.1f} {y - size * 0.75:.1f} L{x + size * 1.2:.1f} {y + size * 0.75:.1f} Z"
    elif direction == "right":
        d = f"M{x:.1f} {y:.1f} L{x - size * 1.2:.1f} {y - size * 0.75:.1f} L{x - size * 1.2:.1f} {y + size * 0.75:.1f} Z"
    elif direction == "up":
        d = f"M{x:.1f} {y:.1f} L{x - size * 0.75:.1f} {y + size * 1.2:.1f} L{x + size * 0.75:.1f} {y + size * 1.2:.1f} Z"
    else:
        d = f"M{x:.1f} {y:.1f} L{x - size * 0.75:.1f} {y - size * 1.2:.1f} L{x + size * 0.75:.1f} {y - size * 1.2:.1f} Z"
    f.path(d, fill=ink, stroke=ink, sw=1)
