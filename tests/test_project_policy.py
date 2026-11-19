from dataclasses import replace

import pytest
from devmind.contracts import Project
from test_runner import PLAN, SUBMIT, run


def test_protected_path_aliases_are_canonical(config):
    data = config.projects[0].model_dump()
    project = Project.model_validate(
        data | {"protected": ["./tests", "tests/", "tests"]}
    )
    assert project.protected == ["tests"]


@pytest.mark.parametrize(
    "path", [".", "..", "../tests", "/tests", "a\\tests", "", ".git"]
)
def test_invalid_protected_paths_fail(config, path):
    with pytest.raises(ValueError):
        Project.model_validate(config.projects[0].model_dump() | {"protected": [path]})


@pytest.mark.parametrize("argv", [[""], ["python", "\0"], ["x" * 8001]])
def test_invalid_verification_arguments_fail(config, argv):
    with pytest.raises(ValueError):
        Project.model_validate(config.projects[0].model_dump() | {"verify": argv})


def test_dot_prefix_still_protects_tests(repository, config, request_body):
    project = Project.model_validate(
        config.projects[0].model_dump() | {"protected": ["./tests/"]}
    )
    actions = [
        PLAN,
        {"kind": "read", "path": "tests/test_cache.py"},
        {
            "kind": "replace",
            "path": "tests/test_cache.py",
            "expected": "self.now = 15.0",
            "replacement": "self.now = 16.0",
        },
        SUBMIT,
    ]
    identifier, boxes = run(
        repository, replace(config, projects=(project,), steps=4), request_body, actions
    )
    assert repository.get(identifier)["status"] == "failed"
    assert len(boxes) == 1
    assert any(
        e["kind"] == "observation"
        and e["payload"]["observation"].get("error") == "Protected paths changed"
        for e in repository.timeline(identifier)
    )
