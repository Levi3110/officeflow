import hashlib
import json

import pytest

from synthetic_human.reporting import build_report, resources


def trace(directory, role, interval=0.15):
    """Explicit synthetic fixture for report tests, never a published baseline."""
    directory.mkdir()
    rows = [
        {
            "kind": "recorder.status",
            "phase": "start",
            "enabled": True,
            "recording_role": role,
            "timestamp": 100.0,
        }
    ]
    for index in range(40):
        native = int((1 + index * interval) * 1e9)
        rows.extend(
            [
                {
                    "kind": "input.observed",
                    "event": "key_down",
                    "press_id": index,
                    "native_timestamp_ns": native,
                },
                {
                    "kind": "input.observed",
                    "event": "key_up",
                    "press_id": index,
                    "native_timestamp_ns": native + 50_000_000,
                },
            ]
        )
    rows.append(
        {
            "kind": "recorder.status",
            "phase": "stop",
            "enabled": True,
            "recording_role": role,
            "timestamp": 110.0,
        }
    )
    (directory / "inputs.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
    return directory


def test_archive_preserves_sources_and_reports_unscored_uncertainty(tmp_path):
    agent, human = trace(tmp_path / "agent-test", "agent"), trace(tmp_path / "person-test", "human", 0.2)
    originals = {
        role: (path / "inputs.jsonl").read_bytes() for role, path in (("agent", agent), ("human", human))
    }
    output = tmp_path / "report"
    manifest = build_report(agent, human, output, archive_raw=True, study_notes=["Test protocol note."])
    for role, path in (("agent", agent), ("human", human)):
        archived = (output / "raw" / role / "inputs.jsonl").read_bytes()
        assert archived == originals[role] == (path / "inputs.jsonl").read_bytes()
        assert (
            manifest["inputs"][role]["files"]["inputs.jsonl"]["sha256"]
            == hashlib.sha256(archived).hexdigest()
        )
        assert manifest["inputs"][role]["recording_duration_seconds"] == 10
    result = json.loads((output / "comparison.json").read_text())
    assert result["status"] == "descriptive_comparison"
    assert result["weighted_score"] is None
    assert result["distances"]["inter_key_seconds"]["wasserstein"] == pytest.approx(0.05)
    report = (output / "report.md").read_text()
    assert "Human behaviour varies across people" in report
    assert "not independent participants" in report
    assert "agent-test vs person-test" in report
    assert "Test protocol note." in report
    assert "human-05" not in report
    assert "four agent and five human" not in report
    assert "Raw snapshots are included in this local report folder." in report
    assert b"\r" not in (output / "summary.csv").read_bytes()
    csv_rows = (output / "summary.csv").read_text().splitlines()
    assert csv_rows[0].startswith("feature,unit,agent_count")
    assert "inter_key_seconds,ms,39,39" in csv_rows[1]


def test_aggregate_report_does_not_copy_raw_or_overwrite(tmp_path):
    agent, human = trace(tmp_path / "agent", "agent"), trace(tmp_path / "human", "human")
    output = tmp_path / "report"
    manifest = build_report(agent, human, output)
    assert not manifest["raw_archived"]
    assert not (output / "raw").exists()
    assert "no raw snapshots were copied" in (output / "report.md").read_text()
    sentinel = (output / "manifest.json").read_bytes()
    with pytest.raises(FileExistsError):
        build_report(agent, human, output)
    assert (output / "manifest.json").read_bytes() == sentinel


def test_active_capture_cannot_be_archived_as_benchmark(tmp_path):
    agent, human = trace(tmp_path / "agent", "agent"), trace(tmp_path / "human", "human")
    path = human / "inputs.jsonl"
    path.write_text("\n".join(path.read_text().splitlines()[:-1]) + "\n")
    with pytest.raises(ValueError, match="recording_not_closed"):
        build_report(agent, human, tmp_path / "invalid", archive_raw=True)
    assert not (tmp_path / "invalid").exists()


def test_resource_summary_excludes_first_cpu_sample_and_labels_foreground(tmp_path):
    rows = [
        {
            "kind": "os.sample",
            "timestamp": 1,
            "foreground": {"name": "Code"},
            "processes": [
                {"runner": True, "rss_bytes": 2 * 1024**2, "cpu_percent": 99, "cpu_first_sample": True},
                {"runner": False, "rss_bytes": 4 * 1024**2, "cpu_percent": 88, "cpu_first_sample": True},
            ],
        },
        {
            "kind": "os.sample",
            "timestamp": 2,
            "foreground": {"name": "Code"},
            "processes": [
                {"runner": True, "rss_bytes": 3 * 1024**2, "cpu_percent": 7},
                {"runner": False, "rss_bytes": 5 * 1024**2, "cpu_percent": 12},
            ],
        },
    ]
    result = resources("\n".join(json.dumps(row) for row in rows).encode())
    assert result["statistics"]["runner_cpu_percent"]["count"] == 1
    assert result["statistics"]["runner_cpu_percent"]["peak"] == 7
    assert result["statistics"]["apps_cpu_percent"]["peak"] == 12
    assert result["statistics"]["runner_rss_mib"]["count"] == 2
    assert result["statistics"]["runner_rss_mib"]["peak"] == 3
    assert result["foreground_samples_diagnostic_only"] == {"Code": 2}
    assert any("stale" in note for note in result["limitations"])
