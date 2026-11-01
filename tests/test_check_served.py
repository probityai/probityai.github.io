"""Tests for the Pages build wait in scripts/check_served.py."""

import importlib.util
import pathlib
import unittest

SPEC = importlib.util.spec_from_file_location(
    "check_served", pathlib.Path(__file__).resolve().parents[1] / "scripts" / "check_served.py"
)
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)

SHA = "a" * 40


class Clock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = 0

    def sleep(self, seconds):
        self.now += seconds
        self.sleeps += 1

    def __call__(self):
        return self.now


def reader(answers):
    items = list(answers)

    def read():
        item = items.pop(0) if len(items) > 1 else items[0]
        if isinstance(item, Exception):
            raise item
        return item

    return read


def built(commit=SHA):
    return {"status": "built", "commit": commit}


class WaitForBuild(unittest.TestCase):
    def run_wait(self, answers, deadline=100.0):
        clock = Clock()
        mod.wait_for_build(SHA, reader(answers), clock.sleep, clock, deadline, 10.0)
        return clock

    def test_built_at_once(self):
        self.assertEqual(self.run_wait([built()]).sleeps, 0)

    def test_built_after_polls(self):
        building = {"status": "building", "commit": SHA}
        stale = built("b" * 40)
        self.assertEqual(self.run_wait([stale, building, building, built()]).sleeps, 3)

    def test_transient_read_failure_is_retried(self):
        self.assertEqual(self.run_wait([mod.BuildError("could not read"), built()]).sleeps, 1)

    def test_errored_build_fails_at_once(self):
        clock = Clock()
        errored = {"status": "errored", "commit": SHA, "error": {"message": "boom"}}
        with self.assertRaisesRegex(mod.BuildErrored, "errored.*boom"):
            mod.wait_for_build(SHA, reader([errored]), clock.sleep, clock, 100.0, 10.0)
        self.assertEqual(clock.sleeps, 0)

    def test_deadline_exceeded_says_the_build_did_not_finish(self):
        building = {"status": "building", "commit": SHA}
        with self.assertRaisesRegex(mod.BuildError, "did not finish"):
            self.run_wait([building], deadline=35.0)

    def test_other_commit_built_never_satisfies(self):
        with self.assertRaisesRegex(mod.BuildError, "did not finish"):
            self.run_wait([built("c" * 40)], deadline=25.0)


if __name__ == "__main__":
    unittest.main()
