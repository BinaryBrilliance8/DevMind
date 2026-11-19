"""Lease-fenced orchestration with independent verification and human review."""

import hashlib
import json
import logging
import threading
import time
import uuid
from collections.abc import Callable

from devmind.config import Config
from devmind.database import Repository
from devmind.isolation import DockerMachine, InfrastructureError
from devmind.model import PROMPT_VERSION, Gateway, initial_messages
from devmind.operations import checkout_snapshot, diff

log = logging.getLogger("devmind.worker")


class RunStopped(RuntimeError):
    """Cancellation, expired lease or a resource limit stopped the attempt."""


class Runner:
    def __init__(
        self,
        config: Config,
        repository: Repository,
        model_factory: Callable = Gateway,
        machine_factory: Callable = DockerMachine,
        shutdown: threading.Event | None = None,
    ):
        self.shutdown = shutdown or threading.Event()
        self.config, self.repository = config, repository
        self.model_factory, self.machine_factory = model_factory, machine_factory

    def once(self) -> bool:
        if self.shutdown.is_set():
            return False
        owner = str(uuid.uuid4())
        job = self.repository.claim(owner, self.config.lease_seconds)
        if job is None:
            return False
        identifier = job["id"]
        stop = threading.Event()
        lost = threading.Event()

        started = time.monotonic()
        machine = None
        patch = ""
        model = None
        original = None
        provenance = {"model": self.config.model, "prompt": PROMPT_VERSION}
        boxes = []
        boxes_lock = threading.Lock()

        def heartbeat() -> None:
            while not stop.wait(min(1.0, self.config.lease_seconds / 3)):
                try:
                    elapsed = time.monotonic() - started
                    if self.shutdown.is_set() or elapsed >= self.config.seconds:
                        lost.set()
                        self.repository.complete(
                            identifier,
                            owner,
                            "failed",
                            provenance
                            | {
                                "reason": "Worker shutting down"
                                if self.shutdown.is_set()
                                else "Run wall-clock budget exceeded",
                                "duration": round(elapsed, 3),
                                "tokens": model.tokens if model else 0,
                            },
                        )
                    elif not self.repository.alive(
                        identifier, owner, self.config.lease_seconds
                    ):
                        lost.set()
                except Exception:
                    lost.set()
                if lost.is_set():
                    with boxes_lock:
                        current = list(boxes)
                    for box in current:
                        try:
                            box.dispose()
                        except Exception:
                            log.error("run=%s watchdog_cleanup_failed=true", identifier)
                    return

        thread = threading.Thread(target=heartbeat, daemon=True)
        thread.start()

        def guard() -> None:
            if self.shutdown.is_set():
                raise RunStopped("Worker shutting down")
            if lost.is_set() or not self.repository.alive(identifier, owner):
                raise RunStopped("Run cancelled or worker lease lost")
            if time.monotonic() - started > self.config.seconds:
                raise RunStopped("Run scheduling budget exceeded")
            if model is not None and model.tokens >= self.config.token_limit:
                raise RunStopped("Token budget exceeded")

        def new_machine(files: dict):
            seconds = max(1, int(self.config.seconds - (time.monotonic() - started)))
            if self.machine_factory is DockerMachine:
                box = DockerMachine(
                    project.image, files, self.config.command_seconds, lifetime=seconds
                )
            else:
                box = self.machine_factory(
                    project.image, files, self.config.command_seconds
                )
            with boxes_lock:
                boxes.append(box)
            try:
                guard()
            except BaseException:
                box.dispose()
                raise
            return box

        def emit(kind: str, payload: dict, phase: str | None = None) -> None:
            if not self.repository.emit(identifier, owner, kind, payload, phase):
                raise RunStopped("Worker no longer owns this run")
            log.info("run=%s event=%s", identifier, kind)

        try:
            model = self.model_factory(self.config)
            project = self.config.project(job["request"]["project"])
            if not self.config.model:
                raise InfrastructureError(
                    "Configure DEVMIND_MODEL and a running model endpoint"
                )
            guard()
            sha, original = checkout_snapshot(
                project.checkout, job["request"]["commit"]
            )
            provenance |= {
                "commit": sha,
                "image": project.image,
                "test_command": project.verify,
                "protected": project.protected,
                "snapshot_sha256": hashlib.sha256(
                    json.dumps(original, sort_keys=True).encode()
                ).hexdigest(),
            }
            emit("source", provenance | {"files": len(original)}, "preparing")
            machine = new_machine(original)
            baseline = machine.invoke(
                {
                    "kind": "command",
                    "argv": project.verify,
                    "seconds": self.config.command_seconds,
                }
            )
            emit("baseline", baseline, "planning")
            messages = initial_messages(
                job["request"]["issue"],
                {
                    "protected": project.protected,
                    "verification_argv": project.verify,
                    "commit": sha,
                },
            )
            messages.append(
                {
                    "role": "user",
                    "content": "Baseline test evidence: " + json.dumps(baseline),
                }
            )
            planned = False
            inspected = set()
            for step in range(1, self.config.steps + 1):
                guard()
                while (
                    len(json.dumps(messages)) > self.config.context_chars
                    and len(messages) > 5
                ):
                    del messages[3:5]
                if len(json.dumps(messages)) > self.config.context_chars:
                    raise RunStopped("Context budget exceeded")
                try:
                    decision = model.decide(messages)
                except (ValueError, KeyError, TypeError, IndexError):
                    emit("invalid_action", {"step": step})
                    messages.append(
                        {
                            "role": "user",
                            "content": "Invalid JSON action. Follow the action schema.",
                        }
                    )
                    continue
                guard()
                action = decision.model_dump()
                emit(
                    "action",
                    {"step": step, "action": action},
                    "running" if planned else "planning",
                )
                messages.append({"role": "assistant", "content": json.dumps(action)})
                try:
                    kind = action["kind"]
                    if kind == "plan":
                        planned = True
                        observation = {"plan_recorded": action["steps"]}
                    elif not planned and kind not in {"locate", "read"}:
                        observation = {
                            "error": "Submit a plan before modifying or executing code"
                        }
                    elif (
                        kind == "replace"
                        and action["path"] in original
                        and action["path"] not in inspected
                    ):
                        observation = {"error": "Read this file before editing it"}
                    elif kind == "verify":
                        observation = machine.invoke(
                            {
                                "kind": "command",
                                "argv": project.verify,
                                "seconds": self.config.command_seconds,
                            }
                        )
                        emit("test", observation)
                    elif kind == "submit":
                        candidate = machine.invoke({"kind": "snapshot"})["files"]
                        patch = diff(original, candidate)
                        changes = [
                            name
                            for name in original.keys() | candidate.keys()
                            if original.get(name) != candidate.get(name)
                        ]
                        protected = [
                            name
                            for name in changes
                            if any(
                                name == p.rstrip("/")
                                or name.startswith(p.rstrip("/") + "/")
                                for p in project.protected
                            )
                        ]
                        if protected or not patch:
                            observation = {
                                "error": "Protected paths changed"
                                if protected
                                else "No patch to review",
                                "paths": protected,
                            }
                        else:
                            guard()
                            emit(
                                "verification_started",
                                {"changed_files": changes},
                                "verifying",
                            )
                            verifier = new_machine(candidate)
                            try:
                                verified = verifier.invoke(
                                    {
                                        "kind": "command",
                                        "argv": project.verify,
                                        "seconds": self.config.command_seconds,
                                    }
                                )
                            finally:
                                verifier.dispose()
                            emit("verification", verified)
                            guard()
                            if (
                                verified["code"] == 0
                                and not verified["timeout"]
                                and not verified["overflow"]
                            ):
                                result = provenance | {
                                    "summary": action["summary"],
                                    "steps": step,
                                    "tokens": model.tokens,
                                    "duration": round(time.monotonic() - started, 3),
                                    "verification": verified,
                                    "baseline": baseline,
                                    "changed_files": changes,
                                    "claim": "Tests passed; human review required",
                                }
                                self.repository.complete(
                                    identifier, owner, "review", result, patch
                                )
                                return True
                            observation = {
                                "error": "Verification failed; revise the patch",
                                "tests": verified,
                            }
                    else:
                        if kind == "command":
                            action["seconds"] = self.config.command_seconds
                        observation = machine.invoke(action)
                        if kind == "read":
                            inspected.add(action["path"])
                except (ValueError, KeyError, OSError) as error:
                    observation = {"error": str(error)[:1200]}
                emit("observation", {"step": step, "observation": observation})
                messages.append({"role": "user", "content": json.dumps(observation)})
            raise RunStopped("Maximum action count reached")
        except Exception as error:
            # Preserve the latest candidate when an action budget is exhausted.
            # Cancellation and lease loss still fence all artifact writes.
            if machine is not None and original is not None and not lost.is_set():
                try:
                    if self.repository.alive(identifier, owner):
                        patch = diff(
                            original, machine.invoke({"kind": "snapshot"})["files"]
                        )
                except Exception:
                    log.warning("run=%s final_snapshot_unavailable=true", identifier)
            # Source-bearing exceptions are not copied to public process logs.
            reason = (
                str(error)
                if isinstance(error, (InfrastructureError, RunStopped))
                else (f"{type(error).__name__}: inspect configuration and run events")
            )
            self.repository.complete(
                identifier,
                owner,
                "failed",
                provenance
                | {
                    "reason": reason,
                    "duration": round(time.monotonic() - started, 3),
                    "tokens": model.tokens if model else 0,
                },
                patch,
            )
            log.error("run=%s failure=%s", identifier, type(error).__name__)
        finally:
            stop.set()
            thread.join(timeout=2)
            if machine:
                try:
                    machine.dispose()
                except Exception:
                    log.error("run=%s cleanup_failed=true", identifier)
        return True
