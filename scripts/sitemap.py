#!/usr/bin/env python3
"""Write sitemap.xml for the combined site tree, dating each page by when its bytes last changed.

A page's <lastmod> is the UTC date of the publish that last changed that page's bytes. The
dates live in sitemap-ledger.json beside the pages: path -> {sha256, lastmod}. Each run reads the
previous ledger, keeps the date of every page whose digest is unchanged, and stamps today on a page
that is new or whose digest moved. Run twice on the same tree it writes the same bytes, so a
publish with no change to any page changes nothing. The date never comes from a build clock or from
git history, which a shallow checkout truncates into one date for every page.

A page is listed when its canonical link names this host. Pages whose canonical link names another
host (the identifier pages answer under w3id.org) are left out: this host cannot vouch for them.

    python3 scripts/sitemap.py --tree <combined tree> [--prior <ledger.json>] --today YYYY-MM-DD
                               [--changed-out <file>]
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import pathlib
import re
import sys
from xml.sax.saxutils import escape

HOST = "https://probityai.github.io"
LEDGER = "sitemap-ledger.json"
SITEMAP = "sitemap.xml"
SCOPED = ("agent-evidence-atlas",)
CANONICAL = re.compile(r"<link\b[^>]*\brel=[\"']canonical[\"'][^>]*>", re.I)
HREF = re.compile(r"\bhref=[\"']([^\"']+)[\"']", re.I)
NOINDEX = re.compile(r"<meta\b[^>]*\bname=[\"']robots[\"'][^>]*noindex", re.I)
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def canonical_url(text: str) -> str | None:
    """The page's canonical URL on this host, or None when it has none here or says noindex."""
    if NOINDEX.search(text):
        return None
    tag = CANONICAL.search(text)
    href = HREF.search(tag.group(0)) if tag else None
    if href is None:
        return None
    url = html.unescape(href.group(1))
    return url if url == HOST or url.startswith(HOST + "/") else None


def scan(tree: pathlib.Path) -> dict[str, tuple[str, str]]:
    """Map each listed page's tree-relative path to (canonical URL, sha256 of its bytes)."""
    pages: dict[str, tuple[str, str]] = {}
    for path in sorted(tree.rglob("*.html")):
        rel = path.relative_to(tree).as_posix()
        if rel.startswith(".git/"):
            continue
        data = path.read_bytes()
        url = canonical_url(data.decode("utf-8", errors="replace"))
        if url is not None:
            pages[rel] = (url, hashlib.sha256(data).hexdigest())
    return pages


def read_ledger(path: pathlib.Path | None) -> dict[str, dict[str, str]]:
    """The recorded {path: {sha256, lastmod}}; an absent file is an empty ledger, a bad one is fatal."""
    if path is None or not path.is_file():
        return {}
    pages = json.loads(path.read_text(encoding="utf-8")).get("pages", {})
    for rel, row in pages.items():
        if not DATE.match(str(row.get("lastmod", ""))) or not row.get("sha256"):
            raise SystemExit(f"FAIL ledger row {rel} is malformed: {row}")
    return pages


def update(
    pages: dict[str, tuple[str, str]], prior: dict[str, dict[str, str]], today: str
) -> tuple[dict[str, dict[str, str]], list[str]]:
    """New ledger and the URLs of pages that are new or changed since the prior ledger."""
    ledger: dict[str, dict[str, str]] = {}
    changed: list[str] = []
    for rel, (url, digest) in sorted(pages.items()):
        before = prior.get(rel)
        if before is not None and before["sha256"] == digest:
            ledger[rel] = {"sha256": digest, "lastmod": before["lastmod"]}
        else:
            ledger[rel] = {"sha256": digest, "lastmod": today}
            changed.append(url)
    return ledger, changed


def render(entries: list[tuple[str, str]]) -> str:
    """Sitemap XML for (URL, lastmod) pairs, sorted by URL, one entry per URL."""
    seen: dict[str, str] = {}
    for url, lastmod in entries:
        seen[url] = max(lastmod, seen.get(url, ""))
    rows = "".join(
        f"  <url><loc>{escape(url)}</loc><lastmod>{seen[url]}</lastmod></url>\n" for url in sorted(seen)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + rows + "</urlset>\n"
    )


def write(tree: pathlib.Path, pages: dict[str, tuple[str, str]], ledger: dict[str, dict[str, str]]) -> None:
    """Write the ledger, the site sitemap and each scoped section's sitemap into the tree."""
    entries = [(pages[rel][0], ledger[rel]["lastmod"]) for rel in sorted(pages)]
    (tree / SITEMAP).write_text(render(entries), encoding="utf-8")
    for scope in SCOPED:
        prefix = f"{HOST}/{scope}/"
        part = [(url, lastmod) for url, lastmod in entries if url.startswith(prefix)]
        if part:
            (tree / scope / SITEMAP).write_text(render(part), encoding="utf-8")
    body = json.dumps({"version": 1, "pages": ledger}, indent=1, sort_keys=True)
    (tree / LEDGER).write_text(body + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--tree", type=pathlib.Path, required=True)
    parser.add_argument("--prior", type=pathlib.Path, help="previous ledger; default is the tree's own")
    parser.add_argument("--today", required=True, help="UTC date YYYY-MM-DD for new or changed pages")
    parser.add_argument("--changed-out", type=pathlib.Path, help="write the new or changed URLs here")
    args = parser.parse_args(argv)
    if not DATE.match(args.today):
        print(f"FAIL --today must be YYYY-MM-DD, got {args.today!r}")
        return 1
    pages = scan(args.tree)
    if not pages:
        print("FAIL no page in the tree names this host as canonical; nothing to list")
        return 1
    prior = read_ledger(args.prior if args.prior is not None else args.tree / LEDGER)
    ledger, changed = update(pages, prior, args.today)
    write(args.tree, pages, ledger)
    if args.changed_out is not None:
        args.changed_out.write_text("".join(f"{url}\n" for url in changed), encoding="utf-8")
    print(f"{len(pages)} pages listed, {len(changed)} new or changed since the prior ledger")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
