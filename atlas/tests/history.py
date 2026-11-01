"""Read a file of the Atlas as it stood at an earlier commit, from pinned records.

The retention tests compare today's register and packets with the bytes at a baseline
commit. Those commits are in the history of probityai/agent-evidence-vectors, where the
Atlas lived under site/ until 2026-10-31; this repository does not hold that history. So
each baseline file the tests read is pinned in history/HISTORY.json, which records the
source repository, the commit, the path it had there and its SHA-256. The bytes come from
history/<commit>/<path> when the file has since changed, from the restored experiment
archive when it is one (ARCHIVES.json), and otherwise from today's file. A baseline equal
to today's file is not copied: the recorded digest is the pin, so if today's file changes,
the read below finds no source with that digest and fails loudly.

To pin a new baseline, set ATLAS_HISTORY_FROM to a clone of agent-evidence-vectors and run
the test that reads it; show() then reads the file from that clone's history and records it.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

from imported_commits import here

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "history"
INDEX = STORE / "HISTORY.json"
SOURCE_REPO = "probityai/agent-evidence-vectors"
SOURCE_PREFIX = "site/"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _index() -> dict[str, dict[str, str]]:
    return json.loads(INDEX.read_text()) if INDEX.exists() else {}


def _archive(digest: str) -> Path | None:
    """A restored experiment archive with this SHA-256, if ARCHIVES.json lists one."""
    for row in json.loads((ROOT / "ARCHIVES.json").read_text())["archives"]:
        if row["sha256"] == digest:
            return ROOT / row["path"]
    return None


def _pin(commit: str, path: str, clone: Path) -> bytes:
    data = subprocess.run(["git", "-C", str(clone), "show", f"{commit}:{SOURCE_PREFIX}{path}"],
                          capture_output=True, check=True).stdout
    digest = _sha(data)
    current = ROOT / path
    unchanged = current.is_file() and _sha(current.read_bytes()) == digest
    if _archive(digest) is None and not unchanged:
        target = STORE / commit / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    index = _index()
    index[f"{commit}:{path}"] = {"repository": SOURCE_REPO, "commit": commit,
                                 "path": SOURCE_PREFIX + path, "sha256": digest}
    STORE.mkdir(parents=True, exist_ok=True)
    INDEX.write_text(json.dumps(dict(sorted(index.items())), indent=2) + "\n")
    return data


def show(revision: str, path: str) -> bytes:
    """The bytes of Atlas-relative ``path`` at source commit ``revision``."""
    commit = here(revision)
    path = path.removeprefix("./")
    record = _index().get(f"{commit}:{path}")
    if record is None:
        clone = os.environ.get("ATLAS_HISTORY_FROM")
        if not clone:
            raise FileNotFoundError(f"no pinned history for {commit}:{path}; see tests/history.py")
        return _pin(commit, path, Path(clone))
    stored = STORE / commit / path
    archive = _archive(record["sha256"])
    source = stored if stored.is_file() else archive if archive is not None else ROOT / path
    data = source.read_bytes() if source.is_file() else b""
    if _sha(data) != record["sha256"]:
        raise ValueError(f"no source for pinned history {commit}:{path} matches its recorded SHA-256")
    return data
