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
  rotate ai-catalog.py rotate --to <new public_key_sha256> < pinned-private-key.pem
         Writes catalog/rotation.json: the pinned key hands over to the new key, so `sign` accepts
         the new key and `check --live` accepts a pin that differs from the key the site serves.
  check  ai-catalog.py check [--at RFC3339] [--a2a-card FILE] [--emit-cases DIR]
         Without the key: the published catalog is the source plus digests and manifests (nothing
         edited by hand), did.json holds the pinned key, every signature verifies with this
         script's own JWS code, and each signature is current at --at (default now) with at least
         30 days left. With
         --a2a-card, the A2A entry's data must equal the card the released server serves. With
         --emit-cases, writes the inputs the two independent readers judge (see `judge`). With
         --live, the pinned key is the key the site serves at /.well-known/did.json (or that key
         handed over to it in catalog/rotation.json), and every release the entries point at is
         read from its source: each commit is on its repository's default branch, each tag names
         its commit, and PyPI serves exactly the files the entry signs, none yanked.
  judge  ai-catalog.py judge DIR --verify CMD --vectors CMD
         Runs agent-evidence-verify (claim catalog_trust_manifest/v1) and the agent-evidence-vectors
         reference reader over every emitted case and requires `supported` / `accept` for each
         entry under both constructions and for the snapshot, and for each refusal case (edited
         data, a changed signature bit, another key, signatures swapped between entries, the
         expiry instant, one second before issue) the decision, reason and exit status each
         reader must give, so neither a reader that passes everything nor one that only
         recomputes digests passes this step.
"""

from __future__ import annotations

import argparse
import base64
import copy
import datetime as dt
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.parse
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
ROTATION = ROOT / "catalog" / "rotation.json"

DID = "did:web:probityai.github.io"
KID = DID + "#catalog-es256"
# did:web resolution: the document the domain serves is the key authority a consumer reads.
SERVED_DID = "https://" + DID.removeprefix("did:web:") + "/.well-known/did.json"
PROFILE = "did-web-v1"
AIC, ARD, SNAPSHOT = "ai-catalog-2026-11", "ard-draft-bu-00", "ai-catalog-snapshot"
ROTATE = "ai-catalog-key-rotation"
TYP = {AIC: "ai-catalog-trust-manifest+jws", SNAPSHOT: "ai-catalog+jws", ROTATE: "ai-catalog-key-rotation+jws"}
RELEASE_TYPE = "application/vnd.probityai.release+json"
MCP_TYPE = "application/mcp-registry-server+json"
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

    def constant(name: str) -> Any:
        raise Failure(f"{name} is not a JSON value")

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise Failure("the bytes are not UTF-8") from exc
    if text.startswith("﻿"):
        raise Failure("a byte order mark is not JSON")
    try:
        return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)
    except json.JSONDecodeError as exc:
        raise Failure(f"not JSON: {exc}") from exc


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


def instant(text: Any) -> dt.datetime:
    """An RFC 3339 UTC time written exactly as `stamp` writes it. strptime alone also reads
    2026-11-1T1:2:3Z, which other readers refuse, so the text must round-trip."""
    try:
        moment = dt.datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.UTC)
    except (TypeError, ValueError) as exc:
        raise Failure(f"{text!r} is not an RFC 3339 UTC time with seconds") from exc
    if stamp(moment) != text:
        raise Failure(f"{text!r} is not written as YYYY-MM-DDTHH:MM:SSZ")
    return moment


# ----------------------------------------------------------------------------- commands


def entry_errors(catalog: dict[str, Any]) -> list[str]:
    """What the signed fields of each entry say about one another, read without the network: the
    digest is the digest of the published data, the release a pointer names is the one its version,
    tag, provenance and install line name, and an install line pins what the entry signs."""
    errors: list[str] = []
    seen: set[str] = set()
    for entry in catalog["entries"]:
        name, kind, data = entry["identifier"], entry["type"], entry["data"]
        if name in seen:
            errors.append(f"{name}: the identifier is listed twice")
        seen.add(name)
        if entry["digest"] != digest(data):
            errors.append(f"{name}: digest is not the digest of the published data")
        source = entry["trustManifests"][0]["provenance"][0]["sourceId"]
        version = entry.get("version")
        if kind == RELEASE_TYPE:
            errors += release_errors(name, data, source, version)
        elif kind == MCP_TYPE:
            if data.get("repository", {}).get("url") != source:
                errors.append(f"{name}: server.json repository is not the provenance source {source}")
            if data.get("version") != version:
                errors.append(f"{name}: entry version {version} is not the server.json version {data.get('version')}")
            for package in data.get("packages") or [None]:
                if not isinstance(package, dict) or package.get("registryType") != "pypi":
                    errors.append(f"{name}: every package must be a PyPI package, the one registry the live check reads")
                elif package.get("version") != version:
                    errors.append(f"{name}: package {package.get('identifier')} {package.get('version')} is not {version}")
        elif kind == A2A_TYPE:
            if data.get("version") != version:
                errors.append(f"{name}: entry version {version} is not the card version {data.get('version')}")
        else:
            errors.append(f"{name}: no check for type {kind}")
    return errors


def release_errors(name: str, data: dict[str, Any], source: str, version: str | None) -> list[str]:
    errors = []
    if data.get("repository") != source:
        errors.append(f"{name}: repository {data.get('repository')} is not the provenance source {source}")
    repo, commit, tag = source.removeprefix("https://github.com/"), data.get("commit"), data.get("tag")
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        errors.append(f"{name}: commit is not a full lowercase SHA-1")
    if (tag is None) != (version is None) or (tag is not None and tag != f"v{version}"):
        errors.append(f"{name}: tag {tag} and version {version} do not name one release")
    packages = data.get("packages", [])
    pins = [f"uses: {repo}@{commit}" + (f" # {tag}" if tag else "")]
    for package in packages:
        files = package.get("files") or []
        names = [item.get("filename") for item in files]
        if package.get("registry") != "pypi" or package.get("version") != version:
            errors.append(f"{name}: package {package.get('name')} is not PyPI {version}")
        if not files or len(set(names)) != len(names):
            errors.append(f"{name}: package {package.get('name')} lists no files, or one file twice")
        if any(not re.fullmatch(r"[0-9a-f]{64}", str(item.get("sha256"))) for item in files):
            errors.append(f"{name}: package {package.get('name')} has a file digest that is not SHA-256 hex")
        pins.append(f"pip install {package.get('name')}=={version}")
    # A tagged or packaged release is installed by the line the entry carries, so that line must pin
    # the signed commit or version; an install line that floats (@main, no ==) is not this release.
    if (tag is not None or packages) and data.get("use") not in pins:
        errors.append(f"{name}: use {data.get('use')!r} does not pin the release; expected one of {pins}")
    return errors


def rotation_hands_over(rotation: Any, old: dict[str, Any], new: dict[str, Any]) -> bool:
    """catalog/rotation.json names the old key in full, the new key by its pin, and is signed by the old key."""
    if rotation is None:
        return False
    if not isinstance(rotation, dict) or set(rotation) != {"from", "to", "jws"}:
        raise Failure("catalog/rotation.json holds other members than from, to and jws")
    statement = {"from": rotation["from"], "to": rotation["to"]}
    if rotation["from"] != old["publicKeyJwk"] or rotation["to"] != new["public_key_sha256"]:
        return False
    verify_one(public_of(rotation["from"]), ROTATE, statement, rotation["jws"], "catalog/rotation.json")
    return True


def cmd_sign(args: argparse.Namespace) -> int:
    key = serialization.load_pem_private_key(sys.stdin.buffer.read(), password=None)
    if not isinstance(key, ec.EllipticCurvePrivateKey) or key.curve.name != "secp256r1":
        raise Failure("the private key on standard input is not a P-256 key")
    jwk = jwk_of(key.public_key())
    if PIN.exists():
        pinned = strict_loads(PIN.read_bytes())
        rotation = strict_loads(ROTATION.read_bytes()) if ROTATION.exists() else None
        if pinned["publicKeyJwk"] != jwk and not rotation_hands_over(rotation, pinned, pin_of(jwk)):
            raise Failure(
                f"this key (public_key_sha256 {pin_of(jwk)['public_key_sha256']}) is not the pinned catalog key; "
                "hand over first: the pinned key | ai-catalog.py rotate --to <that sha256>"
            )
    now = dt.datetime.now(dt.UTC)
    catalog = signed(strict_loads(SOURCE.read_bytes()), key, stamp(now), stamp(now + dt.timedelta(days=args.days)))
    errors = entry_errors(catalog)
    if errors:
        raise Failure("catalog/source.json: " + "; ".join(errors))
    CATALOG.parent.mkdir(exist_ok=True)
    CATALOG.write_bytes(dump(catalog))
    DID_DOC.write_bytes(dump(did_document(jwk)))
    PIN.write_bytes(dump(pin_of(jwk)))
    print(f"signed {len(catalog['entries'])} entries under {AIC} and {ARD}, and the catalog under {SNAPSHOT}")
    return 0


def cmd_rotate(args: argparse.Namespace) -> int:
    """Sign, with the pinned key on standard input, the hand-over to the key whose pin is --to."""
    key = serialization.load_pem_private_key(sys.stdin.buffer.read(), password=None)
    if not isinstance(key, ec.EllipticCurvePrivateKey) or key.curve.name != "secp256r1":
        raise Failure("the private key on standard input is not a P-256 key")
    pinned = strict_loads(PIN.read_bytes())
    if pinned["publicKeyJwk"] != jwk_of(key.public_key()):
        raise Failure("only the pinned key can hand over; this key is not it")
    if not re.fullmatch(r"[0-9a-f]{64}", args.to):
        raise Failure("--to is the new key's public_key_sha256, 64 lowercase hex digits")
    statement = {"from": pinned["publicKeyJwk"], "to": args.to}
    ROTATION.write_bytes(dump({**statement, "jws": sign_one(key, ROTATE, statement)}))
    print(f"wrote {ROTATION.relative_to(ROOT)}: the pinned key hands over to {args.to}; now sign with the new key")
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
    if ROTATION.exists():
        rotation = strict_loads(ROTATION.read_bytes())
        if not isinstance(rotation, dict) or not rotation_hands_over(rotation, pin_of(rotation.get("from", {})), pin):
            raise Failure("catalog/rotation.json does not hand over to the pinned key")
    public = public_of(jwk)
    window = catalog.get("signature", {})
    issued, expires = window.get("issuedAt"), window.get("expiresAt")
    if not isinstance(issued, str) or not isinstance(expires, str):
        raise Failure("the catalog signature carries no issuedAt and expiresAt")
    if not instant(issued) < instant(expires):
        raise Failure(f"the catalog expires ({expires}) no later than it is issued ({issued})")
    stripped = copy.deepcopy(catalog)
    stripped["signature"].pop("jws", None)
    for entry in stripped.get("entries", []):
        entry["trustManifests"][0]["signature"].pop("jws", None)
        entry["trustManifest"].pop("signature", None)
    # Compare bytes, not Python values: Python calls false == 0 and 1 == 1.0, so a published 0 where the
    # source holds false compared equal while its digest no longer matched its data.
    if canonical(stripped) != canonical(unsigned(source, issued, expires)):
        raise Failure(".well-known/ai-catalog.json is not catalog/source.json signed; re-run `sign`")
    errors = entry_errors(catalog)
    if errors:
        raise Failure("; ".join(errors))
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


def flip(jws: str) -> str:
    """The same JWS with one bit of r changed: the header and payload still match, the signature does not."""
    protected, _, signature = jws.split(".")
    raw = bytearray(b64url_decode(signature))
    raw[10] ^= 1
    return f"{protected}..{b64url(bytes(raw))}"


def resigned(catalog: dict[str, Any], key: ec.EllipticCurvePrivateKey) -> dict[str, Any]:
    """The same catalog with every signature made by another key."""
    out = copy.deepcopy(catalog)
    for index, entry in enumerate(out["entries"]):
        entry["trustManifests"][0]["signature"]["jws"] = sign_one(key, AIC, payload(AIC, out, index))
        entry["trustManifest"]["signature"] = sign_one(key, ARD, payload(ARD, out, index))
    out["signature"]["jws"] = sign_one(key, SNAPSHOT, payload(SNAPSHOT, out, None))
    return out


def with_signature(catalog: dict[str, Any], construction: str, change) -> dict[str, Any]:
    """A copy whose signature for entry 0 (or the snapshot) is change(catalog, current jws)."""
    out = copy.deepcopy(catalog)
    if construction == AIC:
        slot = out["entries"][0]["trustManifests"][0]["signature"]
        slot["jws"] = change(catalog, slot["jws"])
    elif construction == ARD:
        out["entries"][0]["trustManifest"]["signature"] = change(catalog, out["entries"][0]["trustManifest"]["signature"])
    else:
        out["signature"]["jws"] = change(catalog, out["signature"]["jws"])
    return out


def entry_one_signature(construction: str):
    def change(catalog: dict[str, Any], _jws: str) -> str:
        second = catalog["entries"][1]
        return second["trustManifests"][0]["signature"]["jws"] if construction == AIC else second["trustManifest"]["signature"]

    return change


def emit(directory: Path, catalog: dict[str, Any], document: dict[str, Any], pin: dict[str, Any], at: str) -> int:
    """Case inputs for both readers: each entry under both constructions and the snapshot, which both
    must support, and per construction six refusals, each with the reason both readers must give. A
    data edit alone is caught by recomputing digests, so a reader that never verified a signature
    passed the earlier three-case set; the signature, key, swap and time cases need a real verifier."""
    raw = CATALOG.read_bytes()
    documents = canonical({DID: document})
    other = ec.generate_private_key(ec.SECP256R1())
    other_documents = canonical({DID: did_document(jwk_of(other.public_key()))})
    tampered = copy.deepcopy(catalog)
    first = tampered["entries"][0]
    first["data"] = {**first["data"], "description": first["data"].get("description", "") + " (edited)"}
    issued, expires = catalog["signature"]["issuedAt"], catalog["signature"]["expiresAt"]
    before = stamp(instant(issued) - dt.timedelta(seconds=1))
    jobs: list[tuple[str, bytes, bytes, str, int, str, tuple[str, str], tuple[str, str]]] = []
    for index in range(len(catalog["entries"])):
        for construction in (AIC, ARD):
            decision, reason, accept = PASS[construction]
            jobs.append((f"{index:02d}-{construction}", raw, documents, construction, index, at, (decision, reason), (accept, reason)))
    decision, reason, accept = PASS[SNAPSHOT]
    jobs.append(("snapshot", raw, documents, SNAPSHOT, 0, at, (decision, reason), (accept, reason)))

    def refuse(reason: str) -> tuple[tuple[str, str], tuple[str, str]]:
        return ("contradicted", reason), ("reject", reason)

    for construction in (AIC, ARD, SNAPSHOT):
        edited = "signature_invalid" if construction == SNAPSHOT else "artifact_digest_mismatch"
        cases = [
            ("tampered", dump(tampered), documents, at, refuse(edited)),
            ("signature-bit", dump(with_signature(catalog, construction, lambda _c, jws: flip(jws))), documents, at,
             refuse("signature_invalid")),
            ("other-key", dump(resigned(catalog, other)), documents, at, refuse("signature_invalid")),
            # The DID documents name the other key. agent-evidence-verify refuses it against the pin; the
            # vectors reader takes the DID documents as the resolver's answer and has no pin input, so it
            # accepts. The pin is held by `check` (did.json is the pinned key's document) and by verify.
            ("other-did", dump(resigned(catalog, other)), other_documents, at,
             (("contradicted", "key_not_pinned"), (PASS[construction][2], PASS[construction][1]))),
            ("expired", raw, documents, expires, refuse("manifest_expired")),
            ("not-yet-issued", raw, documents, before, refuse("issued_in_future")),
        ]
        if construction != SNAPSHOT:
            cases.append(("swapped", dump(with_signature(catalog, construction, entry_one_signature(construction))),
                          documents, at, refuse("signature_invalid")))
        for label, body, docs, moment, (mine, theirs) in cases:
            jobs.append((f"{label}-{construction}", body, docs, construction, 0, moment, mine, theirs))

    assessments, plan = {}, []
    for name, body, docs, construction, index, moment, mine, theirs in jobs:
        case = directory / "cases" / name
        case.mkdir(parents=True, exist_ok=True)
        (case / "catalog.json").write_bytes(body)
        (case / "did-documents.json").write_bytes(docs)
        (case / "context.json").write_bytes(
            dump(
                {
                    "at": moment,
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
                        for file, data in (("catalog.json", body), ("did-documents.json", docs))
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
            "at": moment,
            "entry": index,
            "manifest": 0,
            "key_authority": {
                "kind": "pin",
                "keys": [{"kid": pin["kid"], "public_key_sha256": pin["public_key_sha256"]}],
            },
        }
        plan.append({"name": name, "construction": construction, "verify": list(mine), "vectors": list(theirs)})
    (directory / "policy.json").write_bytes(dump({"schema_version": "probity-policy/v1", "assessments": assessments}))
    (directory / "plan.json").write_bytes(dump(plan))
    return len(plan)


def fetch(url: str) -> bytes | None:
    """The body at url, or None for 404. Three tries on a 5xx or a dropped connection (Pages answers a
    transient 503 now and then); any other answer is a failure, never an empty result."""
    headers = {"User-Agent": "probityai-ai-catalog-check", "Accept": "application/json"}
    token = os.environ.get("GH_TOKEN")
    if token and url.startswith("https://api.github.com/"):
        headers["Authorization"] = f"Bearer {token}"
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            if exc.code < 500 or attempt == 2:
                raise Failure(f"could not read {url}: HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt == 2:
                raise Failure(f"could not read {url}: {exc}") from exc
        time.sleep(5 * (attempt + 1))
    raise Failure(f"could not read {url}")


def fetch_json(url: str) -> Any:
    body = fetch(url)
    if body is None:
        raise Failure(f"could not read {url}: HTTP 404")
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise Failure(f"could not read {url}: {exc}") from exc


def pypi_files(name: str, version: str) -> dict[str, str]:
    """Every file PyPI serves for the release, refused when any is yanked or there are none."""
    release = fetch_json(f"https://pypi.org/pypi/{urllib.parse.quote(name)}/{urllib.parse.quote(version)}/json")
    files = {}
    for item in release["urls"]:
        if item.get("yanked"):
            raise Failure(f"PyPI {name} {version}: {item['filename']} is yanked")
        files[item["filename"]] = item["digests"]["sha256"]
    if not files:
        raise Failure(f"PyPI has no files for {name} {version}")
    return files


def on_default_branch(repo: str, commit: str) -> None:
    """The commits endpoint answers for any commit in the fork network, including a closed pull
    request's head that never merged, so existence is not enough: the default branch must contain it."""
    branch = fetch_json(f"https://api.github.com/repos/{repo}")["default_branch"]
    compare = fetch_json(f"https://api.github.com/repos/{repo}/compare/{commit}...{urllib.parse.quote(branch)}")
    if compare.get("status") not in ("ahead", "identical"):
        raise Failure(f"{repo}: commit {commit} is not on {branch} (compare says {compare.get('status')})")


def check_key_continuity(pin: dict[str, Any]) -> str:
    """The pinned key is the key the site already serves, or the served key handed over to it in
    catalog/rotation.json. Without this, one change that replaced the key, the pin and did.json
    together passed every other check. Before the first publication nothing is served."""
    body = fetch(SERVED_DID)
    if body is None:
        return f"{SERVED_DID} is not served yet: this is the first publication of the key"
    served = strict_loads(body)
    methods = served.get("verificationMethod") if isinstance(served, dict) else None
    if not isinstance(methods, list) or len(methods) != 1 or served != did_document(methods[0].get("publicKeyJwk")):
        raise Failure(f"{SERVED_DID} is not a did:web document of one catalog key")
    old = pin_of(methods[0]["publicKeyJwk"])
    if old["public_key_sha256"] == pin["public_key_sha256"]:
        return "the pinned key is the key the site serves"
    rotation = strict_loads(ROTATION.read_bytes()) if ROTATION.exists() else None
    if rotation is None or not rotation_hands_over(rotation, old, pin):
        raise Failure(
            f"the pinned key {pin['public_key_sha256']} is not the served key {old['public_key_sha256']}, "
            "and no catalog/rotation.json signed by the served key hands over to it"
        )
    return f"the served key {old['public_key_sha256']} hands over to the pinned key"


def check_live(catalog: dict[str, Any]) -> int:
    """Each pointer the entries sign resolves to what they say, read from the registry or forge."""
    checked = 0
    for entry in catalog["entries"]:
        data, name = entry["data"], entry["identifier"]
        if entry["type"] == RELEASE_TYPE:
            repo = data["repository"].removeprefix("https://github.com/")
            commit = fetch_json(f"https://api.github.com/repos/{repo}/commits/{data['commit']}")
            if commit.get("sha") != data["commit"]:
                raise Failure(f"{name}: commit {data['commit']} is not in {repo}")
            on_default_branch(repo, data["commit"])
            if "tag" in data:
                ref = fetch_json(f"https://api.github.com/repos/{repo}/git/ref/tags/{urllib.parse.quote(data['tag'])}")
                ref = ref["object"]
                if ref["type"] == "tag":
                    ref = fetch_json(ref["url"])["object"]
                if ref["sha"] != data["commit"]:
                    raise Failure(f"{name}: tag {data['tag']} names {ref['sha']}, not {data['commit']}")
            for package in data.get("packages", []):
                served = pypi_files(package["name"], package["version"])
                listed = {item["filename"]: item["sha256"] for item in package["files"]}
                if served != listed:
                    raise Failure(
                        f"{name}: PyPI {package['name']} {package['version']} serves {sorted(served.items())}, "
                        f"the entry signs {sorted(listed.items())}"
                    )
            checked += 1
        elif entry["type"] == MCP_TYPE:
            for package in data["packages"]:
                pypi_files(package["identifier"], package["version"])
            checked += 1
        elif entry["type"] == A2A_TYPE:
            pypi_files("agent-evidence-verify", entry["version"])
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
        if len(cards) != 1 or canonical(cards[0]["data"]) != canonical(served):
            raise Failure("the A2A entry's data is not the card the released server serves")
        if cards[0].get("version") != served.get("version"):
            raise Failure("the A2A entry's version is not the served card's version")
    if args.live:
        print(f"ai-catalog: {check_key_continuity(pin)}")
        print(f"ai-catalog: {check_live(catalog)} of {len(catalog['entries'])} entries resolve at their source")
    count = len(catalog["entries"])
    print(f"ai-catalog: {count} entries, {2 * count + 1} signatures verify with the pinned key at {stamp(at)}")
    if args.emit_cases:
        print(
            f"ai-catalog: wrote {emit(Path(args.emit_cases), catalog, document, pin, stamp(at))} cases "
            f"to {args.emit_cases}"
        )
    return 0


def run_reader(command: list[str], exits: dict[str, int]) -> dict[str, Any]:
    """One reader's answer. Its exit status must be the one it gives for that decision, so a reader
    that printed a verdict and then failed is not read as having given it."""
    done = subprocess.run(command, capture_output=True, text=True, check=False)
    try:
        answer = json.loads(done.stdout)
    except json.JSONDecodeError as exc:
        raise Failure(
            f"{shlex.join(command)} exited {done.returncode} with no JSON: {done.stdout[-400:]}{done.stderr[-400:]}"
        ) from exc
    if not isinstance(answer, dict) or not isinstance(answer.get("decision"), str):
        raise Failure(f"{shlex.join(command)} printed no decision")
    answer["exit_as_decided"] = exits.get(answer["decision"]) == done.returncode
    answer["exit"] = done.returncode
    return answer


# agent-evidence-verify reports every decision in its JSON and exits 0; the vectors reader exits 1 on reject.
VERIFY_EXITS = {"supported": 0, "contradicted": 0}
VECTORS_EXITS = {"accept": 0, "reject": 1}


def cmd_judge(args: argparse.Namespace) -> int:
    directory = Path(args.directory)
    plan = strict_loads((directory / "plan.json").read_bytes())
    verify, vectors = shlex.split(args.verify), shlex.split(args.vectors)
    wrong = []
    for job in plan:
        case = directory / "cases" / job["name"]
        mine = run_reader(
            [*verify, str(case / "case.json"), "--policy", str(directory / "policy.json"), "--json"], VERIFY_EXITS
        )
        theirs = run_reader([*vectors, "catalog-trust-manifest/v1", str(case), "--json"], VECTORS_EXITS)
        ok = (
            [mine["decision"], mine.get("reason")] == job["verify"]
            and [theirs["decision"], theirs.get("reason")] == job["vectors"]
            and mine["exit_as_decided"]
            and theirs["exit_as_decided"]
        )
        line = (
            f"{job['name']}: agent-evidence-verify {mine['decision']} {mine.get('reason')} exit {mine['exit']}; "
            f"vectors reader {theirs['decision']} {theirs.get('reason')} exit {theirs['exit']}"
        )
        if not ok:
            line += f" (expected {' '.join(job['verify'])}; {' '.join(job['vectors'])})"
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
    rotate = sub.add_parser("rotate", help="hand over from the pinned key (PEM on standard input) to a new key")
    rotate.add_argument("--to", required=True, help="the new key's public_key_sha256")
    rotate.set_defaults(run=cmd_rotate)
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
    except (KeyError, IndexError, TypeError, AttributeError) as error:
        # A missing or mistyped member in a file this script reads: refused, with the member named.
        print(f"ai-catalog: malformed input: {type(error).__name__}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
