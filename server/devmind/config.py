"""Operator-only configuration; no credentials are stored in source files."""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from devmind.contracts import Project


def default_web() -> Path:
    packaged = Path(__file__).parent / "web"
    return packaged if packaged.is_dir() else Path("web").resolve()


@dataclass(frozen=True)
class Config:
    database: str = "sqlite:///./state/devmind.db"
    projects: tuple[Project, ...] = ()
    api_token: str = field(default="", repr=False)
    model_key: str = field(default="", repr=False)
    model_url: str = "http://127.0.0.1:8001/v1"
    model: str = ""
    steps: int = 40
    seconds: int = 1200
    command_seconds: int = 90
    token_limit: int = 120000
    context_chars: int = 120000
    lease_seconds: int = 120
    capacity: int = 200
    web: Path = field(default_factory=default_web)

    def project(self, key: str) -> Project:
        for project in self.projects:
            if project.key == key:
                return project
        raise ValueError("Unknown project; register it in the operator project file")

    def validate(self) -> None:
        if len(self.api_token) < 32:
            raise ValueError("DEVMIND_API_TOKEN needs at least 32 characters")
        if len({p.key for p in self.projects}) != len(self.projects):
            raise ValueError("project keys must be unique")
        for name in (
            "steps",
            "seconds",
            "command_seconds",
            "token_limit",
            "context_chars",
            "lease_seconds",
            "capacity",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        url = urlsplit(self.model_url)
        if not url.hostname:
            raise ValueError("model endpoint requires a hostname")
        if not (
            url.scheme == "https"
            or (
                url.scheme == "http"
                and url.hostname in {"localhost", "127.0.0.1", "::1"}
            )
        ):
            raise ValueError("model endpoint requires HTTPS or loopback HTTP")
        if url.username or url.password or url.query or url.fragment:
            raise ValueError(
                "model URL must not contain credentials or query parameters"
            )


def load() -> Config:
    registry = Path(os.environ.get("DEVMIND_PROJECTS", "projects.json")).resolve()
    projects = []
    if registry.exists():
        for entry in json.loads(registry.read_text()):
            project = Project.model_validate(entry)
            project.checkout = (registry.parent / project.checkout).resolve()
            projects.append(project)
    config = Config(
        database=os.environ.get("DEVMIND_DATABASE", "sqlite:///./state/devmind.db"),
        projects=tuple(projects),
        api_token=os.environ.get("DEVMIND_API_TOKEN", ""),
        model_key=os.environ.get("DEVMIND_MODEL_KEY", ""),
        model_url=os.environ.get("DEVMIND_MODEL_URL", "http://127.0.0.1:8001/v1"),
        model=os.environ.get("DEVMIND_MODEL", ""),
        web=Path(os.environ.get("DEVMIND_WEB", str(default_web()))).resolve(),
        **{
            name: int(os.environ.get("DEVMIND_" + name.upper(), str(default)))
            for name, default in {
                "steps": 40,
                "seconds": 1200,
                "command_seconds": 90,
                "token_limit": 120000,
                "context_chars": 120000,
                "lease_seconds": 120,
                "capacity": 200,
            }.items()
        },
    )
    config.validate()
    return config
