"""A Docker boundary with explicit failure, resource limits and no host fallback."""

import json
import shutil
import uuid
from typing import Protocol

from devmind.operations import execute


class Machine(Protocol):
    def invoke(self, action: dict) -> dict: ...
    def dispose(self) -> None: ...


class InfrastructureError(RuntimeError):
    """The execution environment is unavailable or failed."""


class DockerMachine:
    def __init__(self, image: str, files: dict, seconds: int, lifetime: int = 3600):
        if not shutil.which("docker"):
            raise InfrastructureError(
                "Docker is not installed; repository execution is disabled"
            )
        self.identifier = "devmind-run-" + uuid.uuid4().hex
        self.seconds = seconds
        self.closed = False
        command = [
            "docker",
            "run",
            "-d",
            "--rm",
            "--pull=never",
            "--name",
            self.identifier,
            "--label",
            "devmind.execution=true",
            "--network=none",
            "--read-only",
            "--user=65532:65532",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--memory=1g",
            "--memory-swap=1g",
            "--cpus=1",
            "--pids-limit=128",
            "--init",
            "--tmpfs=/workspace:rw,nosuid,size=384m,mode=1777",
            "--tmpfs=/tmp:rw,nosuid,noexec,size=128m,mode=1777",
            "--log-driver=none",
            "--workdir=/workspace",
            "--env=HOME=/tmp",
            "--env=PYTHONDONTWRITEBYTECODE=1",
            image,
            "sleep",
            str(max(1, lifetime)),
        ]
        try:
            outcome, _ = execute(command, deadline=30, limit=4000)
            if outcome.code or outcome.timeout or outcome.overflow:
                raise InfrastructureError(
                    "Docker startup failed; check daemon and trusted image"
                )
            self.invoke({"kind": "initialize", "files": files})
        except BaseException:
            self.dispose()
            raise

    def invoke(self, action: dict) -> dict:
        if self.closed:
            raise InfrastructureError("Execution container is closed")
        outcome, raw = execute(
            [
                "docker",
                "exec",
                "-i",
                self.identifier,
                "python",
                "-I",
                "/opt/computer.py",
            ],
            deadline=self.seconds + 15,
            data=json.dumps(action).encode(),
            limit=48 * 1024 * 1024,
        )
        if outcome.code or outcome.timeout or outcome.overflow:
            self.dispose()
            raise InfrastructureError(
                "Execution transport exceeded its bounds or failed"
            )
        try:
            response = json.loads(raw)
        except ValueError as error:
            raise InfrastructureError(
                "Execution broker returned invalid data"
            ) from error
        if not response["ok"]:
            raise ValueError(response["error"])
        return response["result"]

    def dispose(self) -> None:
        if not self.closed:
            self.closed = True
            execute(["docker", "rm", "-f", self.identifier], deadline=20, limit=4000)
