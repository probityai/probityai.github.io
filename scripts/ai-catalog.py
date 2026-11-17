# /// script
# requires-python = ">=3.11"
# dependencies = ["cryptography==50.0.2"]
# ///
"""Build, sign and check the signed AI Catalog this site serves at /.well-known/ai-catalog.json.

catalog/source.json is the only file edited by hand: the host, and per entry its identifier, type,
version, tags, publisher, inline `data` and the repository it is published from (`source`). From
it this script writes:

  .well-known/ai-catalog.json  every entry with `digest` (SHA-256 of the RFC 8785 bytes of `data`)
                               and two publisher trust manifests over the same subject: one in
                               `trustManifests` under the AI Catalog construction
                               (ai-catalog-2026-11) and one in `trustManifest` under the ARD draft
                               construction (ard-draft-bu-00); then a whole-catalog signature
                               (ai-catalog-snapshot) over everything else.
  .well-known/did.json         the did:web document of did:web:probityai.github.io that holds the
                               signing key as its only assertion method.
  catalog/signing-key.json     the public key and its SHA-256 pin, for consumers and for `check`.

Every signature is a detached compact JWS, ES256 with a raw r || s signature.

  sign   ai-catalog.py sign --days 365 < private-key.pem
         The private key comes on standard input, never from a file in this repository; it lives
         in the operator's keyring (service probityai-ai-catalog, account es256-private-key-pem).
  check  ai-catalog.py check [--at RFC3339] [--a2a-card FILE] [--emit-cases DIR]
         Without the key: the published catalog is the source plus digests and manifests (nothing
         edited by hand), did.json holds the pinned key, every signature verifies with this
         script's own JWS code, and each signature is current at --at (default now) with at least
         30 days left. With
         --a2a-card, the A2A entry's data must equal the card the released server serves. With
         --emit-cases, writes the inputs the two independent readers judge (see `judge`). With
         --live, every release the entries point at is read from its source: each commit exists,
         each tag names its commit, and each PyPI file has the digest the entry signs.
  judge  ai-catalog.py judge DIR --verify CMD --vectors CMD
         Runs agent-evidence-verify (claim catalog_trust_manifest/v1) and the agent-evidence-vectors
         reference reader over every emitted case and requires `supported` / `accept` for each
         entry under both constructions and for the snapshot, and a refusal from both readers for
         each tampered copy, so a reader that passes everything fails this step.
"""

from __future__ import annotations

import argparse
import base64
import copy
import datetime as dt
import hashlib
import json
import os
import shlex
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature, encode_dss_signature

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "catalog" / "source.json"
PIN = ROOT / "catalog" / "signing-key.json"
CATALOG = ROOT / ".well-known" / "ai-catalog.json"
DID_DOC = ROOT / ".well-known" / "did.json"

DID = "did:web:probityai.github.io"
KID = DID + "#catalog-es256"
PROFILE = "did-web-v1"
AIC, ARD, SNAPSHOT = "ai-catalog-2026-11", "ard-draft-bu-00", "ai-catalog-snapshot"
TYP = {AIC: "ai-catalog-trust-manifest+jws", SNAPSHOT: "ai-catalog+jws"}
PASS = {
    AIC: ("supported", "signature_covers_release", "accept"),
    ARD: ("supported", "signature_covers_release", "accept"),
    SNAPSHOT: ("supported", "snapshot_signature_valid", "accept"),
}
SAFE = 2**53 - 1
A2A_TYPE = "application/a2a-agent-card+json"
# The weekly CI run fails this long before the signatures expire, so a stale catalog is never served.
RENEW = dt.timedelta(days=30)


class Failure(Exception):
    """A check that did not hold; the message says which and where."""


# ----------------------------------------------------------------------------- bytes


def strict_loads(raw: bytes) -> Any:
    """JSON with a duplicate member name refused, so one file is never read two ways."""

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in items:
            if key in out:
                raise Failure(f"duplicate member name {key!r}")
            out[key] = value
        return out

    return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs)


def _string(text: str) -> str:
    out = ['"']
    for ch in text:
        code = ord(ch)
        if ch in '"\\':
            out.append("\\" + ch)
        elif code < 0x20:
            out.append({8: "\\b", 9: "\\t", 10: "\\n", 12: "\\f", 13: "\\r"}.get(code, f"\\u{code:04x}"))
        elif 0xD800 <= code <= 0xDFFF:
            raise Failure("a lone surrogate has no RFC 8785 form")
        else:
            out.append(ch)
    return "".join(out) + '"'


def canonical(value: Any) -> bytes:
    """RFC 8785 bytes for the JSON this catalog holds: no fractions, integers within 2**53 - 1."""

    def ser(v: Any) -> str:
        if v is None:
            return "null"
        if v is True:
            return "true"
        if v is False:
            return "false"
        if isinstance(v, int):
            if abs(v) > SAFE:
                raise Failure(f"integer {v} is past 2**53 - 1")
            return str(v)
        if isinstance(v, float):
            raise Failure("the catalog holds no fractional numbers")
        if isinstance(v, str):
            return _string(v)
        if isinstance(v, list):
            return "[" + ",".join(ser(x) for x in v) + "]"
        if isinstance(v, dict):
            keys = sorted(v, key=lambda k: k.encode("utf-16-be"))
            return "{" + ",".join(_string(k) + ":" + ser(v[k]) for k in keys) + "}"
        raise Failure(f"no JSON form for {type(v).__name__}")

    return ser(value).encode("utf-8")


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(text: str) -> bytes:
    if "=" in text or any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for c in text):
        raise Failure("not unpadded base64url")
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value)).hexdigest()


def dump(value: Any) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


# ----------------------------------------------------------------------------- keys


def jwk_of(public: ec.EllipticCurvePublicKey) -> dict[str, str]:
    numbers = public.public_numbers()
    return {
        "crv": "P-256",
        "kty": "EC",
        "x": b64url(numbers.x.to_bytes(32, "big")),
        "y": b64url(numbers.y.to_bytes(32, "big")),
    }


def public_of(jwk: dict[str, str]) -> ec.EllipticCurvePublicKey:
    if jwk.get("kty") != "EC" or jwk.get("crv") != "P-256" or set(jwk) != {"crv", "kty", "x", "y"}:
        raise Failure("the signing key is not a bare P-256 public JWK")
    x, y = b64url_decode(jwk["x"]), b64url_decode(jwk["y"])
    if len(x) != 32 or len(y) != 32:
        raise Failure("the signing key coordinates are not 32 bytes")
    return ec.EllipticCurvePublicNumbers(
        int.from_bytes(x, "big"), int.from_bytes(y, "big"), ec.SECP256R1()
    ).public_key()


def pin_of(jwk: dict[str, str]) -> dict[str, Any]:
    point = b"\x04" + b64url_decode(jwk["x"]) + b64url_decode(jwk["y"])
    return {"kid": KID, "publicKeyJwk": jwk, "public_key_sha256": hashlib.sha256(point).hexdigest()}


def did_document(jwk: dict[str, str]) -> dict[str, Any]:
    return {
        "@context": ["https://www.w3.org/ns/did/v1"],
        "id": DID,
        "verificationMethod": [{"id": KID, "type": "JsonWebKey2020", "controller": DID, "publicKeyJwk": jwk}],
        "assertionMethod": [KID],
    }


# ----------------------------------------------------------------------------- the catalog


def unsigned(source: dict[str, Any], issued: str, expires: str) -> dict[str, Any]:
    """The catalog the source describes, every signature slot present and every jws absent."""
    window = {"issuedAt": issued, "expiresAt": expires}
    entries = []
    for item in source["entries"]:
        entry = {
            key: item[key] for key in ("identifier", "type", "version", "tags", "publisher", "data") if key in item
        }
        entry["digest"] = digest(item["data"])
        subject = {key: entry[key] for key in ("identifier", "type", "digest", "version") if key in entry}
        entry["trustManifests"] = [
            {
                "contributor": DID,
                "subject": subject,
                "provenance": [{"relation": "publishedFrom", "sourceId": item["source"]}],
                "signature": {"signer": DID, "profile": PROFILE, **window},
            }
        ]
        entry["trustManifest"] = {"identity": DID, "subject": copy.deepcopy(subject), **window}
        entries.append(entry)
    return {
        "specVersion": source["specVersion"],
        "host": source["host"],
        "entries": entries,
        "signature": {"signer": DID, "profile": PROFILE, **window},
    }


def payload(construction: str, catalog: dict[str, Any], index: int | None) -> Any:
    """The JSON value whose RFC 8785 bytes a construction signs (AI Catalog and draft section 3.5)."""
    if construction == SNAPSHOT:
        out = copy.deepcopy(catalog)
        out["signature"].pop("jws", None)
        out.pop("additionalSignatures", None)
        return out
    entry = catalog["entries"][index]
    if construction == AIC:
        out = copy.deepcopy(entry["trustManifests"][0])
        out["signature"].pop("jws", None)
        out.pop("additionalSignatures", None)
        return out
    out = copy.deepcopy(entry["trustManifest"])
    out.pop("signature", None)
    return out


def header(construction: str) -> str:
    fields = {"alg": "ES256", "kid": KID}
    if construction in TYP:
        fields["typ"] = TYP[construction]
    return b64url(canonical(fields))


def sign_one(key: ec.EllipticCurvePrivateKey, construction: str, value: Any) -> str:
    protected = header(construction)
    message = protected.encode("ascii") + b"." + b64url(canonical(value)).encode("ascii")
    r, s = decode_dss_signature(key.sign(message, ec.ECDSA(hashes.SHA256())))
    return f"{protected}..{b64url(r.to_bytes(32, 'big') + s.to_bytes(32, 'big'))}"


def verify_one(public: ec.EllipticCurvePublicKey, construction: str, value: Any, jws: Any, where: str) -> None:
    if not isinstance(jws, str) or jws.count(".") != 2 or jws.split(".")[1] != "":
        raise Failure(f"{where}: not a detached compact JWS")
    protected, _, signature = jws.split(".")
    if protected != header(construction):
        raise Failure(f"{where}: protected header is not the {construction} header for {KID}")
    raw = b64url_decode(signature)
    if len(raw) != 64:
        raise Failure(f"{where}: ES256 signature is not 64 bytes")
    der = encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big"))
    message = protected.encode("ascii") + b"." + b64url(canonical(value)).encode("ascii")
    try:
        public.verify(der, message, ec.ECDSA(hashes.SHA256()))
    except InvalidSignature as exc:
        raise Failure(f"{where}: signature does not verify") from exc


def signed(source: dict[str, Any], key: ec.EllipticCurvePrivateKey, issued: str, expires: str) -> dict[str, Any]:
    catalog = unsigned(source, issued, expires)
    for index, entry in enumerate(catalog["entries"]):
        entry["trustManifests"][0]["signature"]["jws"] = sign_one(key, AIC, payload(AIC, catalog, index))
        entry["trustManifest"]["signature"] = sign_one(key, ARD, payload(ARD, catalog, index))
    catalog["signature"]["jws"] = sign_one(key, SNAPSHOT, payload(SNAPSHOT, catalog, None))
    return catalog


def stamp(moment: dt.datetime) -> str:
    return moment.astimezone(dt.UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def instant(text: str) -> dt.datetime:
    return dt.datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.UTC)


# ----------------------------------------------------------------------------- commands


def cmd_sign(args: argparse.Namespace) -> int:
    key = serialization.load_pem_private_key(sys.stdin.buffer.read(), password=None)
    if not isinstance(key, ec.EllipticCurvePrivateKey) or key.curve.name != "secp256r1":
        raise Failure("the private key on standard input is not a P-256 key")
    jwk = jwk_of(key.public_key())
    if PIN.exists() and strict_loads(PIN.read_bytes())["publicKeyJwk"] != jwk:
        raise Failure("this key is not the pinned catalog key; rotate the pin on purpose, not by signing")
    now = dt.datetime.now(dt.UTC)
    catalog = signed(strict_loads(SOURCE.read_bytes()), key, stamp(now), stamp(now + dt.timedelta(days=args.days)))
    CATALOG.parent.mkdir(exist_ok=True)
    CATALOG.write_bytes(dump(catalog))
    DID_DOC.write_bytes(dump(did_document(jwk)))
    PIN.write_bytes(dump(pin_of(jwk)))
    print(f"signed {len(catalog['entries'])} entries under {AIC} and {ARD}, and the catalog under {SNAPSHOT}")
    return 0


def check_published(at: dt.datetime) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    source = strict_loads(SOURCE.read_bytes())
    catalog = strict_loads(CATALOG.read_bytes())
    document = strict_loads(DID_DOC.read_bytes())
    pin = strict_loads(PIN.read_bytes())
    jwk = pin["publicKeyJwk"]
    if pin != pin_of(jwk):
        raise Failure("catalog/signing-key.json: the pin does not match its own key")
    if document != did_document(jwk):
        raise Failure(".well-known/did.json is not the did:web document of the pinned key")
    public = public_of(jwk)
    window = catalog.get("signature", {})
    issued, expires = window.get("issuedAt"), window.get("expiresAt")
    if not isinstance(issued, str) or not isinstance(expires, str):
        raise Failure("the catalog signature carries no issuedAt and expiresAt")
    stripped = copy.deepcopy(catalog)
    stripped["signature"].pop("jws", None)
    for entry in stripped.get("entries", []):
        entry["trustManifests"][0]["signature"].pop("jws", None)
        entry["trustManifest"].pop("signature", None)
    if stripped != unsigned(source, issued, expires):
        raise Failure(".well-known/ai-catalog.json is not catalog/source.json signed; re-run `sign`")
    for index, entry in enumerate(catalog["entries"]):
        name = entry["identifier"]
        verify_one(
            public, AIC, payload(AIC, catalog, index), entry["trustManifests"][0]["signature"]["jws"], f"{name} {AIC}"
        )
        verify_one(public, ARD, payload(ARD, catalog, index), entry["trustManifest"]["signature"], f"{name} {ARD}")
    verify_one(public, SNAPSHOT, payload(SNAPSHOT, catalog, None), catalog["signature"]["jws"], SNAPSHOT)
    if not instant(issued) <= at < instant(expires):
        raise Failure(f"the signatures are not current at {stamp(at)} (issued {issued}, expire {expires}); re-sign")
    if at + RENEW >= instant(expires):
        raise Failure(f"the signatures expire {expires}, within {RENEW.days} days of {stamp(at)}; re-sign now")
    return catalog, document, pin


def emit(directory: Path, catalog: dict[str, Any], document: dict[str, Any], pin: dict[str, Any], at: str) -> int:
    """Case inputs for both readers: each entry under both constructions, the snapshot, and one
    tampered copy per construction that both readers must refuse."""
    raw = CATALOG.read_bytes()
    documents = canonical({DID: document})
    tampered = copy.deepcopy(catalog)
    first = tampered["entries"][0]
    first["data"] = {**first["data"], "description": first["data"].get("description", "") + " (edited)"}
    edited = dump(tampered)
    jobs = [(f"{i:02d}-{c}", raw, c, i, True) for i in range(len(catalog["entries"])) for c in (AIC, ARD)]
    jobs.append(("snapshot", raw, SNAPSHOT, 0, True))
    jobs += [(f"tampered-{c}", edited, c, 0, False) for c in (AIC, ARD, SNAPSHOT)]
    assessments, plan = {}, []
    for name, body, construction, index, expect in jobs:
        case = directory / "cases" / name
        case.mkdir(parents=True, exist_ok=True)
        (case / "catalog.json").write_bytes(body)
        (case / "did-documents.json").write_bytes(documents)
        (case / "context.json").write_bytes(
            dump(
                {
                    "at": at,
                    "attestationFiles": [],
                    "construction": construction,
                    "entry": index,
                    "manifest": 0,
                    "role": "publisher",
                }
            )
        )
        case_id = f"own-ai-catalog-{name}"
        (case / "case.json").write_bytes(
            dump(
                {
                    "schema_version": "probity-case/v1",
                    "case_id": case_id,
                    "artifacts": {
                        file: {"path": file, "length": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                        for file, data in (("catalog.json", body), ("did-documents.json", documents))
                    },
                }
            )
        )
        assessments[case_id] = {
            "claim_type": "catalog_trust_manifest/v1",
            "catalog": "catalog.json",
            "did_documents": "did-documents.json",
            "construction": construction,
            "role": "publisher",
            "at": at,
            "entry": index,
            "manifest": 0,
            "key_authority": {
                "kind": "pin",
                "keys": [{"kid": pin["kid"], "public_key_sha256": pin["public_key_sha256"]}],
            },
        }
        plan.append({"name": name, "construction": construction, "expect_pass": expect})
    (directory / "policy.json").write_bytes(dump({"schema_version": "probity-policy/v1", "assessments": assessments}))
    (directory / "plan.json").write_bytes(dump(plan))
    return len(plan)


def fetch_json(url: str) -> Any:
    headers = {"User-Agent": "probityai-ai-catalog-check", "Accept": "application/json"}
    token = os.environ.get("GH_TOKEN")
    if token and url.startswith("https://api.github.com/"):
        headers["Authorization"] = f"Bearer {token}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as resp:
            return json.loads(resp.read())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise Failure(f"could not read {url}: {exc}") from exc


def pypi_files(name: str, version: str) -> dict[str, str]:
    release = fetch_json(f"https://pypi.org/pypi/{name}/{version}/json")
    return {item["filename"]: item["digests"]["sha256"] for item in release["urls"]}


def check_live(catalog: dict[str, Any]) -> int:
    """Each pointer the entries sign resolves to what they say, read from the registry or forge."""
    checked = 0
    for entry in catalog["entries"]:
        data, name = entry["data"], entry["identifier"]
        if entry["type"] == "application/vnd.probityai.release+json":
            repo = data["repository"].removeprefix("https://github.com/")
            commit = fetch_json(f"https://api.github.com/repos/{repo}/commits/{data['commit']}")
            if commit.get("sha") != data["commit"]:
                raise Failure(f"{name}: commit {data['commit']} is not in {repo}")
            if "tag" in data:
                ref = fetch_json(f"https://api.github.com/repos/{repo}/git/ref/tags/{data['tag']}")["object"]
                if ref["type"] == "tag":
                    ref = fetch_json(ref["url"])["object"]
                if ref["sha"] != data["commit"]:
                    raise Failure(f"{name}: tag {data['tag']} names {ref['sha']}, not {data['commit']}")
            for package in data.get("packages", []):
                served = pypi_files(package["name"], package["version"])
                for item in package["files"]:
                    if served.get(item["filename"]) != item["sha256"]:
                        raise Failure(f"{name}: PyPI {item['filename']} is not {item['sha256']}")
            checked += 1
        elif entry["type"] == "application/mcp-registry-server+json":
            for package in data["packages"]:
                if not pypi_files(package["identifier"], package["version"]):
                    raise Failure(f"{name}: PyPI has no files for {package['identifier']} {package['version']}")
            checked += 1
        elif entry["type"] == A2A_TYPE:
            if not pypi_files("agent-evidence-verify", entry["version"]):
                raise Failure(f"{name}: PyPI has no agent-evidence-verify {entry['version']}")
            checked += 1
        else:
            raise Failure(f"{name}: no live check for type {entry['type']}")
    return checked


def cmd_check(args: argparse.Namespace) -> int:
    at = instant(args.at) if args.at else dt.datetime.now(dt.UTC).replace(microsecond=0)
    catalog, document, pin = check_published(at)
    if args.a2a_card:
        served = strict_loads(Path(args.a2a_card).read_bytes())
        cards = [e for e in catalog["entries"] if e["type"] == A2A_TYPE]
        if len(cards) != 1 or cards[0]["data"] != served:
            raise Failure("the A2A entry's data is not the card the released server serves")
        if cards[0].get("version") != served.get("version"):
            raise Failure("the A2A entry's version is not the served card's version")
    if args.live:
        print(f"ai-catalog: {check_live(catalog)} of {len(catalog['entries'])} entries resolve at their source")
    count = len(catalog["entries"])
    print(f"ai-catalog: {count} entries, {2 * count + 1} signatures verify with the pinned key at {stamp(at)}")
    if args.emit_cases:
        print(
            f"ai-catalog: wrote {emit(Path(args.emit_cases), catalog, document, pin, stamp(at))} cases "
            f"to {args.emit_cases}"
        )
    return 0


def run_reader(command: list[str]) -> dict[str, Any]:
    done = subprocess.run(command, capture_output=True, text=True, check=False)
    try:
        answer = json.loads(done.stdout)
    except json.JSONDecodeError as exc:
        raise Failure(
            f"{shlex.join(command)} exited {done.returncode} with no JSON: {done.stdout[-400:]}{done.stderr[-400:]}"
        ) from exc
    if not isinstance(answer, dict) or not isinstance(answer.get("decision"), str):
        raise Failure(f"{shlex.join(command)} printed no decision")
    return answer


def cmd_judge(args: argparse.Namespace) -> int:
    directory = Path(args.directory)
    plan = strict_loads((directory / "plan.json").read_bytes())
    verify, vectors = shlex.split(args.verify), shlex.split(args.vectors)
    wrong = []
    for job in plan:
        case = directory / "cases" / job["name"]
        mine = run_reader([*verify, str(case / "case.json"), "--policy", str(directory / "policy.json"), "--json"])
        theirs = run_reader([*vectors, "catalog-trust-manifest/v1", str(case), "--json"])
        decision, reason, accept = PASS[job["construction"]]
        if job["expect_pass"]:
            ok = (mine["decision"], mine.get("reason")) == (decision, reason) and (
                theirs["decision"],
                theirs.get("reason"),
            ) == (accept, reason)
        else:
            ok = mine["decision"] == "contradicted" and theirs["decision"] == "reject"
        line = (
            f"{job['name']}: agent-evidence-verify {mine['decision']} {mine.get('reason')}; "
            f"vectors reader {theirs['decision']} {theirs.get('reason')}"
        )
        print(("ok    " if ok else "WRONG ") + line)
        if not ok:
            wrong.append(job["name"])
    print(f"ai-catalog judge: {len(plan) - len(wrong)} of {len(plan)} cases as expected")
    return 1 if wrong else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sign = sub.add_parser("sign", help="sign catalog/source.json with the PEM key on standard input")
    sign.add_argument("--days", type=int, default=365)
    sign.set_defaults(run=cmd_sign)
    check = sub.add_parser("check", help="check the published catalog without the key")
    check.add_argument("--at", help="check time, RFC 3339 UTC with seconds (default now)")
    check.add_argument("--a2a-card", help="the card the released A2A server serves")
    check.add_argument("--emit-cases", help="write reader inputs to this directory")
    check.add_argument("--live", action="store_true", help="read every pointed-at release from its source")
    check.set_defaults(run=cmd_check)
    judge = sub.add_parser("judge", help="run both readers over emitted cases")
    judge.add_argument("directory")
    judge.add_argument("--verify", required=True, help="the agent-evidence-verify command")
    judge.add_argument("--vectors", required=True, help="the vectors reference reader command")
    judge.set_defaults(run=cmd_judge)
    args = parser.parse_args(argv)
    try:
        return args.run(args)
    except Failure as failure:
        print(f"ai-catalog: {failure}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
