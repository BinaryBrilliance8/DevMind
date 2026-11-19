import importlib.util
import json
from pathlib import Path


def test_live_repair_preflight_never_falls_back_to_host(
    tmp_path, config, request_body, monkeypatch
):
    path = Path(__file__).parents[1] / "research/paper_revision/live_repair.py"
    spec = importlib.util.spec_from_file_location("live_repair_study", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "load", lambda: config)
    monkeypatch.setattr(
        module,
        "inspect",
        lambda *_: {
            "ready": False,
            "checks": {"docker": {"ready": False}},
        },
    )

    def forbidden(*_):
        raise AssertionError("Runner must not start without execution dependencies")

    monkeypatch.setattr(module, "Runner", forbidden)
    tasks = tmp_path / "tasks.jsonl"
    tasks.write_text(request_body.model_dump_json() + "\n")
    output = tmp_path / "run"
    assert module.run(output, f"sqlite:///{tmp_path}/evaluation.db", tasks) == 2
    assert not json.loads((output / "preflight.json").read_text())["ready"]
    assert not (output / "summary.json").exists()
