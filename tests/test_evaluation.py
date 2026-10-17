import json

import pytest

from synthetic_human.evaluation import compare, distances, read_inputs


def fixture_trace(path, role, interval=0.15, dropped=0):
    # Explicit synthetic test fixture, never shipped as genuine telemetry evidence.
    records = [
        {
            "kind": "recorder.status",
            "enabled": True,
            "recording_role": role,
            "phase": "start",
            "dropped_events": dropped,
        }
    ]
    for index in range(40):
        timestamp = index * interval + 1
        records += [
            {
                "kind": "input.observed",
                "event": "key_down",
                "native_timestamp_ns": int(timestamp * 1e9),
                "press_id": index,
                "is_shortcut": False,
                "repeat": False,
            },
            {
                "kind": "input.observed",
                "event": "key_up",
                "native_timestamp_ns": int((timestamp + 0.05) * 1e9),
                "press_id": index,
            },
        ]
    records.append({"kind": "recorder.status", "enabled": True, "recording_role": role, "phase": "stop"})
    path.write_text("".join(json.dumps(row) + "\n" for row in records))


def test_empirical_distances_have_correct_units():
    assert distances([0, 1], [0, 1]) == {"ks": 0, "wasserstein": 0}
    assert distances([0, 0], [2, 2]) == {"ks": 1, "wasserstein": 2}
    assert distances([], [1])["ks"] is None


def test_observed_holds_and_baseline_comparison(tmp_path):
    agent, human = tmp_path / "agent.jsonl", tmp_path / "human.jsonl"
    fixture_trace(agent, "agent", 0.15)
    fixture_trace(human, "human", 0.20)
    observation = read_inputs(agent)
    assert observation["statistics"]["key_hold_seconds"]["median"] == pytest.approx(0.05)
    result = compare(agent, human)
    assert result["status"] == "descriptive_comparison"
    assert result["distances"]["inter_key_seconds"]["wasserstein"] == pytest.approx(0.05)
    assert result["weighted_score"] is None


def test_missing_permission_or_dropped_events_cannot_be_scored(tmp_path):
    agent, human = tmp_path / "agent.jsonl", tmp_path / "human.jsonl"
    agent.write_text(
        json.dumps({"kind": "recorder.status", "enabled": False, "recording_role": "agent"}) + "\n"
    )
    fixture_trace(human, "human")
    result = compare(agent, human)
    assert result["status"] == "insufficient_evidence"
    assert result["distances"]["inter_key_seconds"]["ks"] is None
    fixture_trace(agent, "agent", dropped=10)
    assert compare(agent, human)["status"] == "insufficient_evidence"


def test_same_role_recordings_are_not_a_human_baseline(tmp_path):
    agent, other = tmp_path / "agent.jsonl", tmp_path / "other.jsonl"
    fixture_trace(agent, "agent")
    fixture_trace(other, "agent")
    assert compare(agent, other)["status"] == "insufficient_evidence"


def test_live_recording_is_not_a_completed_baseline_even_with_many_samples(tmp_path):
    agent, human = tmp_path / "agent.jsonl", tmp_path / "human.jsonl"
    fixture_trace(agent, "agent")
    fixture_trace(human, "human")
    human.write_text("\n".join(human.read_text().splitlines()[:-1]) + "\n")
    result = compare(agent, human)
    assert result["human"]["statistics"]["inter_key_seconds"]["count"] == 39
    assert not result["human"]["coverage"]["completed"]
    assert result["status"] == "insufficient_evidence"
    assert "recording_not_closed" in result["insufficient_evidence_reasons"]["human"]
    assert all(value == {"ks": None, "wasserstein": None} for value in result["distances"].values())


def test_truncated_live_json_is_reported_instead_of_crashing_or_scoring(tmp_path):
    agent, human = tmp_path / "agent.jsonl", tmp_path / "human.jsonl"
    fixture_trace(agent, "agent")
    fixture_trace(human, "human")
    with human.open("a") as stream:
        stream.write('{"kind":"input.observed"')
    result = compare(agent, human)
    assert result["status"] == "insufficient_evidence"
    assert result["human"]["coverage"]["incomplete_lines"] == 1


def test_completed_restarts_are_allowed_but_missing_stop_cannot_be_hidden(tmp_path):
    path = tmp_path / "agent.jsonl"
    fixture_trace(path, "agent")
    one_session = path.read_text()
    path.write_text(one_session + one_session)
    observation = read_inputs(path)
    assert observation["coverage"]["completed"]
    assert observation["coverage"]["sessions_started"] == 2
    assert observation["statistics"]["key_hold_seconds"]["count"] == 80
    path.write_text("\n".join(one_session.splitlines()[:-1]) + "\n" + one_session)
    observation = read_inputs(path)
    assert not observation["coverage"]["completed"]
    assert observation["coverage"]["lifecycle_errors"] == 1


def test_auto_repeat_is_reported_separately_from_physical_corrections(tmp_path):
    path = tmp_path / "human.jsonl"
    fixture_trace(path, "human")
    records = [json.loads(line) for line in path.read_text().splitlines()]
    records[1]["is_correction"] = True
    repeat = {**records[1], "repeat": True, "native_timestamp_ns": 1_020_000_000}
    records.insert(2, repeat)
    path.write_text("".join(json.dumps(row) + "\n" for row in records))
    observation = read_inputs(path)
    assert observation["coverage"]["completed"]
    assert observation["event_counts"]["repeat_key_downs"] == 1
    assert observation["event_counts"]["corrections"] == 2
    assert observation["event_counts"]["nonrepeat_corrections"] == 1
    assert observation["statistics"]["key_hold_seconds"]["count"] == 40


def test_shortcut_resets_typing_but_does_not_hide_real_input_silence(tmp_path):
    path = tmp_path / "agent.jsonl"
    fixture_trace(path, "agent")
    records = [json.loads(line) for line in path.read_text().splitlines()]
    records[1]["is_shortcut"] = True
    for record in records[3:]:
        if record.get("native_timestamp_ns"):
            record["native_timestamp_ns"] += 3_000_000_000
    path.write_text("".join(json.dumps(row) + "\n" for row in records))
    observation = read_inputs(path)
    assert observation["statistics"]["idle_seconds"]["count"] == 0
    assert observation["statistics"]["input_silence_seconds"]["count"] == 1
    assert observation["statistics"]["input_silence_seconds"]["median"] == pytest.approx(3.1)
