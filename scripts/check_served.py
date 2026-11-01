#!/usr/bin/env python3
"""Check that GitHub Pages serves every published file with the bytes we published.

Reads a tree laid out the way the pages-live branch is (the default is a checkout of
pages-live) and, for every file under agent-evidence-atlas/ and agent-evidence/, fetches
https://probityai.github.io/<path> and compares its SHA-256 with the file's. It also
follows every persistent identifier under https://w3id.org/agent-evidence/ that the
w3id rules map to a page in agent-evidence/, and requires the redirect to land on the
same bytes. Outside adopters and signed records carry these URLs, so a page that moves
or changes without a new publish is a break, not a cosmetic difference.

Prints one line per failure and a final "N of M" line; exits 1 when any URL failed.

    python3 scripts/check_served.py --tree <pages-live checkout> [--sync <token>]
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import pathlib
import sys
import time
import urllib.error
import urllib.request

DESCRIPTION = "Check that GitHub Pages serves every published file with the bytes we published."
HOST = "https://probityai.github.io"
W3ID = "https://w3id.org/agent-evidence"
SERVED_DIRS = ("agent-evidence-atlas", "agent-evidence")
TRIES = 4


def fetch(url: str) -> tuple[int, bytes, str]:
    """Return (status, body, final URL) after redirects; status 0 means no answer."""
    last: tuple[int, bytes, str] = (0, b"", url)
    for attempt in range(TRIES):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "probityai-served-check"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.status, resp.read(), resp.geturl()
        except urllib.error.HTTPError as err:
            last = (err.code, b"", url)
            if err.code == 404:
                return last
        except (urllib.error.URLError, TimeoutError, ConnectionError) as err:
            last = (0, str(err).encode(), url)
        time.sleep(2 * (attempt + 1))
    return last


def targets(tree: pathlib.Path, sync: str) -> list[tuple[str, str, str]]:
    """(label, url, expected sha256) for every served file and every w3id identifier."""
    out: list[tuple[str, str, str]] = []
    suffix = f"?sync={sync}" if sync else ""
    for top in SERVED_DIRS:
        for path in sorted((tree / top).rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(tree).as_posix()
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            out.append((rel, f"{HOST}/{rel}{suffix}", digest))
            # The w3id rules map predicate/v1/<name>, vocab/v1/<term>, the two indexes,
            # the root and the registry YAML files onto agent-evidence/.
            if top == "agent-evidence":
                ident = rel[len("agent-evidence/"):]
                if ident.endswith("index.html"):
                    ident = ident[: -len("index.html")].rstrip("/")
                    out.append((f"w3id:{ident or '/'}", f"{W3ID}/{ident}", digest))
                elif ident.startswith("vocab/v1/registry/") and ident.endswith(".yaml"):
                    out.append((f"w3id:{ident}", f"{W3ID}/{ident}", digest))
    return out


def check(target: tuple[str, str, str]) -> str | None:
    label, url, want = target
    status, body, final = fetch(url)
    if status != 200:
        return f"FAIL {label}: HTTP {status or 'no answer'} from {url}"
    got = hashlib.sha256(body).hexdigest()
    if got != want:
        return f"FAIL {label}: served sha256 {got} at {final}, published {want}"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument("--tree", required=True, type=pathlib.Path)
    parser.add_argument("--sync", default="", help="cache-busting query value")
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args()
    for top in SERVED_DIRS:
        if not (args.tree / top).is_dir():
            print(f"FAIL the tree has no {top}/ directory; nothing was checked")
            return 1
    todo = targets(args.tree, args.sync)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        failures = [r for r in pool.map(check, todo) if r]
    for line in sorted(failures):
        print(line)
    w3id = sum(1 for t in todo if t[0].startswith("w3id:"))
    print(f"{len(todo) - len(failures)} of {len(todo)} URLs answer 200 with the published bytes "
          f"({len(todo) - w3id} Pages files, {w3id} w3id identifiers)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
