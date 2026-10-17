import json
import sys
from types import SimpleNamespace

from synthetic_human.input_recorder import InputRecorder


def test_missing_permission_produces_status_not_fabricated_input(tmp_path, monkeypatch):
    monkeypatch.setattr("synthetic_human.input_recorder.platform.system", lambda: "Darwin")
    monkeypatch.setitem(sys.modules, "Quartz", SimpleNamespace(CGPreflightListenEventAccess=lambda: False))
    path = tmp_path / "inputs.jsonl"
    recorder = InputRecorder(path)
    assert recorder.start() is False
    records = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(records) == 1
    assert records[0]["kind"] == "recorder.status"
    assert records[0]["enabled"] is False
    assert "permission" in records[0]["reason"]
    recorder.stop()
