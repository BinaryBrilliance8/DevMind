import os
import uuid

import pytest
from devmind.database import Repository
from devmind.isolation import DockerMachine, InfrastructureError


def test_no_host_fallback(monkeypatch, source):
    monkeypatch.setattr("devmind.isolation.shutil.which", lambda _: None)
    with pytest.raises(InfrastructureError, match="Docker is not installed"):
        DockerMachine("image", source, 10)


@pytest.mark.docker
@pytest.mark.skipif(
    os.environ.get("DEVMIND_TEST_DOCKER") != "1",
    reason="Docker integration explicitly gated",
)
def test_real_docker(source):
    machine = DockerMachine("devmind-executor:1", source, 10)
    try:
        assert (
            machine.invoke({"kind": "command", "argv": ["id", "-u"]})["stdout"].strip()
            == "65532"
        )
        assert (
            machine.invoke({"kind": "command", "argv": ["touch", "/opt/not-allowed"]})[
                "code"
            ]
            != 0
        )
        assert (
            machine.invoke(
                {
                    "kind": "command",
                    "argv": [
                        "python",
                        "-c",
                        "import socket; socket.create_connection(('1.1.1.1',443),1)",
                    ],
                }
            )["code"]
            != 0
        )
        machine.invoke(
            {
                "kind": "replace",
                "path": "cache.py",
                "expected": "self.clock() > expiry",
                "replacement": "self.clock() >= expiry",
            }
        )
        assert (
            machine.invoke(
                {
                    "kind": "command",
                    "argv": ["python", "-m", "unittest", "discover", "-s", "tests"],
                }
            )["code"]
            == 0
        )
    finally:
        machine.dispose()


@pytest.mark.postgres
@pytest.mark.skipif(
    not os.environ.get("DEVMIND_TEST_POSTGRES"),
    reason="Dedicated PostgreSQL integration database required",
)
def test_real_postgres(request_body):
    repository = Repository(os.environ["DEVMIND_TEST_POSTGRES"])
    repository.initialize()
    identifier, _ = repository.submit(
        request_body, "integration-" + uuid.uuid4().hex, 1000
    )
    claimed = repository.claim("integration-worker", 60)
    assert claimed and claimed["id"] == identifier
    assert repository.cancel(identifier)
    repository.engine.dispose()


@pytest.mark.postgres
@pytest.mark.skipif(
    not os.environ.get("DEVMIND_TEST_POSTGRES"),
    reason="Dedicated PostgreSQL integration database required",
)
def test_postgres_concurrent_claim_and_fencing(request_body):
    from concurrent.futures import ThreadPoolExecutor

    repository = Repository(os.environ["DEVMIND_TEST_POSTGRES"])
    repository.initialize()
    identifiers = {
        repository.submit(request_body, "parallel-" + uuid.uuid4().hex, 1000)[0]
        for _ in range(8)
    }

    def claim_one(index):
        owner = "parallel-" + str(index)
        row = repository.claim(owner, 60)
        return owner, row

    with ThreadPoolExecutor(max_workers=8) as pool:
        claimed = list(pool.map(claim_one, range(8)))
    assert {row["id"] for _, row in claimed} == identifiers
    for owner, row in claimed:
        assert repository.cancel(row["id"])
        assert not repository.emit(row["id"], owner, "late", {})
        assert not repository.complete(row["id"], owner, "review", {})
    repository.engine.dispose()
