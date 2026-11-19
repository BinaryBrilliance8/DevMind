"""Bounded subprocess I/O and immutable source materialization."""

import base64
import os
import selectors
import signal
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath

MAX_SOURCE = 32 * 1024 * 1024
MAX_FILES = 8000
IGNORED = {".git", "__pycache__", ".pytest_cache", ".ruff_cache", "node_modules"}


@dataclass
class Outcome:
    code: int
    stdout: str
    stderr: str
    timeout: bool
    overflow: bool

    def json(self) -> dict:
        return asdict(self)


def execute(
    argv: list[str],
    cwd: Path | None = None,
    deadline: float = 60,
    data: bytes = b"",
    limit: int = 65536,
    environment: dict | None = None,
) -> tuple[Outcome, bytes]:
    captured = [bytearray(), bytearray()]
    timeout = overflow = False
    with tempfile.TemporaryFile() as stdin:
        stdin.write(data)
        stdin.seek(0)
        with subprocess.Popen(
            argv,
            cwd=cwd,
            env=environment,
            stdin=stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        ) as child:
            until = time.monotonic() + deadline
            with selectors.DefaultSelector() as selector:
                selector.register(child.stdout, selectors.EVENT_READ, 0)
                selector.register(child.stderr, selectors.EVENT_READ, 1)
                while selector.get_map():
                    if time.monotonic() >= until:
                        timeout = True
                        break
                    for key, _ in selector.select(0.05):
                        chunk = os.read(key.fileobj.fileno(), 32768)
                        if not chunk:
                            selector.unregister(key.fileobj)
                            continue
                        room = limit - sum(map(len, captured))
                        captured[key.data].extend(chunk[:room])
                        if len(chunk) > room:
                            overflow = True
                            break
                    if overflow:
                        break
            if not (timeout or overflow):
                try:
                    child.wait(timeout=max(0.001, until - time.monotonic()))
                except subprocess.TimeoutExpired:
                    timeout = True
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            code = child.wait()
    return Outcome(
        code,
        captured[0].decode(errors="replace"),
        captured[1].decode(errors="replace"),
        timeout,
        overflow,
    ), bytes(captured[0])


def git(
    root: Path, arguments: list[str], data: bytes = b"", limit: int = MAX_SOURCE * 2
) -> bytes:
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": "/nonexistent",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        "LC_ALL": "C",
    }
    result, output = execute(
        [
            "git",
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "safe.directory=" + str(root.resolve()),
            "-c",
            "core.fsmonitor=false",
            "-c",
            "core.attributesFile=/dev/null",
            *arguments,
        ],
        root,
        data=data,
        limit=limit,
        environment=env,
    )
    if result.code or result.timeout or result.overflow:
        raise RuntimeError("Git failed or exceeded the operation budget")
    return output


def safe_name(name: str) -> None:
    path = PurePosixPath(name)
    if (
        not name
        or name == "."
        or path.is_absolute()
        or str(path) != name
        or "\\" in name
        or "\0" in name
        or any(p.casefold() in {"..", ".git"} for p in path.parts)
    ):
        raise ValueError("Invalid repository-relative path")


def check_snapshot(snapshot: dict) -> None:
    total = 0
    canonical = set()
    if len(snapshot) > MAX_FILES:
        raise ValueError("Repository file limit exceeded")
    for name, item in snapshot.items():
        safe_name(name)
        if name.casefold() in canonical:
            raise ValueError("Ambiguous case-insensitive file names")
        canonical.add(name.casefold())
        content = base64.b64decode(item["content"], validate=True)
        total += len(content)
        if total > MAX_SOURCE or item["mode"] not in (420, 493):
            raise ValueError("Repository byte limit or invalid file mode")


def checkout_snapshot(path: Path, ref: str | None) -> tuple[str, dict]:
    sha = (
        git(path, ["rev-parse", "--verify", (ref or "HEAD") + "^{commit}"])
        .decode()
        .strip()
    )
    entries = git(path, ["ls-tree", "-rz", sha]).split(b"\0")
    objects = []
    for entry in filter(None, entries):
        head, name = entry.split(b"\t", 1)
        mode, kind, object_id = head.decode().split()
        name = name.decode()
        safe_name(name)
        if kind != "blob" or mode not in {"100644", "100755"}:
            raise ValueError("Symlinks and Git submodules are not supported")
        if any(p in IGNORED for p in PurePosixPath(name).parts):
            continue
        objects.append((name, mode, object_id))
    if not objects or len(objects) > MAX_FILES:
        raise ValueError("Empty or oversized repository")
    batch = git(
        path,
        ["cat-file", "--batch"],
        "".join(item[2] + "\n" for item in objects).encode(),
        MAX_SOURCE + MAX_FILES * 100,
    )
    position = 0
    snapshot = {}
    for name, mode, object_id in objects:
        end = batch.index(b"\n", position)
        actual, kind, size = batch[position:end].decode().split()
        size = int(size)
        if actual != object_id or kind != "blob":
            raise ValueError("Invalid Git object response")
        position = end + 1
        content = batch[position : position + size]
        if len(content) != size:
            raise ValueError("Truncated Git object")
        position += size + 1
        snapshot[name] = {
            "content": base64.b64encode(content).decode(),
            "mode": 493 if mode == "100755" else 420,
        }
    check_snapshot(snapshot)
    return sha, snapshot


def populate(root: Path, snapshot: dict) -> None:
    check_snapshot(snapshot)
    for name, entry in snapshot.items():
        destination = root / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(base64.b64decode(entry["content"]))
        destination.chmod(entry["mode"])


def diff(original: dict, candidate: dict) -> str:
    """Use a controller-owned index; never trust agent-modified Git metadata."""
    with tempfile.TemporaryDirectory(prefix="devmind-patch-") as temporary:
        root = Path(temporary)
        git(root, ["init", "-q"])
        populate(root, original)
        git(root, ["add", "--all", "--force"])
        tree = git(root, ["write-tree"]).decode().strip()
        for name in original:
            (root / name).unlink()
        for directory in sorted(
            root.rglob("*"), key=lambda p: len(p.parts), reverse=True
        ):
            if (
                ".git" not in directory.parts
                and directory.is_dir()
                and not any(directory.iterdir())
            ):
                directory.rmdir()
        populate(root, candidate)
        git(root, ["add", "--all", "--force"])
        return git(
            root,
            ["diff", "--cached", "--binary", "--no-ext-diff", "--no-textconv", tree],
            limit=4 * 1024 * 1024,
        ).decode()
