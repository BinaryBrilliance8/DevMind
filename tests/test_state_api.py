from concurrent.futures import ThreadPoolExecutor

import pytest
from devmind.api import create_app
from devmind.database import Rejected
from fastapi.testclient import TestClient


def test_idempotency_capacity_and_claim(repository, request_body):
    first, created = repository.submit(request_body, "key-one", 1)
    assert created
    assert repository.submit(request_body, "key-one", 1) == (first, False)
    with pytest.raises(Rejected):
        repository.submit(request_body, "key-two", 1)
    with pytest.raises(Rejected):
        repository.submit(
            request_body.model_copy(update={"title": "Another title"}), "key-one", 1
        )
    with ThreadPoolExecutor(max_workers=6) as pool:
        claimed = list(pool.map(lambda n: repository.claim(str(n), 60), range(6)))
    assert sum(item is not None for item in claimed) == 1


def test_cancellation_fences_every_write(repository, request_body):
    identifier, _ = repository.submit(request_body, "key-one", 10)
    repository.claim("owner", 60)
    assert repository.cancel(identifier)
    assert not repository.alive(identifier, "owner", 60)
    assert not repository.emit(identifier, "owner", "late", {})
    assert not repository.complete(identifier, "owner", "review", {}, "patch")
    assert repository.get(identifier)["status"] == "cancelled"


def test_expiry_and_review_transition(repository, request_body):
    identifier, _ = repository.submit(request_body, "key-one", 10)
    repository.claim("owner", -1)
    assert repository.claim("new-owner", 60) is None
    assert repository.get(identifier)["status"] == "interrupted"
    second, _ = repository.submit(request_body, "key-two", 10)
    repository.claim("owner", 60)
    assert repository.complete(second, "owner", "review", {"summary": "done"}, "patch")
    assert repository.artifact(second, "patch")["content"] == "patch"
    assert repository.review(second, "approved", "Reviewed all tests")
    assert not repository.review(second, "rejected", "Cannot review twice")


def test_api_authorization_and_lifecycle(config, repository, request_body):
    headers = {
        "Authorization": "Bearer " + config.api_token,
        "Idempotency-Key": "test-request-01",
    }
    with TestClient(create_app(config, repository)) as client:
        assert client.get("/").status_code == 200
        assert client.get("/assets/app.js").status_code == 200
        assert client.get("/api/runs").status_code == 401
        assert client.get("/health").json()["status"] == "online"
        response = client.post(
            "/api/runs", headers=headers, json=request_body.model_dump()
        )
        assert response.status_code == 201
        identifier = response.json()["id"]
        assert (
            client.post(
                "/api/runs", headers=headers, json=request_body.model_dump()
            ).status_code
            == 200
        )
        assert (
            "owner" not in client.get("/api/runs/" + identifier, headers=headers).json()
        )
        assert (
            client.get(f"/api/runs/{identifier}/patch", headers=headers).status_code
            == 409
        )
        assert (
            client.get(
                f"/api/runs/{identifier}/trajectory", headers=headers
            ).status_code
            == 422
        )
        assert (
            client.post(
                f"/api/runs/{identifier}/review",
                headers=headers,
                json={"decision": "approved", "note": "Premature"},
            ).status_code
            == 409
        )
        assert client.post(f"/api/runs/{identifier}/cancel", headers=headers).json()[
            "cancelled"
        ]
        assert client.get("/api/runs/missing", headers=headers).status_code == 404
        assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
        assert response.headers["cache-control"] == "no-store"


def test_api_schema_and_size_bounds(config, repository, request_body):
    headers = {
        "Authorization": "Bearer " + config.api_token,
        "Idempotency-Key": "test-request-02",
    }
    with TestClient(create_app(config, repository)) as client:
        assert (
            client.post("/api/runs", headers=headers, content=b"x" * 33000).status_code
            == 413
        )
        assert (
            client.post(
                "/api/runs",
                headers=headers,
                json=request_body.model_dump() | {"shell": "bad"},
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/runs",
                headers=headers,
                json=request_body.model_dump() | {"project": "missing"},
            ).status_code
            == 422
        )


def test_prediction_and_approved_export(config, repository, request_body):
    request_body.benchmark_id = "org__cache-1"
    identifier, _ = repository.submit(request_body, "benchmark", 10)
    repository.claim("owner", 60)
    repository.complete(identifier, "owner", "review", {"model": "fixture"}, "patch")
    headers = {"Authorization": "Bearer " + config.api_token}
    with TestClient(create_app(config, repository)) as client:
        assert (
            client.get(
                f"/api/runs/{identifier}/trajectory?consent=true", headers=headers
            ).status_code
            == 409
        )
        repository.review(identifier, "approved", "Reviewed by human")
        assert (
            client.get(
                f"/api/runs/{identifier}/trajectory?consent=true", headers=headers
            ).status_code
            == 200
        )
        exported = client.get(
            f"/api/runs/{identifier}/prediction", headers=headers
        ).json()
        assert exported == {
            "instance_id": "org__cache-1",
            "model_name_or_path": "fixture",
            "model_patch": "patch",
        }
