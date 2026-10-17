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
