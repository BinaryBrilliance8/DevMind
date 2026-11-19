"""Dependency-free ACI broker installed into the read-only execution image."""

import base64
import json
import os
import sys
from pathlib import Path

from devmind.operations import (
    IGNORED,
    MAX_FILES,
    MAX_SOURCE,
    execute,
    git,
    populate,
    safe_name,
)


class Computer:
    def __init__(self, directory: Path):
        self.root = directory.resolve()

    def resolve(self, name: str) -> Path:
        safe_name(name)
        target = self.root / name
        if not target.resolve().is_relative_to(self.root):
            raise ValueError("Path leaves repository")
        probe = target
        while probe != self.root:
            if probe.is_symlink():
                raise ValueError("Symlink access denied")
            probe = probe.parent
        return target

    def snapshot(self) -> dict:
        result = {}
        total = 0
        for parent, dirs, names in os.walk(self.root, followlinks=False):
            dirs[:] = sorted(d for d in dirs if d not in IGNORED)
            for name in sorted(names):
                path = Path(parent) / name
                relative = path.relative_to(self.root).as_posix()
                self.resolve(relative)
                if not path.is_file():
                    raise ValueError("Non-regular file in workspace")
                total += path.stat().st_size
                if total > MAX_SOURCE or len(result) >= MAX_FILES:
                    raise ValueError("Workspace exceeds file or byte limit")
                result[relative] = {
                    "content": base64.b64encode(path.read_bytes()).decode(),
                    "mode": 493 if path.stat().st_mode & 0o111 else 420,
                }
        return result

    def invoke(self, action: dict) -> dict:
        kind = action["kind"]
        if kind == "initialize":
            populate(self.root, action["files"])
            git(self.root, ["init", "-q"])
            git(self.root, ["add", "--all", "--force"])
            git(
                self.root,
                [
                    "-c",
                    "user.name=DevMind",
                    "-c",
                    "user.email=agent@example.invalid",
                    "commit",
                    "-qm",
                    "isolated baseline",
                ],
            )
            return {"initialized": True}
        if kind == "snapshot":
            return {"files": self.snapshot()}
        if kind == "locate":
            query = action.get("query", "")
            matches = []
            for name, item in self.snapshot().items():
                if not query:
                    matches.append({"path": name})
                else:
                    content = base64.b64decode(item["content"]).decode(errors="replace")
                    for line, text in enumerate(content.splitlines(), 1):
                        if query in text:
                            matches.append(
                                {"path": name, "line": line, "text": text[:240]}
                            )
                        if len(matches) >= 120:
                            break
                if len(matches) >= 120:
                    break
            return {"matches": matches, "limit": 120}
        if kind == "read":
            target = self.resolve(action["path"])
            if target.stat().st_size > 1024 * 1024:
                raise ValueError("File too large for text reader")
            first = action.get("first_line", 1)
            count = action.get("line_count", 120)
            if first < 1 or not 1 <= count <= 300:
                raise ValueError("Invalid line window")
            lines = target.read_text().splitlines()
            return {
                "path": action["path"],
                "total_lines": len(lines),
                "text": "\n".join(
                    f"{index + 1}: {text}"
                    for index, text in enumerate(lines)
                    if first - 1 <= index < first + count - 1
                )[:30000],
            }
        if kind == "replace":
            target = self.resolve(action["path"])
            expected, replacement = action["expected"], action["replacement"]
            if not expected:
                if target.exists():
                    raise ValueError("Use expected text to modify an existing file")
                content = replacement
            else:
                if target.stat().st_size > 1024 * 1024:
                    raise ValueError("File exceeds edit budget")
                content = target.read_text()
                if content.count(expected) != 1:
                    raise ValueError(
                        "Expected text must match once; read the file again"
                    )
                content = content.replace(expected, replacement, 1)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
            return {"edited": action["path"]}
        if kind == "command":
            outcome, _ = execute(
                action["argv"],
                self.root,
                deadline=min(180, action.get("seconds", 90)),
                limit=48000,
            )
            return outcome.json()
        raise ValueError("Unsupported computer action")


def main() -> None:
    try:
        action = json.loads(sys.stdin.buffer.read(48 * 1024 * 1024))
        result = Computer(Path("/workspace")).invoke(action)
        print(json.dumps({"ok": True, "result": result}))
    except Exception as error:
        print(
            json.dumps(
                {"ok": False, "error": f"{type(error).__name__}: {str(error)[:500]}"}
            )
        )


if __name__ == "__main__":
    main()
