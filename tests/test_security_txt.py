"""Tests for .well-known/security.txt: the RFC 9116 fields a reporter and a scanner read.

RFC 9116 requires Contact and Expires, and a file past its Expires must be treated as stale. The
test fails 30 days before the date, so the next run of CI asks for a new date in time.
"""

import datetime as dt
import pathlib
import unittest

FILE = pathlib.Path(__file__).resolve().parents[1] / ".well-known" / "security.txt"
HORIZON = dt.timedelta(days=30)


def fields(text):
    out = {}
    for line in text.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        key, sep, value = line.partition(":")
        assert sep, f"not a field: {line!r}"
        out.setdefault(key.strip().lower(), []).append(value.strip())
    return out


class SecurityTxt(unittest.TestCase):
    def setUp(self):
        self.f = fields(FILE.read_text(encoding="utf-8"))

    def test_required_fields(self):
        self.assertTrue(self.f.get("contact"), "Contact is required")
        self.assertEqual(len(self.f.get("expires", [])), 1, "exactly one Expires is required")
        for c in self.f["contact"]:
            self.assertTrue(c.startswith(("https://", "mailto:")), c)

    def test_canonical_is_the_served_path(self):
        self.assertEqual(self.f.get("canonical"), ["https://probityai.github.io/.well-known/security.txt"])

    def test_not_about_to_expire(self):
        expires = dt.datetime.fromisoformat(self.f["expires"][0].replace("Z", "+00:00"))
        now = dt.datetime.now(dt.timezone.utc)
        self.assertGreater(expires - now, HORIZON, "set Expires to a date under a year away")
        self.assertLess(expires - now, dt.timedelta(days=366), "RFC 9116 asks for less than a year")


if __name__ == "__main__":
    unittest.main()
