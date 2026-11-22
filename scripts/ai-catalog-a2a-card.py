# /// script
# requires-python = ">=3.11"
# dependencies = ["agent-evidence-verify[a2a]==0.5.1"]
# ///
"""Print the A2A agent card that `probity-a2a` from agent-evidence-verify 0.5.1 serves.

The catalog entry for the verify A2A server carries this card inline. The card the
released server serves is the authority, so this script asks the server for it instead
of restating it: the server is built with its own create_app at its default loopback
origin (http://127.0.0.1:41241, the `probity-a2a` default) and no Lab register, and the
card is read from /.well-known/agent-card.json with one in-process ASGI request.

Usage: uv run --script scripts/ai-catalog-a2a-card.py POLICY ARTIFACT_ROOT
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from agent_evidence_verify.a2a_server import create_app

ORIGIN = "http://127.0.0.1:41241"


async def get(app, path: str) -> tuple[int, bytes]:
    """One GET through the ASGI interface, as the server's own HTTP front end would send it."""
    sent: list[dict] = []

    async def receive() -> dict:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict) -> None:
        sent.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "server": ("127.0.0.1", 41241),
        "client": ("127.0.0.1", 50000),
        "path": path,
        "raw_path": path.encode(),
        "root_path": "",
        "query_string": b"",
        "headers": [(b"host", b"127.0.0.1:41241")],
    }
    await app(scope, receive, send)
    status = next(m["status"] for m in sent if m["type"] == "http.response.start")
    body = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
    return status, body


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__.strip().splitlines()[-1], file=sys.stderr)
        return 2
    policy, root = Path(argv[0]).read_bytes(), Path(argv[1])
    status, body = asyncio.run(get(create_app(policy, root, ORIGIN), "/.well-known/agent-card.json"))
    if status != 200:
        print(f"agent card: HTTP {status}", file=sys.stderr)
        return 1
    print(json.dumps(json.loads(body), indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
