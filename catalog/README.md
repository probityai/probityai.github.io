# Signed AI Catalog

`https://probityai.github.io/.well-known/ai-catalog.json` lists the organization's runnable resources in the AI Catalog format: the agent-evidence-mcp server, the agent-evidence-verify A2A server, the agent-evidence-vectors GitHub Action and corpus, evidence-starter and the conformance matrix. Each entry carries its artifact inline (`data`), its `digest` (SHA-256 of the RFC 8785 bytes of `data`) and two publisher trust manifests over the same subject:

| Member | Construction | Signed bytes |
| --- | --- | --- |
| `trustManifests[0]` | `ai-catalog-2026-11` | RFC 8785 of the manifest without its `signature.jws` |
| `trustManifest` | `ard-draft-bu-00` (draft-bu-dawn-ard-discovery-00 section 3.5) | RFC 8785 of the manifest without `signature` |

The catalog root carries a third signature under `ai-catalog-snapshot`. Every signature is a detached compact JWS, ES256, signed by `did:web:probityai.github.io` with the one key in [`/.well-known/did.json`](../.well-known/did.json); its SHA-256 pin is in [`signing-key.json`](signing-key.json).

Check it yourself with the two readers CI runs:

```sh
uv run --script scripts/ai-catalog.py check --live --emit-cases /tmp/catalog-cases
uv run --script scripts/ai-catalog.py judge /tmp/catalog-cases --verify agent-evidence-verify \
  --vectors "python3 -m agent_evidence_vectors.catalogtrust"
```

`check` proves the published file is `source.json` signed, compared as RFC 8785 bytes (nothing edited by hand), that each entry's version, tag, provenance and install line name one release, and that every signature verifies and is current. With `--live` it also proves the pinned key is the key the site serves at `/.well-known/did.json` (or that key handed over to it in `rotation.json`), each commit is on its repository's default branch, each tag names its commit, and PyPI serves exactly the files an entry signs, none yanked. `judge` runs agent-evidence-verify (claim `catalog_trust_manifest/v1`) and the agent-evidence-vectors reference reader over every entry under both constructions and the snapshot, and over 20 refusal cases (edited data, a changed signature bit, another key, signatures swapped between entries, the expiry instant, one second before issue), and requires the decision, reason and exit status each reader gives. The vectors reader takes the DID documents it is given as the resolver's answer and has no pin input, so the case signed by another key whose DID document names that key is refused by agent-evidence-verify (`key_not_pinned`) and accepted by the vectors reader; `check` holds the pin by requiring `did.json` to be the pinned key's document. `tests/ai_catalog_cases.py` holds each input an earlier version of `check` or `judge` passed.

A verdict says which key signed which bytes and that the subject binds the entry and its data. It does not say the software is safe.

## Changing an entry

Edit `source.json`, then sign with the key from the keyring:

```sh
secret-tool lookup service probityai-ai-catalog account es256-private-key-pem \
  | uv run --script scripts/ai-catalog.py sign --days 365
```

To change the key, hand over from the pinned key first, then sign with the new one (the new key's `public_key_sha256` is printed when `sign` refuses it):

```sh
secret-tool lookup service probityai-ai-catalog account es256-private-key-pem \
  | uv run --script scripts/ai-catalog.py rotate --to <new public_key_sha256>
```

The A2A entry's `data` is the card `probity-a2a` serves; `scripts/ai-catalog-a2a-card.py` prints it from the released package, and CI fails when the two differ. The signatures expire after a year, and the weekly CI run fails before a stale catalog is served.
