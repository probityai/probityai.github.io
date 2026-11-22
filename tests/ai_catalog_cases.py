# /// script
# requires-python = ">=3.11"
# dependencies = ["cryptography==50.0.2"]
# ///
"""Constructed inputs that scripts/ai-catalog.py must refuse, each one an input that an earlier
version passed. Run: uv run --script tests/ai_catalog_cases.py

The name does not match test*.py on purpose: `unittest discover -s tests` runs under a bare python3
without cryptography, and this file needs it, so CI runs it as its own uv script."""

from __future__ import annotations

import copy
import datetime as dt
import importlib.util
import io
import json
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric import ec

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ai_catalog", ROOT / "scripts" / "ai-catalog.py")
aic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(aic)

ISSUED, EXPIRES, AT = "2026-11-17T00:00:00Z", "2027-11-17T00:00:00Z", "2026-11-18T00:00:00Z"
PATHS = ("SOURCE", "PIN", "CATALOG", "DID_DOC", "ROTATION")


def find(catalog, suffix):
    return next(e for e in catalog["entries"] if e["identifier"].endswith(suffix))


class Tree(unittest.TestCase):
    """A copy of the catalog files signed with a key made for the test, and the module pointed at it."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.saved = {name: getattr(aic, name) for name in (*PATHS, "fetch")}
        (self.tmp / "catalog").mkdir()
        (self.tmp / ".well-known").mkdir()
        shutil.copy(ROOT / "catalog" / "source.json", self.tmp / "catalog" / "source.json")
        aic.SOURCE = self.tmp / "catalog" / "source.json"
        aic.PIN = self.tmp / "catalog" / "signing-key.json"
        aic.ROTATION = self.tmp / "catalog" / "rotation.json"
        aic.CATALOG = self.tmp / ".well-known" / "ai-catalog.json"
        aic.DID_DOC = self.tmp / ".well-known" / "did.json"
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.source = json.loads(aic.SOURCE.read_text())
        self.publish(aic.signed(self.source, self.key, ISSUED, EXPIRES))

    def tearDown(self):
        for name, value in self.saved.items():
            setattr(aic, name, value)
        shutil.rmtree(self.tmp)

    def publish(self, catalog, key=None):
        jwk = aic.jwk_of((key or self.key).public_key())
        aic.CATALOG.write_bytes(aic.dump(catalog))
        aic.DID_DOC.write_bytes(aic.dump(aic.did_document(jwk)))
        aic.PIN.write_bytes(aic.dump(aic.pin_of(jwk)))

    def resign(self, catalog):
        """Every signature made again over the catalog as given: what a key holder can publish."""
        return aic.resigned(catalog, self.key)

    def from_source(self, edit):
        """The catalog `sign` would write for an edited source, built without sign's own refusals."""
        source = copy.deepcopy(self.source)
        edit(source)
        aic.SOURCE.write_text(json.dumps(source))
        catalog = aic.signed(source, self.key, ISSUED, EXPIRES)
        self.publish(catalog)
        return catalog

    def refused(self, needle, call=None):
        with self.assertRaises(aic.Failure) as caught:
            (call or (lambda: aic.check_published(aic.instant(AT))))()
        self.assertIn(needle, str(caught.exception))


class Published(Tree):
    def test_the_genuine_catalog_passes(self):
        catalog, _, _ = aic.check_published(aic.instant(AT))
        self.assertEqual(len(catalog["entries"]), len(self.source["entries"]))

    def test_the_repository_catalog_passes_offline(self):
        for name, value in self.saved.items():
            setattr(aic, name, value)
        published = json.loads(aic.CATALOG.read_text())["signature"]
        at = aic.instant(published["issuedAt"]) + dt.timedelta(days=1)
        aic.check_published(at)

    def test_false_published_as_zero(self):
        catalog = json.loads(aic.CATALOG.read_text())
        card = find(catalog, ":a2a:agent-evidence-verify")["data"]["capabilities"]
        flag = next(k for k, v in card.items() if v is False)
        card[flag] = 0
        self.publish(self.resign(catalog))
        self.refused("is not catalog/source.json signed")

    def test_digest_that_is_not_the_data_digest(self):
        catalog = self.from_source(lambda s: None)
        entry = catalog["entries"][0]
        entry["digest"] = aic.digest({"other": True})
        self.assertIn(
            "digest is not the digest of the published data", " ".join(aic.entry_errors(self.resign(catalog)))
        )

    def test_loose_timestamps(self):
        self.publish(aic.resigned(aic.unsigned(self.source, "2026-11-1T1:2:3Z", "2027-11-1T1:2:3Z"), self.key))
        self.refused("is not written as YYYY-MM-DDTHH:MM:SSZ")

    def test_expiry_not_after_issue(self):
        self.publish(aic.resigned(aic.unsigned(self.source, EXPIRES, ISSUED), self.key))
        self.refused("no later than it is issued")

    def test_check_time_must_be_rfc3339(self):
        self.refused("is not written", lambda: aic.instant("2026-11-18T0:00:00Z"))

    def test_json_two_ways(self):
        for raw, needle in (
            (b'{"a": 1, "a": 2}', "duplicate member name"),
            (b'{"a": NaN}', "NaN is not a JSON value"),
            (b'{"a": Infinity}', "Infinity is not a JSON value"),
            (b'\xef\xbb\xbf{"a": 1}', "byte order mark"),
            (b'{"a": "\xff"}', "not UTF-8"),
            (b"{", "not JSON"),
        ):
            with self.subTest(raw=raw):
                self.refused(needle, lambda raw=raw: aic.strict_loads(raw))


class Entries(Tree):
    """Each edit is one `sign` now refuses; the check refuses it too when a catalog skips `sign`."""

    def assert_refused(self, edit, needle):
        self.from_source(edit)
        self.refused(needle)

    def test_corpus_lists_no_files(self):
        self.assert_refused(
            lambda s: find(s, ":corpus:agent-evidence-vectors")["data"]["packages"][0].update(files=[]),
            "lists no files",
        )

    def test_mcp_version_is_not_the_server_version(self):
        self.assert_refused(lambda s: find(s, ":mcp:agent-evidence-mcp").update(version="9.9.9"), "is not the server.json")

    def test_action_use_floats(self):
        self.assert_refused(
            lambda s: find(s, ":action:agent-evidence-vectors")["data"].update(
                use="uses: probityai/agent-evidence-vectors@main"
            ),
            "does not pin the release",
        )

    def test_unpinned_pip_install(self):
        self.assert_refused(
            lambda s: find(s, ":corpus:agent-evidence-vectors")["data"].update(use="pip install agent-evidence-vectors"),
            "does not pin the release",
        )

    def test_provenance_names_another_repository(self):
        self.assert_refused(
            lambda s: find(s, ":matrix:agent-evidence-matrix").update(source="https://github.com/probityai/evidence-starter"),
            "is not the provenance source",
        )

    def test_tag_and_version_disagree(self):
        self.assert_refused(lambda s: find(s, ":action:agent-evidence-vectors")["data"].update(tag="v0.36.0"), "do not name one release")

    def test_short_commit(self):
        self.assert_refused(lambda s: find(s, ":matrix:agent-evidence-matrix")["data"].update(commit="4167aaa"), "full lowercase SHA-1")

    def test_identifier_twice(self):
        self.assert_refused(lambda s: s["entries"].append(copy.deepcopy(s["entries"][0])), "listed twice")

    def test_a2a_card_compared_as_bytes(self):
        catalog = json.loads(aic.CATALOG.read_text())
        card = copy.deepcopy(find(catalog, ":a2a:agent-evidence-verify")["data"])
        flag = next(k for k, v in card["capabilities"].items() if v is False)
        card["capabilities"][flag] = 0
        served = self.tmp / "card.json"
        served.write_text(json.dumps(card))
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()) as err:
            code = aic.main(["check", "--at", AT, "--a2a-card", str(served)])
        self.assertEqual(code, 1)
        self.assertIn("not the card the released server serves", err.getvalue())


class Live(Tree):
    """The network answers are fixed by the test; each case is what GitHub or PyPI really answers."""

    def answers(self, extra=None):
        table = {}
        for entry in json.loads(aic.CATALOG.read_text())["entries"]:
            data = entry["data"]
            if entry["type"] == aic.RELEASE_TYPE:
                repo = data["repository"].removeprefix("https://github.com/")
                table[f"https://api.github.com/repos/{repo}/commits/{data['commit']}"] = {"sha": data["commit"]}
                table[f"https://api.github.com/repos/{repo}"] = {"default_branch": "main"}
                table[f"https://api.github.com/repos/{repo}/compare/{data['commit']}...main"] = {"status": "ahead"}
                if "tag" in data:
                    table[f"https://api.github.com/repos/{repo}/git/ref/tags/{data['tag']}"] = {
                        "object": {"type": "commit", "sha": data["commit"]}
                    }
                for package in data.get("packages", []):
                    table[f"https://pypi.org/pypi/{package['name']}/{package['version']}/json"] = {
                        "urls": [
                            {"filename": f["filename"], "digests": {"sha256": f["sha256"]}, "yanked": False}
                            for f in package["files"]
                        ]
                    }
            elif entry["type"] == aic.MCP_TYPE:
                for package in data["packages"]:
                    table[f"https://pypi.org/pypi/{package['identifier']}/{package['version']}/json"] = {
                        "urls": [{"filename": "x.whl", "digests": {"sha256": "0" * 64}, "yanked": False}]
                    }
            else:
                table[f"https://pypi.org/pypi/agent-evidence-verify/{entry['version']}/json"] = {
                    "urls": [{"filename": "y.whl", "digests": {"sha256": "1" * 64}, "yanked": False}]
                }
        table[aic.SERVED_DID] = None
        table.update(extra or {})

        def fetch(url):
            if url not in table:
                raise AssertionError(f"unexpected read {url}")
            value = table[url]
            return value if value is None or isinstance(value, bytes) else json.dumps(value).encode()

        aic.fetch = fetch
        return table

    def live(self):
        pin = json.loads(aic.PIN.read_text())
        catalog = json.loads(aic.CATALOG.read_text())
        return aic.check_key_continuity(pin), aic.check_live(catalog)

    def test_genuine_answers_pass(self):
        self.answers()
        note, checked = self.live()
        self.assertIn("first publication", note)
        self.assertEqual(checked, len(self.source["entries"]))

    def test_pypi_serves_a_file_the_entry_does_not_sign(self):
        table = self.answers()
        corpus = find(json.loads(aic.CATALOG.read_text()), ":corpus:agent-evidence-vectors")["data"]["packages"][0]
        url = f"https://pypi.org/pypi/{corpus['name']}/{corpus['version']}/json"
        table[url]["urls"].append({"filename": "extra-0.37.0-cp312-manylinux.whl", "digests": {"sha256": "2" * 64}})
        self.refused("serves", self.live)

    def test_yanked_release(self):
        table = self.answers()
        corpus = find(json.loads(aic.CATALOG.read_text()), ":corpus:agent-evidence-vectors")["data"]["packages"][0]
        table[f"https://pypi.org/pypi/{corpus['name']}/{corpus['version']}/json"]["urls"][0]["yanked"] = True
        self.refused("is yanked", self.live)

    def test_commit_off_the_default_branch(self):
        table = self.answers()
        matrix = find(json.loads(aic.CATALOG.read_text()), ":matrix:agent-evidence-matrix")["data"]
        repo = matrix["repository"].removeprefix("https://github.com/")
        table[f"https://api.github.com/repos/{repo}/compare/{matrix['commit']}...main"] = {"status": "diverged"}
        self.refused("is not on main", self.live)

    def test_transient_error_is_never_a_result(self):
        self.answers()

        def broken(url):
            raise aic.Failure(f"could not read {url}: HTTP 503")

        aic.fetch = broken
        self.refused("HTTP 503", self.live)

    def served(self, key):
        return aic.dump(aic.did_document(aic.jwk_of(key.public_key())))

    def test_key_swapped_in_one_change(self):
        served = ec.generate_private_key(ec.SECP256R1())
        self.answers({aic.SERVED_DID: self.served(served)})
        self.refused("is not the served key", self.live)

    def test_key_handed_over_by_the_served_key(self):
        old = ec.generate_private_key(ec.SECP256R1())
        self.answers({aic.SERVED_DID: self.served(old)})
        new_pin = json.loads(aic.PIN.read_text())["public_key_sha256"]
        statement = {"from": aic.jwk_of(old.public_key()), "to": new_pin}
        aic.ROTATION.write_bytes(aic.dump({**statement, "jws": aic.sign_one(old, aic.ROTATE, statement)}))
        self.assertIn("hands over", self.live()[0])
        aic.check_published(aic.instant(AT))

    def test_hand_over_signed_by_another_key(self):
        old, forger = ec.generate_private_key(ec.SECP256R1()), ec.generate_private_key(ec.SECP256R1())
        self.answers({aic.SERVED_DID: self.served(old)})
        new_pin = json.loads(aic.PIN.read_text())["public_key_sha256"]
        statement = {"from": aic.jwk_of(old.public_key()), "to": new_pin}
        aic.ROTATION.write_bytes(aic.dump({**statement, "jws": aic.sign_one(forger, aic.ROTATE, statement)}))
        self.refused("signature does not verify", self.live)

    def test_sign_refuses_a_new_key_without_a_hand_over(self):
        other = ec.generate_private_key(ec.SECP256R1())
        from cryptography.hazmat.primitives import serialization

        pem = other.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
        )
        stdin = sys.stdin
        sys.stdin = io.TextIOWrapper(io.BytesIO(pem))
        try:
            with redirect_stderr(io.StringIO()) as err:
                code = aic.main(["sign"])
        finally:
            sys.stdin = stdin
        self.assertEqual(code, 1)
        self.assertIn("hand over first", err.getvalue())


class Judge(Tree):
    """The judge's refusal cases need a reader that verifies signatures, keys and times."""

    def reader(self, body):
        path = self.tmp / f"reader-{len(list(self.tmp.glob('reader-*')))}.py"
        path.write_text(body)
        return f"{sys.executable} -I {path}"

    def judge(self, verify, vectors):
        cases = self.tmp / "cases"
        with redirect_stdout(io.StringIO()):
            aic.emit(cases, *aic.check_published(aic.instant(AT)), AT)
            return aic.main(["judge", str(cases), "--verify", verify, "--vectors", vectors])

    DIGEST_ONLY = '''
import hashlib, json, sys
from pathlib import Path
sys.path.insert(0, {root!r})
import importlib.util
spec = importlib.util.spec_from_file_location("a", {script!r}); a = importlib.util.module_from_spec(spec); spec.loader.exec_module(a)
args = sys.argv[1:]
vectors = args[0] == "catalog-trust-manifest/v1"
case = Path(args[1]) if vectors else Path(args[0]).parent
cat = json.loads((case / "catalog.json").read_text()); ctx = json.loads((case / "context.json").read_text())
snap = ctx["construction"] == a.SNAPSHOT
entries = cat["entries"] if snap else [cat["entries"][ctx["entry"]]]
good = all(a.digest(e["data"]) == e["digest"] for e in entries)
reason = a.PASS[ctx["construction"]][1] if good else ("signature_invalid" if snap else "artifact_digest_mismatch")
decision = ("accept" if good else "reject") if vectors else ("supported" if good else "contradicted")
print(json.dumps({{"decision": decision, "reason": reason}}))
sys.exit(1 if decision == "reject" else 0)
'''

    def test_a_reader_that_only_recomputes_digests_fails(self):
        body = self.DIGEST_ONLY.format(root=str(ROOT), script=str(ROOT / "scripts" / "ai-catalog.py"))
        self.assertEqual(self.judge(self.reader(body), self.reader(body)), 1)

    def test_a_reader_that_passes_everything_fails(self):
        body = (
            "import json, sys\nv = sys.argv[1] == 'catalog-trust-manifest/v1'\n"
            "print(json.dumps({'decision': 'accept' if v else 'supported', 'reason': 'signature_covers_release'}))\n"
        )
        self.assertEqual(self.judge(self.reader(body), self.reader(body)), 1)

    # Answers what plan.json expects for the case, so only the part each test changes can fail it.
    ORACLE = """
import json, sys
from pathlib import Path
args = sys.argv[1:]
vectors = args[0] == "catalog-trust-manifest/v1"
case = Path(args[1]) if vectors else Path(args[0]).parent
job = next(j for j in json.loads((case.parents[1] / "plan.json").read_text()) if j["name"] == case.name)
decision, reason = job["vectors" if vectors else "verify"]
print(json.dumps({"decision": decision, "reason": REASON}))
sys.exit(EXIT)
"""

    def oracle(self, reason="reason", exit_code='1 if decision == "reject" else 0'):
        return self.reader(self.ORACLE.replace("REASON", reason).replace("EXIT", exit_code))

    def test_a_reader_that_gives_every_expected_answer_passes(self):
        self.assertEqual(self.judge(self.oracle(), self.oracle()), 0)

    def test_a_reader_whose_exit_contradicts_its_verdict_fails(self):
        self.assertEqual(self.judge(self.oracle(), self.oracle(exit_code="3")), 1)

    def test_a_reader_with_the_right_decisions_for_the_wrong_reasons_fails(self):
        wrong = self.oracle(reason='"signature_invalid"')
        self.assertEqual(self.judge(wrong, self.oracle()), 1)
        self.assertEqual(self.judge(self.oracle(), wrong), 1)

    def test_every_refusal_case_is_emitted(self):
        cases = self.tmp / "cases"
        with redirect_stdout(io.StringIO()):
            count = aic.emit(cases, *aic.check_published(aic.instant(AT)), AT)
        plan = json.loads((cases / "plan.json").read_text())
        refusals = [job for job in plan if job["vectors"][0] == "reject" or job["verify"][0] == "contradicted"]
        self.assertEqual(count, 2 * len(self.source["entries"]) + 1 + len(refusals))
        labels = {job["name"].rsplit("-", 2)[0] for job in refusals}
        for label in ("tampered", "signature-bit", "other-key", "other-did", "expired", "not-yet-issued", "swapped"):
            self.assertTrue(any(name.startswith(label) for name in labels), label)


if __name__ == "__main__":
    unittest.main(verbosity=2)
