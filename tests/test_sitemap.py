"""Tests for scripts/sitemap.py: lastmod follows the page bytes, never the clock."""

import importlib.util
import json
import pathlib
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location(
    "sitemap", pathlib.Path(__file__).resolve().parents[1] / "scripts" / "sitemap.py"
)
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)

HOST = mod.HOST


def page(canonical, extra=""):
    link = f'<link rel="canonical" href="{canonical}">' if canonical else ""
    return f"<!doctype html><html><head>{link}{extra}</head><body>x</body></html>"


def make_tree(root, files):
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


class SitemapTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tree = pathlib.Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        make_tree(
            self.tree,
            {
                "index.html": page(f"{HOST}/"),
                "agent-evidence-atlas/index.html": page(f"{HOST}/agent-evidence-atlas/"),
                "agent-evidence-atlas/start.html": page(f"{HOST}/agent-evidence-atlas/start.html"),
                "agent-evidence/index.html": page("https://w3id.org/agent-evidence/"),
                "agent-evidence/vocab/v1/x/index.html": page("https://w3id.org/agent-evidence/vocab/v1/x"),
                "hidden.html": page(f"{HOST}/hidden.html", '<meta name="robots" content="noindex">'),
                "nocanonical.html": page(None),
            },
        )

    def run_once(self, today, prior=None):
        pages = mod.scan(self.tree)
        ledger, changed = mod.update(pages, mod.read_ledger(prior), today)
        mod.write(self.tree, pages, ledger)
        return ledger, changed

    def test_lists_only_pages_that_name_this_host(self):
        pages = mod.scan(self.tree)
        self.assertEqual(
            sorted(url for url, _ in pages.values()),
            [
                f"{HOST}/",
                f"{HOST}/agent-evidence-atlas/",
                f"{HOST}/agent-evidence-atlas/start.html",
            ],
        )

    def test_first_run_stamps_today_and_reports_every_page_changed(self):
        ledger, changed = self.run_once("2026-11-04")
        self.assertEqual({row["lastmod"] for row in ledger.values()}, {"2026-11-04"})
        self.assertEqual(len(changed), 3)

    def test_unchanged_page_keeps_its_date_and_changed_page_gets_today(self):
        self.run_once("2026-11-04")
        prior = self.tree / mod.LEDGER
        (self.tree / "agent-evidence-atlas/start.html").write_text(page(f"{HOST}/agent-evidence-atlas/start.html", "<b>new</b>"))
        ledger, changed = self.run_once("2026-11-09", prior)
        self.assertEqual(ledger["index.html"]["lastmod"], "2026-11-04")
        self.assertEqual(ledger["agent-evidence-atlas/start.html"]["lastmod"], "2026-11-09")
        self.assertEqual(changed, [f"{HOST}/agent-evidence-atlas/start.html"])

    def test_second_run_on_the_same_tree_writes_the_same_bytes(self):
        self.run_once("2026-11-04")
        first = {p.name: p.read_bytes() for p in (self.tree / mod.SITEMAP, self.tree / mod.LEDGER)}
        _, changed = self.run_once("2026-12-25", self.tree / mod.LEDGER)
        second = {p.name: p.read_bytes() for p in (self.tree / mod.SITEMAP, self.tree / mod.LEDGER)}
        self.assertEqual(first, second)
        self.assertEqual(changed, [])

    def test_removed_page_leaves_the_ledger_and_the_sitemap(self):
        self.run_once("2026-11-04")
        (self.tree / "agent-evidence-atlas/start.html").unlink()
        ledger, _ = self.run_once("2026-11-05", self.tree / mod.LEDGER)
        self.assertNotIn("agent-evidence-atlas/start.html", ledger)
        self.assertNotIn("start.html", (self.tree / mod.SITEMAP).read_text())

    def test_every_url_carries_a_date_and_the_section_sitemap_is_scoped(self):
        self.run_once("2026-11-04")
        site = (self.tree / mod.SITEMAP).read_text()
        self.assertEqual(site.count("<loc>"), site.count("<lastmod>"))
        scoped = (self.tree / "agent-evidence-atlas" / mod.SITEMAP).read_text()
        self.assertEqual(scoped.count("<loc>"), 2)
        self.assertNotIn(f"<loc>{HOST}/</loc>", scoped)

    def test_a_malformed_ledger_row_is_fatal(self):
        bad = self.tree / "bad.json"
        bad.write_text(json.dumps({"pages": {"index.html": {"sha256": "ab", "lastmod": "yesterday"}}}))
        with self.assertRaises(SystemExit):
            mod.read_ledger(bad)

    def test_the_committed_seed_is_well_formed(self):
        seed = pathlib.Path(__file__).resolve().parents[1] / mod.LEDGER
        self.assertTrue(mod.read_ledger(seed))


if __name__ == "__main__":
    unittest.main()
