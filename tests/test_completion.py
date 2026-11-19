import threading
from dataclasses import replace

import pytest
from devmind.api import create_app
from devmind.config import load
from devmind.database import Repository, runs
from devmind.readiness import inspect
from devmind.runner import Runner
from fastapi.testclient import TestClient
from sqlalchemy import update
from test_runner import FIX, PLAN, READ, run


def test_action_budget_retains_candidate(repository, config, request_body):
    identifier, _ = run(
        repository, replace(config, steps=3), request_body, [PLAN, READ, FIX]
    )
    assert repository.get(identifier)["status"] == "failed"
    assert (
        "self.clock() >= expiry" in repository.artifact(identifier, "patch")["content"]
    )


def test_expiry_records_event(repository, request_body):
    identifier, _ = repository.submit(request_body, "expired-event", 10)
    repository.claim("old-owner", 10)
    with repository.engine.begin() as conn:
        conn.execute(update(runs).where(runs.c.id == identifier).values(lease=1))
    assert repository.claim("new-owner", 10) is None
    assert repository.timeline(identifier)[-1]["kind"] == "interrupted"
    assert repository.get(identifier)["lease"] is None


def test_shutdown_does_not_claim(repository, config, request_body):
    identifier, _ = repository.submit(request_body, "shutdown-test", 10)
    stop = threading.Event()
    stop.set()
    assert not Runner(config, repository, shutdown=stop).once()
    assert repository.get(identifier)["status"] == "queued"


def test_readiness_checks_schema(config):
    store = Repository(config.database)
    with TestClient(create_app(config, store)) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/ready").status_code == 503
        assert client.get("/api/readiness").status_code == 401
        store.initialize()
        assert client.get("/ready").status_code == 200
    store.engine.dispose()


def test_execution_readiness_fails_without_dependencies(
    config, repository, monkeypatch
):
    monkeypatch.setattr("devmind.readiness.shutil.which", lambda _: None)
    report = inspect(replace(config, model=""), repository)
    assert not report["ready"]
    assert report["checks"]["database"]["ready"]
    assert not report["checks"]["docker"]["ready"]
    assert not report["checks"]["model"]["ready"]


@pytest.mark.parametrize("field", ["steps", "seconds", "lease_seconds", "capacity"])
def test_budgets_reject_nonpositive(config, field):
    with pytest.raises(ValueError, match="positive"):
        replace(config, **{field: 0}).validate()


def test_environment_budgets(monkeypatch, config):
    monkeypatch.setenv("DEVMIND_API_TOKEN", config.api_token)
    monkeypatch.setenv("DEVMIND_STEPS", "12")
    assert load().steps == 12


def test_review_rejects_unknown_status(repository):
    with pytest.raises(ValueError, match="invalid review"):
        repository.review("nonexistent", "merged", "")


def test_schema_migration_rejects_unknown_version(repository):
    from devmind.database import schema_version

    repository.initialize()
    repository.check_schema()
    with repository.engine.begin() as conn:
        conn.execute(update(schema_version).values(version=999))
    with pytest.raises(RuntimeError, match="Unsupported"):
        repository.initialize()


def test_prediction_validation_includes_empty_patches(tmp_path):
    import json

    from devmind.evaluation import validate_predictions

    path = tmp_path / "predictions.jsonl"
    row = {
        "instance_id": "owner__repo-1",
        "model_name_or_path": "model",
        "model_patch": "",
    }
    path.write_text(json.dumps(row) + "\n")
    assert validate_predictions(path) == [row]
    path.write_text((json.dumps(row) + "\n") * 2)
    with pytest.raises(ValueError, match="Duplicate"):
        validate_predictions(path)


def test_harness_attempt_records_failure(tmp_path, monkeypatch):
    import json
    from types import SimpleNamespace

    from devmind.evaluation import evaluate

    path = tmp_path / "predictions.jsonl"
    path.write_text(
        json.dumps(
            {
                "instance_id": "owner__repo-1",
                "model_name_or_path": "model",
                "model_patch": "",
            }
        )
        + "\n"
    )
    monkeypatch.setattr(
        "devmind.evaluation.importlib.util.find_spec", lambda _: object()
    )
    monkeypatch.setattr(
        "devmind.evaluation.importlib.metadata.version", lambda _: "test"
    )
    commands = []

    def invoke(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=7)

    monkeypatch.setattr("devmind.evaluation.subprocess.run", invoke)
    output = tmp_path / "evaluation"
    assert evaluate(path, output, "princeton-nlp/SWE-bench_Lite", 1) == 7
    manifest = json.loads((output / "evaluation-manifest.json").read_text())
    assert manifest["status"] == "failed" and manifest["exit_code"] == 7
    assert commands[0][-1] == "owner__repo-1"
    with pytest.raises(FileExistsError):
        evaluate(path, output, "princeton-nlp/SWE-bench_Lite", 1)


def test_watchdog_fences_blocked_model(repository, config, request_body):
    import time

    from devmind.contracts import DECISION
    from test_runner import FixtureComputer

    class SlowPolicy:
        tokens = 0

        def decide(self, messages):
            time.sleep(1.3)
            # The watchdog must already have terminated ownership while waiting.
            assert repository.get(identifier)["status"] == "failed"
            return DECISION.validate_python(PLAN)

    identifier, _ = repository.submit(request_body, "watchdog-test", 10)
    Runner(
        replace(config, seconds=1),
        repository,
        lambda _: SlowPolicy(),
        FixtureComputer,
    ).once()
    job = repository.get(identifier)
    assert job["status"] == "failed"
    assert "wall-clock" in job["result"]["reason"]
    assert not any(e["kind"] == "action" for e in repository.timeline(identifier))
