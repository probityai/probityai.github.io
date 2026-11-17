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

`check` proves the published file is `source.json` signed (nothing edited by hand), every signature verifies and is current, and each release an entry points at resolves at its source. `judge` runs agent-evidence-verify (claim `catalog_trust_manifest/v1`) and the agent-evidence-vectors reference reader over every entry under both constructions and the snapshot, and over three tampered copies both must refuse.

A verdict says which key signed which bytes and that the subject binds the entry and its data. It does not say the software is safe.

## Changing an entry

Edit `source.json`, then sign with the key from the keyring:

```sh
secret-tool lookup service probityai-ai-catalog account es256-private-key-pem \
  | uv run --script scripts/ai-catalog.py sign --days 365
```

The A2A entry's `data` is the card `probity-a2a` serves; `scripts/ai-catalog-a2a-card.py` prints it from the released package, and CI fails when the two differ. The signatures expire after a year, and the weekly CI run fails before a stale catalog is served.
