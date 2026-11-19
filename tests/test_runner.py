"""Scripted policy tests execute only the authored TTL-cache fixture locally."""

import sys
import tempfile
from dataclasses import replace
from pathlib import Path

from devmind.contracts import DECISION
from devmind.executor import Computer
from devmind.runner import Runner

PLAN = {
    "kind": "plan",
    "steps": ["Inspect cache expiry", "Correct the boundary", "Verify all cache tests"],
}
READ = {"kind": "read", "path": "cache.py"}
FIX = {
    "kind": "replace",
    "path": "cache.py",
    "expected": "self.clock() > expiry",
    "replacement": "self.clock() >= expiry",
}
SUBMIT = {"kind": "submit", "summary": "Expire entries at the exact TTL boundary."}


class ScriptedPolicy:
    def __init__(self, actions):
        self.actions = iter(actions)
        self.tokens = 0

    def decide(self, messages):
        self.tokens += 10
        item = next(self.actions)
        if isinstance(item, Exception):
            raise item
        return DECISION.validate_python(item)


class FixtureComputer:
    def __init__(self, image, files, seconds):
        self.temp = tempfile.TemporaryDirectory()
        self.computer = Computer(Path(self.temp.name))
        self.computer.invoke({"kind": "initialize", "files": files})
        self.closed = False

    def invoke(self, action):
        if action["kind"] == "command":
            assert action["argv"] == [
                "python",
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests",
                "-v",
            ]
            action = action | {"argv": [sys.executable, *action["argv"][1:]]}
        return self.computer.invoke(action)

    def dispose(self):
        self.closed = True
        self.temp.cleanup()


def run(repository, config, request_body, actions):
    identifier, _ = repository.submit(request_body, "fixture-attempt", 10)
    boxes = []

    def factory(*args):
        box = FixtureComputer(*args)
        boxes.append(box)
        return box

    runner = Runner(config, repository, lambda _: ScriptedPolicy(actions), factory)
    assert runner.once()
    return identifier, boxes


def test_complete_repair_awaits_human_review(repository, config, request_body):
    identifier, boxes = run(repository, config, request_body, [PLAN, READ, FIX, SUBMIT])
    job = repository.get(identifier)
    assert job["status"] == "review"
    assert job["result"]["baseline"]["code"] != 0
    assert job["result"]["verification"]["code"] == 0
    assert len(boxes) == 2 and all(box.closed for box in boxes)
    assert (
        "+        if self.clock() >= expiry:"
        in repository.artifact(identifier, "patch")["content"]
    )


def test_bad_patch_self_correction(repository, config, request_body):
    wrong = FIX | {"replacement": "self.clock() > expiry + 1"}
    correct = FIX | {"expected": "self.clock() > expiry + 1"}
    identifier, boxes = run(
        repository, config, request_body, [PLAN, READ, wrong, SUBMIT, correct, SUBMIT]
    )
    assert repository.get(identifier)["status"] == "review"
    assert len(boxes) == 3
    evidence = [
        e["payload"]["code"]
        for e in repository.timeline(identifier)
        if e["kind"] == "verification"
    ]
    assert evidence == [1, 0]


def test_plan_and_read_are_required(repository, config, request_body):
    identifier, _ = run(
        repository, replace(config, steps=3), request_body, [FIX, PLAN, FIX]
    )
    assert repository.get(identifier)["status"] == "failed"
    observations = [
        e["payload"]["observation"]
        for e in repository.timeline(identifier)
        if e["kind"] == "observation"
    ]
    assert "plan" in observations[0]["error"]
    assert "Read" in observations[-1]["error"]


def test_protected_tests_cannot_be_submitted(repository, config, request_body):
    testpath = "tests/test_cache.py"
    actions = [
        PLAN,
        {"kind": "read", "path": testpath},
        {
            "kind": "replace",
            "path": testpath,
            "expected": "self.now = 15.0",
            "replacement": "self.now = 16.0",
        },
        SUBMIT,
    ]
    identifier, boxes = run(repository, replace(config, steps=4), request_body, actions)
    assert repository.get(identifier)["status"] == "failed" and len(boxes) == 1


def test_missing_model_fails_truthfully(repository, config, request_body):
    identifier, _ = repository.submit(request_body, "missing-model", 10)
    Runner(replace(config, model=""), repository).once()
    assert "Configure DEVMIND_MODEL" in repository.get(identifier)["result"]["reason"]


def test_invalid_response_recovers(repository, config, request_body):
    identifier, _ = run(
        repository,
        config,
        request_body,
        [ValueError("bad JSON"), PLAN, READ, FIX, SUBMIT],
    )
    assert repository.get(identifier)["status"] == "review"
    assert any(e["kind"] == "invalid_action" for e in repository.timeline(identifier))
