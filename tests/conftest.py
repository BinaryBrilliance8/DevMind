import base64
from pathlib import Path

import pytest
from devmind.config import Config
from devmind.contracts import Project, RunRequest
from devmind.database import Repository
from devmind.operations import git, populate

PROJECT_ROOT = Path(__file__).parents[1]
TOKEN = "test-operator-token-with-thirty-two-characters"


@pytest.fixture
def source():
    root = PROJECT_ROOT / "examples/cache_repo"
    return {
        p.relative_to(root).as_posix(): {
            "content": base64.b64encode(p.read_bytes()).decode(),
            "mode": 420,
        }
        for p in root.rglob("*.py")
    }


@pytest.fixture
def config(tmp_path, source):
    root = tmp_path / "repository"
    root.mkdir()
    populate(root, source)
    git(root, ["init", "-q"])
    git(root, ["add", "."])
    git(
        root,
        [
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-qm",
            "baseline",
        ],
    )
    return Config(
        database=f"sqlite:///{tmp_path}/db.sqlite",
        api_token=TOKEN,
        projects=(
            Project(
                key="cache",
                name="Cache",
                checkout=root,
                verify=["python", "-m", "unittest", "discover", "-s", "tests", "-v"],
            ),
        ),
        model="scripted-test-policy",
        web=PROJECT_ROOT / "web",
    )


@pytest.fixture
def repository(config):
    store = Repository(config.database)
    store.initialize()
    yield store
    store.engine.dispose()


@pytest.fixture
def request_body():
    return RunRequest(
        project="cache",
        title="Fix cache expiration boundary",
        issue="Items must expire at the exact TTL boundary, including a zero TTL.",
    )
