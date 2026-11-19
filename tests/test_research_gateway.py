import json
from dataclasses import replace

import httpx
import pytest
from devmind.model import Gateway
from devmind.research import intake, prepare


def test_gateway_reads_typed_action_and_usage(config, monkeypatch):
    client = httpx.Client

    def respond(request):
        assert json.loads(request.content)["model"] == config.model
        return httpx.Response(
            200,
            json={
                "usage": {"total_tokens": 33},
                "choices": [
                    {"message": {"content": '{"kind":"locate","query":"expiry"}'}}
                ],
            },
        )

    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: client(transport=httpx.MockTransport(respond), **kwargs),
    )
    gateway = Gateway(config)
    assert gateway.decide([{"role": "user", "content": "test"}]).kind == "locate"
    assert gateway.tokens == 33


def test_gateway_retries_are_bounded(config, monkeypatch):
    client = httpx.Client
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(503)

    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: client(transport=httpx.MockTransport(respond), **kwargs),
    )
    monkeypatch.setattr("devmind.model.time.sleep", lambda _: None)
    with pytest.raises(RuntimeError, match="unavailable"):
        Gateway(config).decide([])
    assert len(calls) == 3


def test_configuration_rejects_insecure_endpoint(config):
    with pytest.raises(ValueError):
        replace(config, model_url="http://external.invalid/v1").validate()
    with pytest.raises(ValueError):
        replace(config, api_token="weak").validate()


def test_benchmark_import_excludes_gold(tmp_path, config, repository):
    dataset = tmp_path / "instances.jsonl"
    dataset.write_text(
        json.dumps(
            {
                "instance_id": "org__repo-1",
                "repo": "org/repo",
                "base_commit": "a" * 40,
                "problem_statement": "Fix expiration behavior at the exact boundary.",
                "patch": "GOLD_SECRET",
                "test_patch": "GOLD_TEST",
            }
        )
        + "\n"
    )
    identifier = intake(
        dataset, {"org/repo": "cache"}, repository, config, "experiment-1"
    )[0]
    assert "GOLD" not in json.dumps(repository.get(identifier))
    assert intake(
        dataset, {"org/repo": "cache"}, repository, config, "experiment-1"
    ) == [identifier]


def test_training_repository_split(tmp_path):
    def trajectory(project):
        return {
            "run": {
                "id": project,
                "status": "approved",
                "request": {"project": project, "issue": "Fix the relevant behavior"},
                "result": {
                    "protected": ["tests"],
                    "test_command": ["pytest"],
                    "commit": "a" * 40,
                },
            },
            "events": [
                {
                    "kind": "action",
                    "payload": {"action": {"kind": "locate", "query": project}},
                }
            ],
        }

    data = tmp_path / "traces.jsonl"
    data.write_text(
        "\n".join(
            json.dumps(trajectory(project)) for project in ["train-project", "held-out"]
        )
    )
    report = prepare(data, tmp_path / "prepared", {"held-out"})
    assert report["training_examples"] == report["validation_examples"] == 1
    assert (
        json.loads((tmp_path / "prepared/train.jsonl").read_text())["project"]
        == "train-project"
    )
    assert (
        json.loads((tmp_path / "prepared/validation.jsonl").read_text())["project"]
        == "held-out"
    )
    with pytest.raises(ValueError):
        prepare(data, tmp_path / "prepared", set())


def test_gateway_preserves_invalid_response_for_explicit_research(config, monkeypatch):
    client = httpx.Client
    record = {
        "usage": {"total_tokens": 7},
        "choices": [
            {
                "message": {
                    "content": json.dumps({"kind": "plan", "steps": ["step"] * 9})
                }
            }
        ],
    }
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: client(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=record)),
            **kwargs,
        ),
    )
    gateway = Gateway(config)
    with pytest.raises(ValueError):
        gateway.decide([])
    assert gateway.last_response == record
    assert gateway.tokens == 7
