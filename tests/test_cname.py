"""Tests for CNAME: the one file that keeps the site, and every identifier under it, at probityai.org.

GitHub Pages serves this site from the pages-live branch, which sync-atlas.yml rewrites from main on every
publish. For a branch-published site the custom domain lives in the CNAME file of that branch, so a publish
without this file would remove probityai.org from the site. Every https://probityai.org/<path> identifier
would then stop resolving, and the forwarding of every https://probityai.github.io/<path> link would stop
with it. The domain is verified for the probityai organisation; the file must name exactly it.
"""

import pathlib
import unittest

FILE = pathlib.Path(__file__).resolve().parents[1] / "CNAME"


class Cname(unittest.TestCase):
    def test_names_exactly_the_verified_domain(self):
        self.assertEqual(FILE.read_bytes(), b"probityai.org\n")


if __name__ == "__main__":
    unittest.main()
