import base64
import sys

import pytest
from devmind.contracts import DECISION
from devmind.executor import Computer
from devmind.operations import (
    check_snapshot,
    checkout_snapshot,
    diff,
    execute,
    git,
    populate,
    safe_name,
)


@pytest.mark.parametrize(
    "name", ["../file", "/etc/passwd", ".git/config", ".GIT/config", "a//b", "a/./b"]
)
def test_unsafe_paths(name):
    with pytest.raises(ValueError):
        safe_name(name)


def test_collision_and_symlink(tmp_path):
    item = {"content": "", "mode": 420}
    with pytest.raises(ValueError):
        check_snapshot({"File": item, "file": item})
    (tmp_path / "outside").symlink_to("/tmp")
    with pytest.raises(ValueError):
        Computer(tmp_path).resolve("outside/file")


def test_process_limits_and_separated_output():
    result, raw = execute(
        [
            sys.executable,
            "-c",
            "import sys;print('ok');print('warning',file=sys.stderr)",
        ]
    )
    assert raw == b"ok\n" and result.stderr == "warning\n"
    result, _ = execute(
        [sys.executable, "-c", "import time;time.sleep(5)"], deadline=0.05
    )
    assert result.timeout
    result, _ = execute([sys.executable, "-c", "print('x'*100000)"], limit=1000)
    assert result.overflow and len(result.stdout) <= 1000


def test_ingestion_and_patch(config, source, tmp_path):
    root = config.projects[0].checkout
    (root / "cache.py").write_text("uncommitted changes")
    sha, committed = checkout_snapshot(root, None)
    assert len(sha) == 40 and committed == source
    candidate = dict(committed)
    original = base64.b64decode(candidate["cache.py"]["content"]).decode()
    candidate["cache.py"] = {
        "content": base64.b64encode(
            original.replace("self.clock() > expiry", "self.clock() >= expiry").encode()
        ).decode(),
        "mode": 420,
    }
    candidate["binary.dat"] = {
        "content": base64.b64encode(b"\0\1\2").decode(),
        "mode": 493,
    }
    patch = diff(committed, candidate)
    clean = tmp_path / "apply"
    clean.mkdir()
    git(clean, ["init", "-q"])
    populate(clean, committed)
    git(clean, ["apply", "--check", "-"], patch.encode())
    git(clean, ["apply", "-"], patch.encode())
    assert (clean / "binary.dat").read_bytes() == b"\0\1\2"
    assert (clean / "binary.dat").stat().st_mode & 0o111


def test_aci_read_search_and_edits(tmp_path, source):
    computer = Computer(tmp_path)
    computer.invoke({"kind": "initialize", "files": source})
    assert computer.invoke({"kind": "locate", "query": "expiry"})["matches"]
    assert "TTLCache" in computer.invoke({"kind": "read", "path": "cache.py"})["text"]
    with pytest.raises(ValueError):
        computer.invoke(
            {
                "kind": "replace",
                "path": "cache.py",
                "expected": "",
                "replacement": "bad",
            }
        )
    computer.invoke(
        {
            "kind": "replace",
            "path": "cache.py",
            "expected": "self.clock() > expiry",
            "replacement": "self.clock() >= expiry",
        }
    )
    with pytest.raises(ValueError):
        computer.invoke(
            {
                "kind": "replace",
                "path": "cache.py",
                "expected": "missing",
                "replacement": "bad",
            }
        )


def test_action_schema_rejects_unlisted_capabilities():
    for value in [
        {"kind": "host_shell"},
        {"kind": "command", "argv": [""]},
        {"kind": "verify", "argv": ["true"]},
    ]:
        with pytest.raises(ValueError):
            DECISION.validate_python(value)


def test_dot_is_rejected_at_every_snapshot_entrypoint(tmp_path):
    with pytest.raises(ValueError, match="Invalid repository-relative path"):
        safe_name(".")
    with pytest.raises(ValueError, match="Invalid repository-relative path"):
        check_snapshot({".": {"content": "", "mode": 420}})
    with pytest.raises(ValueError, match="Invalid repository-relative path"):
        Computer(tmp_path).resolve(".")
