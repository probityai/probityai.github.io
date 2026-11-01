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
    cmap = f.getBestCmap()
    hmtx = f["hmtx"]
    return sum(hmtx[cmap[ord(c)]][0] for c in s) * size / f["head"].unitsPerEm


def cap_height(size: float, font: str = "sans", weight: int = 400) -> float:
    f = _font((font, weight))
    return f["OS/2"].sCapHeight * size / f["head"].unitsPerEm


def _woff_b64(key: tuple[str, int], chars: set[str]) -> str:
    opts = subset.Options()
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
    els: list[tuple[str, dict[str, str], dict[str, str], str]] = field(default_factory=list)
    chars: dict[tuple[str, int], set[str]] = field(default_factory=dict)
    sizes: list[float] = field(default_factory=list)
    words: list[str] = field(default_factory=list)

    @property
    def text_size(self) -> int:
        return int(TOKENS["type"]["text_" + self.layout])

    def _add(self, tag: str, attrs: dict[str, object], fill: str | None, stroke: str | None, body: str = "") -> None:
        for role in (fill, stroke):
            if role is not None and role not in ROLES:
                raise ValueError(f"unknown colour role {role!r}")
        paint = {}
        paint["fill"] = fill or "none"
        if stroke:
            paint["stroke"] = stroke
        self.els.append((tag, {k: _fmt(v) for k, v in attrs.items()}, paint, body))

    def rect(self, x, y, w, h, fill=None, stroke=None, rx=0, sw=2, dash=None):
        a = {"x": x, "y": y, "width": w, "height": h, "rx": rx}
        if stroke:
            a["stroke-width"] = sw
        if dash:
            a["stroke-dasharray"] = dash
        self._add("rect", a, fill, stroke)

    def circle(self, cx, cy, r, fill=None, stroke=None, sw=2):
        a = {"cx": cx, "cy": cy, "r": r}
        if stroke:
            a["stroke-width"] = sw
        self._add("circle", a, fill, stroke)

    def line(self, x1, y1, x2, y2, stroke, sw=2, dash=None):
        a = {"x1": x1, "y1": y1, "x2": x2, "y2": y2, "stroke-width": sw, "stroke-linecap": "round"}
        if dash:
            a["stroke-dasharray"] = dash
        self._add("line", a, None, stroke)

    def path(self, d, fill=None, stroke=None, sw=2, dash=None, join="round"):
        a = {"d": d}
        if stroke:
            a.update({"stroke-width": sw, "stroke-linecap": "round", "stroke-linejoin": join})
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

    def text(self, x, y, s, fill="fg", font="sans", weight=400, anchor="start", size=None):
        size = size or self.text_size
        if size < self.text_size:
            raise ValueError(f"{self.name}/{self.layout}: {s!r} at {size} is under {self.text_size}")
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
        card = ("rect", {"x": "0", "y": "0", "width": _fmt(self.width), "height": _fmt(self.height), "rx": str(r)}, {"fill": "card"}, "")
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
            rules = "".join(f".{p[0]}-{role}{{{p}:{dark[role]}}}" for p, role in sorted(used))
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
        return s[:-2] if s.endswith(".0") else s
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
        (out / f"{fig.layout}.meta.json").write_text(json.dumps(fig.meta(), indent=1) + "\n")
        mute = root / "_mute"
        mute.mkdir(exist_ok=True)
        (mute / f"{fig.name}-{fig.layout}.svg").write_text(fig.render("light", words=False))
    return paths


# --- Shared motifs -------------------------------------------------------------------------------------
# An artifact is a file sheet with a dog-eared corner holding a grid of byte cells; an archive is a row of
# sheets in one outline with a rosette seal on its top-right corner; a checker is a two-post gate.

CELL, GAP, SPAD, EAR = 12, 5, 11, 12


def sheet_size(cols=4, rows=3, cell=CELL, gap=GAP, pad=SPAD):
    return cols * cell + (cols - 1) * gap + 2 * pad, rows * cell + (rows - 1) * gap + 2 * pad + EAR / 2


def sheet(f: Fig, x, y, cols=4, rows=3, cell=CELL, gap=GAP, pad=SPAD, state="present", mark=None):
    """A file sheet. state "missing" draws a dashed hollow outline in loss ink. mark (col, row) is the
    one byte cell drawn in loss ink, enlarged: the changed byte."""
    w, h = sheet_size(cols, rows, cell, gap, pad)
    outline = f"M{x:.1f} {y:.1f} L{x + w - EAR:.1f} {y:.1f} L{x + w:.1f} {y + EAR:.1f} L{x + w:.1f} {y + h:.1f} L{x:.1f} {y + h:.1f} Z"
    if state == "missing":
        f.path(outline, stroke="loss", sw=2.5, dash="7 5")
        return w, h
    f.path(outline, fill="tile", stroke="rule", sw=2, join="round")
    f.path(f"M{x + w - EAR:.1f} {y:.1f} L{x + w - EAR:.1f} {y + EAR:.1f} L{x + w:.1f} {y + EAR:.1f}", stroke="rule", sw=2)
    top = y + pad + EAR / 2
    for r in range(rows):
        for c in range(cols):
            cx, cy = x + pad + c * (cell + gap), top + r * (cell + gap)
            if mark == (c, r):
                f.rect(cx - 3, cy - 3, cell + 6, cell + 6, fill="loss", rx=3)
            else:
                f.rect(cx, cy, cell, cell, fill="byte", rx=2)
    return w, h


def rosette(f: Fig, cx, cy, r=16, broken=False):
    """The archive's seal: a solid 16-scallop wax seal with two ribbon tails. broken splits it with a gap
    in loss ink."""
    import math

    for side in (-1, 1):
        x = cx + side * r * 0.35
        f.path(f"M{x:.1f} {cy + r * 0.5:.1f} L{x + side * r * 0.25:.1f} {cy + r * 1.45:.1f} L{x - side * r * 0.25:.1f} {cy + r * 1.25:.1f} Z",
               fill="fg", stroke="fg", sw=1.5)
    for i in range(16):
        a = math.pi * i / 8
        f.circle(cx + r * 0.8 * math.cos(a), cy + r * 0.8 * math.sin(a), r * 0.24, fill="fg")
    f.circle(cx, cy, r * 0.85, fill="fg")
    if broken:
        f.path(f"M{cx - r * 0.45:.1f} {cy - r - 3:.1f} L{cx + r * 0.3:.1f} {cy + r + 3:.1f}", stroke="card", sw=7)
        f.path(f"M{cx - r * 0.45:.1f} {cy - r - 3:.1f} L{cx + r * 0.3:.1f} {cy + r + 3:.1f}", stroke="loss", sw=3)


def archive(f: Fig, x, y, n=3, missing=None, mark=None, geo=(4, 3, CELL, GAP, SPAD), sgap=14, broken=False):
    """n sheets in one outline with a rosette on its top-right corner. Returns (width, height)."""
    sw_, sh_ = sheet_size(*geo)
    m = 12
    w = 2 * m + n * sw_ + (n - 1) * sgap
    h = 2 * m + sh_
    f.rect(x, y, w, h, stroke="rule", rx=10, sw=2)
    for i in range(n):
        sheet(f, x + m + i * (sw_ + sgap), y + m, *geo, state="missing" if missing == i else "present",
              mark=mark[1] if mark and mark[0] == i else None)
    rosette(f, x + w - 4, y + 4, broken=broken)
    return w, h


def gate(f: Fig, x, cy, h=56, stroke="fg", notched=False):
    """A checker: a gateway of two posts under a lintel that the route passes through. notched cuts a
    V into the lintel: a changed checker. Returns the x of the far post."""
    top = cy - h / 2
    for px in (x, x + 22):
        f.line(px, top, px, cy + h / 2, stroke, sw=4)
    if notched:
        f.path(f"M{x - 4:.1f} {top:.1f} L{x + 6:.1f} {top:.1f} L{x + 11:.1f} {top + 7:.1f} L{x + 16:.1f} {top:.1f} L{x + 26:.1f} {top:.1f}", stroke=stroke, sw=4, join="miter")
    else:
        f.line(x - 4, top, x + 26, top, stroke, sw=4)
    return x + 22
