"""Public task schemas and a discriminated, typed agent-computer interface."""

from pathlib import Path, PurePosixPath
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator

from devmind.operations import safe_name


def validate_arguments(value: list[str]) -> list[str]:
    if any(not v or len(v) > 8000 or "\0" in v for v in value):
        raise ValueError("invalid command arguments")
    return value


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Project(Contract):
    key: str = Field(pattern=r"^[a-z0-9_-]{1,64}$")
    name: str = Field(min_length=1, max_length=100)
    checkout: Path
    image: str = "devmind-executor:1"
    verify: list[str] = Field(min_length=1, max_length=30)
    protected: list[str] = Field(default_factory=lambda: ["tests"])

    @field_validator("protected")
    @classmethod
    def relative_paths(cls, paths: list[str]) -> list[str]:
        normalized = []
        for path in paths:
            name = str(PurePosixPath(path))
            safe_name(name)
            normalized.append(name)
        return list(dict.fromkeys(normalized))

    @field_validator("verify")
    @classmethod
    def verification_arguments(cls, value: list[str]) -> list[str]:
        return validate_arguments(value)


class RunRequest(Contract):
    project: str = Field(pattern=r"^[a-z0-9_-]{1,64}$")
    title: str = Field(min_length=3, max_length=140)
    issue: str = Field(min_length=20, max_length=20000)
    commit: str | None = Field(default=None, pattern=r"^[a-f0-9]{40}$")
    benchmark_id: str | None = Field(default=None, pattern=r"^[\w.-]{1,160}$")


class Plan(Contract):
    kind: Literal["plan"]
    steps: list[str] = Field(min_length=1, max_length=8)


class Locate(Contract):
    kind: Literal["locate"]
    query: str = Field(default="", max_length=200)


class Read(Contract):
    kind: Literal["read"]
    path: str = Field(max_length=300)
    first_line: int = Field(default=1, ge=1)
    line_count: int = Field(default=120, ge=1, le=300)


class Replace(Contract):
    kind: Literal["replace"]
    path: str = Field(max_length=300)
    expected: str = Field(max_length=80000)
    replacement: str = Field(max_length=80000)


class Command(Contract):
    kind: Literal["command"]
    argv: list[str] = Field(min_length=1, max_length=30)

    @field_validator("argv")
    @classmethod
    def safe_arguments(cls, value: list[str]) -> list[str]:
        return validate_arguments(value)


class Verify(Contract):
    kind: Literal["verify"]


class Submit(Contract):
    kind: Literal["submit"]
    summary: str = Field(min_length=5, max_length=1500)


Decision = Annotated[
    Plan | Locate | Read | Replace | Command | Verify | Submit,
    Field(discriminator="kind"),
]
DECISION = TypeAdapter(Decision)


class Review(Contract):
    decision: Literal["approved", "rejected"]
    note: str = Field(min_length=3, max_length=2000)
