import json

import pytest

from synthetic_human.fixture import Catalog
from synthetic_human.rubric import core_summary, entropy, evaluate, process_profile, render, save
from synthetic_human.telemetry import export_audit, metrics
from synthetic_human.workflow import Workflow


def sample_data():
    # Explicit synthetic fixture. Never published as OS/human evidence.
    return [
        {
            "kind": "os.sample",
            "source": "psutil",
            "backend": "simulation",
            "timestamp": index,
            "monotonic": index / 2,
            "processes": [
                {
                    "pid": 1,
                    "name": "Python",
                    "runner": True,
                    "cpu_percent": 99 if index == 0 else 50,
                    "cpu_first_sample": index == 0,
                    "rss_bytes": 1024**2,
                    "threads": 1,
                    "io": None,
                },
                {
                    "pid": 2,
                    "name": "Chrome",
                    "runner": False,
                    "cpu_percent": 0,
                    "cpu_first_sample": index == 0,
                    "rss_bytes": 2 * 1024**2,
                    "threads": 3,
                    "io": {"read_bytes": 1} if index == 0 else None,
                },
            ],
        }
        for index in range(2)
    ]


def encoded(rows):
    return ("\n".join(json.dumps(row) for row in rows) + "\n").encode()


def core_data():
    return {
        "kind": "simulation.core.benchmark",
        "platform": "test fixture",
        "python": "test",
        "runs": [
            {
                "status": status,
                "workflow_seconds": 0.2,
                "workflow_cpu_seconds": 0.1,
                "maxrss_bytes": 1024**2,
                "import_seconds": 0.1,
                "export_seconds": 0.01,
                "input_dispatches": 100,
                "actions": 22,
                "audit_bytes": 200,
                "database_bytes": 300,
            }
            for status in ("completed", "failed", "completed")
        ],
    }


def test_process_cpu_estimate_uses_elapsed_time_and_excludes_initial_sample():
    result = process_profile(encoded(sample_data()))
    assert result["runner_cpu_seconds_estimate"] == pytest.approx(0.25)
    assert result["runner_cpu_estimate_covered_seconds"] == pytest.approx(0.5)
    assert result["statistics"]["runner_cpu_percent"]["peak"] == 50
    assert result["family_sample_presence"] == {"runner": 2, "Chrome": 2}
    assert result["io_available_rows"] == 1
    assert result["process_rows"] == 4
    assert result["app_threads_per_sample"]["median"] == 3


def test_core_failures_remain_in_denominator_and_simulation_scope():
    result = core_summary(core_data())
    assert result["completed_trials"] == 2
    assert result["trial_count"] == 3
    assert "No GUI" in result["scope"]
    with pytest.raises(ValueError):
        core_summary({"kind": "native", "runs": [1]})


def test_observed_entropy_is_fixed_bin_descriptive_and_missing_is_not_zero():
    assert entropy([]) is None
    assert entropy([0.01] * 10) == 0
    assert entropy([0.01, 0.06]) == 1


async def test_four_dimensions_keep_weights_and_never_promote_simulation(rig, tmp_path):
    rig.store.put("settings", rig.settings.model_dump())
    with Catalog() as catalog:
        assert (await Workflow(rig, catalog.url).run())["status"] == "completed"
    telemetry = rig.directory / "telemetry.jsonl"
    telemetry.write_bytes(encoded(sample_data()))
    summary = metrics(rig.store, telemetry)
    # Deliberately misleading saved claim: fresh assessment must still win.
    summary.update(backend="macos", real_desktop_verified=True)
    (rig.directory / "metrics.json").write_text(json.dumps(summary))
    export_audit(rig.store, rig.directory / "audit.jsonl")
    human = tmp_path / "human"
    human.mkdir()
    (human / "telemetry.jsonl").write_bytes(encoded(sample_data()))
    for directory, role in ((rig.directory, "agent"), (human, "human")):
        rows = [{"kind": "recorder.status", "phase": "start", "recording_role": role, "enabled": True}]
        for index in range(40):
            rows += [
                {
                    "kind": "input.observed",
                    "event": "key_down",
                    "native_timestamp_ns": 1_000_000_000 + index * 150_000_000,
                },
                {
                    "kind": "input.observed",
                    "event": "key_up",
                    "native_timestamp_ns": 1_050_000_000 + index * 150_000_000,
                },
            ]
        rows.append({"kind": "recorder.status", "phase": "stop", "recording_role": role, "enabled": True})
        (directory / "inputs.jsonl").write_bytes(encoded(rows))
    core = tmp_path / "core.json"
    core.write_text(json.dumps(core_data()))
    result = evaluate(rig.directory, human, core)
    assert not result["native_verified"]
    dimensions = result["dimensions"]
    assert [row["weight"] for row in dimensions] == [0.3, 0.3, 0.2, 0.2]
    assert dimensions[2]["priority"] == "Secondary"
    assert dimensions[3]["priority"] == "Primary"
    assert all(row["score_0_100"] is None and row["weighted_points"] is None for row in dimensions)
    assert result["weighted_score"] is None
    assert dimensions[2]["status"] == "native_workflow_not_verified"
    assert dimensions[0]["status"] == "insufficient_native_process_evidence"
    report = render(result)
    assert "Unvalidated run diagnostics (not native evidence)" in report
    assert "### Selected real desktop run" not in report
    assert "not a universal human standard" in report
    assert "Weighted score: unassigned" in report
    output = tmp_path / "rubric-report"
    save(result, output)
    assert (output / "rubric.csv").read_text().count("\n") == 5
    assert not list(output.glob("*.jsonl"))
    with pytest.raises(FileExistsError):
        save(result, output)
