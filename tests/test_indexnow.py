"""Tests for scripts/indexnow.py: 202 is pending, never accepted, and a bad key sends nothing."""

import importlib.util
import json
import pathlib
import unittest

SPEC = importlib.util.spec_from_file_location(
    "indexnow", pathlib.Path(__file__).resolve().parents[1] / "scripts" / "indexnow.py"
)
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)

KEY = "0123456789abcdef0123456789abcdef"


class IndexNowTest(unittest.TestCase):
    def test_verdicts(self):
        self.assertEqual(mod.verdict(200), "ACCEPTED")
        self.assertEqual(mod.verdict(202), "PENDING")
        for status in (0, 400, 403, 422, 429, 500):
            self.assertEqual(mod.verdict(status), "FAILED")

    def test_payload_names_the_key_file_and_the_urls(self):
        sent = []

        def post(url, data, headers):
            sent.append((url, json.loads(data)))
            return 202, b""

        receipts = mod.submit("example.org", KEY, ["https://example.org/a", "https://example.org/b"], post=post)
        self.assertEqual(receipts, [{"status": 202, "verdict": "PENDING", "urls": 2}])
        url, body = sent[0]
        self.assertEqual(url, mod.ENDPOINT)
        self.assertEqual(body["keyLocation"], f"https://example.org/{KEY}.txt")
        self.assertEqual(body["urlList"], ["https://example.org/a", "https://example.org/b"])

    def test_rate_limit_is_retried_then_reported(self):
        answers = iter([429, 429, 429])
        slept = []
        receipts = mod.submit("example.org", KEY, ["https://example.org/a"],
                              post=lambda *a: (next(answers), b""), sleep=slept.append)
        self.assertEqual(receipts[0]["verdict"], "FAILED")
        self.assertEqual(slept, [30, 60, 90])

    def test_batches_split_at_the_protocol_limit(self):
        urls = [f"https://example.org/{i}" for i in range(mod.BATCH + 1)]
        receipts = mod.submit("example.org", KEY, urls, post=lambda *a: (200, b""))
        self.assertEqual([r["urls"] for r in receipts], [mod.BATCH, 1])

    def test_a_key_file_that_does_not_serve_the_key_blocks_the_send(self):
        original = mod.http
        mod.http = lambda url, *a, **k: (404, b"")
        try:
            with self.assertRaises(SystemExit):
                mod.prove_key("example.org", KEY)
        finally:
            mod.http = original


if __name__ == "__main__":
    unittest.main()
