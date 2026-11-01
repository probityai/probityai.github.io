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


RUNNING = ({"id": 1, "name": "pages-build-deployment", "status": "in_progress"},)


class WaitForIdle(unittest.TestCase):
    """A push to pages-live waits until no Pages deploy is in flight (runs 41289027907 and 41290076112)."""

    def test_returns_at_once_when_nothing_is_in_flight(self):
        clock = Clock()
        mod.wait_for_idle(reader([[]]), clock.sleep, clock, 100.0, 10.0)
        self.assertEqual(clock.sleeps, 0)

    def test_waits_while_a_deploy_runs(self):
        clock = Clock()
        mod.wait_for_idle(reader([list(RUNNING), list(RUNNING), []]), clock.sleep, clock, 100.0, 10.0)
        self.assertEqual(clock.sleeps, 2)

    def test_an_unreadable_run_list_is_never_idle(self):
        clock = Clock()
        with self.assertRaises(mod.BuildError):
            mod.wait_for_idle(reader([mod.BuildError("down")]), clock.sleep, clock, 30.0, 10.0)

    def test_a_deploy_still_running_at_the_deadline_fails(self):
        clock = Clock()
        with self.assertRaisesRegex(mod.BuildError, "still in flight"):
            mod.wait_for_idle(reader([list(RUNNING)]), clock.sleep, clock, 30.0, 10.0)
