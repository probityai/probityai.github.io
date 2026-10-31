#!/usr/bin/env python3
"""Restore or check the Atlas experiment archives listed in ARCHIVES.json.

The experiment archives (*.zip) are served with the Atlas and read by its retention
tests, but they are not tracked in git: each one is an asset of the release that
ARCHIVES.json names, stored once per SHA-256. This keeps the tree small and keeps every
archive URL and every byte the pages link to unchanged.

    python3 tools/archives.py fetch [--from DIR]   restore every archive at its path
    python3 tools/archives.py check                refuse a tracked or unlisted archive

fetch refuses any download whose SHA-256 or size differs from the manifest. check
fails when git tracks a *.zip under this tree, or when a *.zip on disk is missing from
the manifest, so a new archive cannot slip into the tree or out of the release.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
import sys
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "ARCHIVES.json"
RELEASES = "https://github.com/probityai/probityai.github.io/releases/download"


def load() -> dict:
    return json.loads(MANIFEST.read_text())


def download(url: str) -> bytes:
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=120) as resp:
                return resp.read()
        except OSError as err:
            if attempt == 3:
                raise SystemExit(f"archives: cannot download {url}: {err}")
            time.sleep(3 * (attempt + 1))
    raise AssertionError("unreachable")


def fetch(source: pathlib.Path | None) -> int:
    man = load()
    cache: dict[str, bytes] = {}
    for row in man["archives"]:
        dest = ROOT / row["path"]
        if dest.is_file() and hashlib.sha256(dest.read_bytes()).hexdigest() == row["sha256"]:
            continue
        data = cache.get(row["asset"])
        if data is None:
            if source is not None:
                data = (source / row["asset"]).read_bytes()
            else:
                data = download(f"{RELEASES}/{man['release']}/{row['asset']}")
            if hashlib.sha256(data).hexdigest() != row["sha256"] or len(data) != row["size"]:
                print(f"archives: {row['asset']} does not match its manifest digest or size", file=sys.stderr)
                return 1
            cache[row["asset"]] = data
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    print(f"archives: {len(man['archives'])} archives present ({len(cache)} restored)")
    return 0


def check() -> int:
    listed = {row["path"] for row in load()["archives"]}
    tracked = subprocess.run(["git", "ls-files", "--", "*.zip"], cwd=ROOT, capture_output=True,
                             text=True, check=True).stdout.split()
    on_disk = {p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*.zip")}
    problems = [f"tracked in git, belongs in the release: {p}" for p in tracked]
    problems += [f"on disk but not in ARCHIVES.json: {p}" for p in sorted(on_disk - listed)]
    for line in problems:
        print(f"archives: {line}", file=sys.stderr)
    if problems:
        return 1
    print(f"archives: {len(listed)} listed, none tracked in git")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("--from", dest="source", type=pathlib.Path)
    sub.add_parser("check")
    args = parser.parse_args()
    return fetch(args.source) if args.cmd == "fetch" else check()


if __name__ == "__main__":
    sys.exit(main())
