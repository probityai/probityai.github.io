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

    def circle(self, cx, cy, r, fill=None, stroke=None, sw=2, dash=None):
        a = {"cx": cx, "cy": cy, "r": r}
        if stroke:
            a["stroke-width"] = sw
        if dash:
            a["stroke-dasharray"] = dash
        self._add("circle", a, fill, stroke)

    def line(self, x1, y1, x2, y2, stroke, sw=2, dash=None):
        a = {"x1": x1, "y1": y1, "x2": x2, "y2": y2, "stroke-width": sw, "stroke-linecap": "round"}
        if dash:
            a["stroke-dasharray"] = dash
        self._add("line", a, None, stroke)

    def path(self, d, fill=None, stroke=None, sw=2, dash=None, join="round", opacity=None):
        a = {"d": d}
        if opacity is not None:
            a["opacity"] = opacity
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
        if fill == "accent":
            raise ValueError("accent is for marks only (the verifier and its route), never text")
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
# sheets in one outline, tied by a cord into a padlock whose body carries a digest mark (#): a signature
# over the files' digest; the verifier is a lens on its route; a kept verdict is a receipt (a small
# dog-eared slip with a check), and kept receipts sit side by side in one folder.

CELL, GAP, SPAD, EAR = 12, 5, 11, 12


def sheet_size(cols=4, rows=3, cell=CELL, gap=GAP, pad=SPAD):
    return cols * cell + (cols - 1) * gap + 2 * pad, rows * cell + (rows - 1) * gap + 2 * pad + EAR / 2


def _eared(x, y, w, h, ear):
    return f"M{x:.1f} {y:.1f} L{x + w - ear:.1f} {y:.1f} L{x + w:.1f} {y + ear:.1f} L{x + w:.1f} {y + h:.1f} L{x:.1f} {y + h:.1f} Z"


def sheet(f: Fig, x, y, cols=4, rows=3, cell=CELL, gap=GAP, pad=SPAD, state="present", mark=None):
    """A file sheet. state "missing" draws a dashed hollow outline in absent ink (not there, not failed).
    mark (col, row) is the one byte cell drawn in loss ink, enlarged well past its neighbours and ringed
    in the card colour so it reads at thumbnail size: the changed byte."""
    w, h = sheet_size(cols, rows, cell, gap, pad)
    outline = _eared(x, y, w, h, EAR)
    if state == "missing":
        f.path(outline, stroke="absent", sw=4.5, dash="9 5")
        return w, h
    f.path(outline, fill="tile", stroke="rule", sw=2, join="round")
    f.path(f"M{x + w - EAR:.1f} {y:.1f} L{x + w - EAR:.1f} {y + EAR:.1f} L{x + w:.1f} {y + EAR:.1f}", stroke="rule", sw=2)
    top = y + pad + EAR / 2
    for r in range(rows):
        for c in range(cols):
            cx, cy = x + pad + c * (cell + gap), top + r * (cell + gap)
            if mark != (c, r):
                f.rect(cx, cy, cell, cell, fill="byte", rx=2)
    if mark:
        c, r = mark
        cx, cy = x + pad + c * (cell + gap), top + r * (cell + gap)
        g = cell * 0.9
        f.rect(cx - g - 2, cy - g - 2, cell + 2 * g + 4, cell + 2 * g + 4, fill="card", rx=5)
        f.rect(cx - g, cy - g, cell + 2 * g, cell + 2 * g, fill="loss", rx=4)
    return w, h


def lock(f: Fig, cx, cy, r=12, broken=False):
    """The archive's signature: a padlock centred on (cx, cy) whose solid body carries a digest mark (#)
    knocked out in the card colour, so it reads as a lock over a digest, not an award. r is half the body
    width. broken swings the shackle open off its right post, snapped, in loss ink: the seal no longer
    holds."""
    bw, bh = 2 * r, 1.6 * r
    bx, by = cx - r, cy - bh * 0.3
    sr = r * 0.62                                 # shackle radius
    sw = max(3.0, r * 0.32)
    f.circle(cx, cy, r * 1.9, fill="card")
    if broken:
        # the shackle swung up and open: its left post leaves the body
        f.path(f"M{cx + sr:.1f} {by:.1f} L{cx + sr:.1f} {by - sr * 0.9:.1f} A{sr:.1f} {sr:.1f} 0 0 0 {cx - sr * 0.9:.1f} {by - sr * 2.1:.1f}",
               stroke="loss", sw=sw)
    else:
        f.path(f"M{cx - sr:.1f} {by:.1f} L{cx - sr:.1f} {by - sr * 0.6:.1f} A{sr:.1f} {sr:.1f} 0 0 1 {cx + sr:.1f} {by - sr * 0.6:.1f} L{cx + sr:.1f} {by:.1f}",
               stroke="fg", sw=sw)
    f.rect(bx, by, bw, bh, fill="fg", rx=r * 0.25)
    # the digest mark: two uprights and two bars, in the card colour
    hw, hs = r * 0.62, max(1.6, r * 0.13)
    hy = by + bh / 2
    for d in (-1, 1):
        f.line(cx + d * hw * 0.28 + hw * 0.08, hy - hw * 0.55, cx + d * hw * 0.28 - hw * 0.08, hy + hw * 0.55, "card", sw=hs)
        f.line(cx - hw * 0.5, hy + d * hw * 0.22, cx + hw * 0.5, hy + d * hw * 0.22, "card", sw=hs)


def archive(f: Fig, x, y, n=3, missing=None, mark=None, geo=(4, 3, CELL, GAP, SPAD), sgap=14, broken=False, lock_r=12):
    """n sheets in one outline, tied by a thin cord that runs across every sheet into the padlock on the
    right edge. Returns (width, height)."""
    sw_, sh_ = sheet_size(*geo)
    m = 12
    w = 2 * m + n * sw_ + (n - 1) * sgap
    h = 2 * m + sh_
    f.rect(x, y, w, h, stroke="rule", rx=10, sw=2)
    for i in range(n):
        sheet(f, x + m + i * (sw_ + sgap), y + m, *geo, state="missing" if missing == i else "present",
              mark=mark[1] if mark and mark[0] == i else None)
    # the lock's cord: one thin strap across every sheet into the lock, so the lock reads as binding the
    # files; broken cuts a gap in the cord over the changed sheet and breaks the lock
    by, bh = y + m + EAR / 2 + 2, 3
    x0, x1 = x + m - 4, x + w - 2
    if broken and mark:
        c0 = x + m + mark[0] * (sw_ + sgap) + sw_ * 0.2
        c1 = c0 + sw_ * 0.6
        f.rect(x0, by, c0 - x0, bh, fill="fg")
        f.rect(c1, by, x1 - c1, bh, fill="fg")
    else:
        f.rect(x0, by, x1 - x0, bh, fill="fg")
    lock(f, x1, by + bh / 2 + lock_r * 0.2, r=lock_r * 0.8, broken=broken)
    return w, h


def archive_size(n=3, geo=(4, 3, CELL, GAP, SPAD), sgap=14):
    sw_, sh_ = sheet_size(*geo)
    return 24 + n * sw_ + (n - 1) * sgap, 24 + sh_


def lens(f: Fig, cx, cy, r=20, stroke="accent", found=None):
    """The verifier: a magnifying lens on the route, handle down-right. found draws what it caught inside
    the glass and turns the rim to loss ink: "hole" is the missing sheet's dashed dog-eared outline, in the
    missing sheet's own absent ink."""
    rim = "loss" if found else stroke
    f.line(cx + r * 0.72, cy + r * 0.72, cx + r * 1.5, cy + r * 1.5, rim, sw=6)
    f.circle(cx, cy, r, fill="card", stroke=rim, sw=4)
    if found == "hole":
        hw, hh = r * 0.76, r * 0.96
        f.path(_eared(cx - hw / 2, cy - hh / 2, hw, hh, hw / 3), stroke="absent", sw=2.5, dash="4 3")
    return cx + r


def receipt(f: Fig, x, cy, h=48, ink="rule"):
    """A kept record of a verdict: a dog-eared slip (tile fill, outline in ink) with two lines of text
    strokes and a check in its lower half."""
    w = round(h * 0.78, 1)
    ear = h * 0.26
    y = cy - h / 2
    f.path(_eared(x, y, w, h, ear), fill="tile", stroke=ink, sw=2.5)
    f.path(f"M{x + w - ear:.1f} {y:.1f} L{x + w - ear:.1f} {y + ear:.1f} L{x + w:.1f} {y + ear:.1f}", stroke=ink, sw=2.5)
    for k, right in ((0, w - ear - 4), (1, w - 6)):
        f.line(x + 6, y + ear * 0.55 + 4 + k * 8, x + right, y + ear * 0.55 + 4 + k * 8, "rule", sw=2.5)
    g = w * 0.5
    f.glyph("check", x + (w - g) / 2, y + h - g - 4, g, "fg", sw=2.5)
    return x + w


def folder(f: Fig, x, y, w, h, ink="fg"):
    """A filing folder: a rounded pocket with a tab on its top-left edge. What sits inside is kept."""
    tw, th = min(56, w * 0.4), 9
    f.path(f"M{x:.1f} {y + 6:.1f} Q{x:.1f} {y:.1f} {x + 6:.1f} {y:.1f} L{x + tw:.1f} {y:.1f} L{x + tw + th:.1f} {y + th:.1f} "
           f"L{x + w - 6:.1f} {y + th:.1f} Q{x + w:.1f} {y + th:.1f} {x + w:.1f} {y + th + 6:.1f} L{x + w:.1f} {y + h - 6:.1f} "
           f"Q{x + w:.1f} {y + h:.1f} {x + w - 6:.1f} {y + h:.1f} L{x + 6:.1f} {y + h:.1f} Q{x:.1f} {y + h:.1f} {x:.1f} {y + h - 6:.1f} Z",
           stroke=ink, sw=2.5)


def arrow(f: Fig, x, y, ink="accent", size=9, direction="right"):
    """A solid arrowhead with its tip at (x, y), pointing right or down."""
    if direction == "right":
        d = f"M{x:.1f} {y:.1f} L{x - size * 1.2:.1f} {y - size * 0.75:.1f} L{x - size * 1.2:.1f} {y + size * 0.75:.1f} Z"
    else:
        d = f"M{x:.1f} {y:.1f} L{x - size * 0.75:.1f} {y - size * 1.2:.1f} L{x + size * 0.75:.1f} {y - size * 1.2:.1f} Z"
    f.path(d, fill=ink, stroke=ink, sw=1)


def strike(f: Fig, x, y, r=7, ink="loss"):
    """Where a fault strikes the route: a dot in the fault's ink ringed in the card colour."""
    f.circle(x, y, r + 3, fill="card")
    f.circle(x, y, r, fill=ink)
