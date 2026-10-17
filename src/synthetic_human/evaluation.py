"""Descriptive comparison of independently observed inputs, without an invented score."""

from __future__ import annotations

import json
import math
import statistics
from collections import Counter


def distribution(values):
    if not values:
        return {"count": 0, "mean": None, "median": None, "p95": None, "cv": None}
    values = sorted(values)
    mean = statistics.fmean(values)
    return {
        "count": len(values),
        "mean": mean,
        "median": statistics.median(values),
        "p95": values[min(len(values) - 1, math.ceil(len(values) * 0.95) - 1)],
        "cv": statistics.pstdev(values) / mean if mean else None,
    }


def distances(left, right):
    """Exact empirical KS and 1-D Wasserstein using a merged CDF sweep; O(n log n)."""
    if not left or not right:
        return {"ks": None, "wasserstein": None}
    a, b = sorted(left), sorted(right)
    i = j = 0
    previous = min(a[0], b[0])
    ks = area = 0.0
    while i < len(a) or j < len(b):
        point = min(a[i] if i < len(a) else math.inf, b[j] if j < len(b) else math.inf)
        area += abs(i / len(a) - j / len(b)) * (point - previous)
        while i < len(a) and a[i] == point:
            i += 1
        while j < len(b) and b[j] == point:
            j += 1
        ks = max(ks, abs(i / len(a) - j / len(b)))
        previous = point
    return {"ks": ks, "wasserstein": area}


def read_inputs(path):
    intervals, holds, pauses, speeds, silences = [], [], [], [], []
    downs = {}
    previous_key = previous_move = None
    previous_input = None
    counts = Counter()
    coverage = {
        "enabled": False,
        "completed": False,
        "sessions_started": 0,
        "sessions_stopped": 0,
        "lifecycle_errors": 0,
        "outside_session_events": 0,
        "incomplete_lines": 0,
        "gaps": 0,
        "errors": 0,
        "dropped_events": 0,
        "invalid_timestamps": 0,
    }
    session_open = False
    roles = set()
    last_native = 0
    for line in path.open():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            coverage["incomplete_lines"] += 1
            continue
        kind = event.get("kind")
        if kind == "recorder.status":
            if event.get("recording_role"):
                roles.add(event["recording_role"])
            if event.get("phase") == "start":
                coverage["sessions_started"] += 1
                coverage["lifecycle_errors"] += session_open
                session_open = True
                previous_key = previous_move = None
                previous_input = None
                last_native = 0
                downs.clear()
            elif event.get("phase") == "stop":
                coverage["sessions_stopped"] += 1
                coverage["lifecycle_errors"] += not session_open
                session_open = False
            elif event.get("phase") == "error":
                coverage["errors"] += 1
            coverage["enabled"] |= event.get("enabled", False)
            coverage["dropped_events"] = max(coverage["dropped_events"], event.get("dropped_events", 0))
            continue
        if kind in ("recorder.gap", "recorder.error"):
            coverage["gaps" if kind == "recorder.gap" else "errors"] += 1
            continue
        if kind != "input.observed":
            continue
        name = event["event"]
        counts[name] += 1
        if not session_open:
            coverage["outside_session_events"] += 1
            continue
        native = event["native_timestamp_ns"]
        if native <= 0 or native < last_native:
            coverage["invalid_timestamps"] += 1
            previous_key = previous_move = None
            previous_input = None
            continue
        last_native = native
        timestamp = native / 1e9
        if previous_input is not None and timestamp - previous_input > 2:
            silences.append(timestamp - previous_input)
        previous_input = timestamp
        if name == "key_down":
            counts["repeat_key_downs"] += bool(event.get("repeat"))
            if event.get("is_correction"):
                counts["corrections"] += 1
                counts["nonrepeat_corrections"] += not event.get("repeat")
            if event.get("repeat") or event.get("is_shortcut") or event.get("is_modifier"):
                previous_key = None
                continue
            if previous_key is not None and timestamp >= previous_key:
                delta = timestamp - previous_key
                (intervals if delta <= 2 else pauses).append(delta)
            previous_key = timestamp
            if event.get("press_id") is not None:
                downs[event["press_id"]] = timestamp
        elif name == "key_up" and event.get("press_id") in downs:
            held = timestamp - downs.pop(event["press_id"])
            if held >= 0:
                holds.append(held)
        elif name == "move":
            if previous_move and timestamp > previous_move[0]:
                distance = math.hypot(event["x"] - previous_move[1], event["y"] - previous_move[2])
                speeds.append(distance / (timestamp - previous_move[0]))
            previous_move = (timestamp, event["x"], event["y"])
    features = {
        "inter_key_seconds": intervals,
        "key_hold_seconds": holds,
        "idle_seconds": pauses,
        "input_silence_seconds": silences,
        "pointer_pixels_per_second": speeds,
    }
    coverage["completed"] = bool(
        coverage["sessions_started"]
        and coverage["sessions_started"] == coverage["sessions_stopped"]
        and not session_open
        and not coverage["lifecycle_errors"]
    )
    return {
        "coverage": coverage,
        "recording_roles": sorted(roles),
        "event_counts": dict(counts),
        "features": features,
        "statistics": {name: distribution(values) for name, values in features.items()},
        "feature_notes": {
            "idle_seconds": "Gaps over 2 seconds between unmodified key downs; shortcuts reset the sequence. This does not measure all reading/planning or absence of input.",
            "input_silence_seconds": "Gaps over 2 seconds between any observed input events inside a session, excluding leading/trailing unobserved periods. Silence does not identify its purpose.",
            "corrections": "Backspace/Delete key downs, including repeats; these also include intentional editing, not solely typing errors.",
            "pointer_pixels_per_second": "Event-to-event velocities without resampling. Different sampling rates and small time intervals can skew means/tails.",
        },
    }


def recording_problems(data):
    coverage = data["coverage"]
    problems = []
    if not coverage["enabled"]:
        problems.append("input_recording_not_enabled")
    if not coverage["completed"]:
        problems.append("recording_not_closed")
    for key in (
        "gaps",
        "errors",
        "dropped_events",
        "invalid_timestamps",
        "lifecycle_errors",
        "outside_session_events",
        "incomplete_lines",
    ):
        if coverage[key]:
            problems.append(key)
    return problems


def compare(agent_path, human_path):
    agent, human = read_inputs(agent_path), read_inputs(human_path)
    reasons = {}
    for role, data in (("agent", agent), ("human", human)):
        problems = recording_problems(data)
        if data["recording_roles"] != [role]:
            problems.append("incorrect_recording_role")
        if len(data["features"]["inter_key_seconds"]) < 30:
            problems.append("fewer_than_30_active_typing_intervals")
        if problems:
            reasons[role] = problems
    sufficient = not reasons
    return {
        "status": "descriptive_comparison" if sufficient else "insufficient_evidence",
        "insufficient_evidence_reasons": reasons,
        "agent": {key: value for key, value in agent.items() if key != "features"},
        "human": {key: value for key, value in human.items() if key != "features"},
        "distances": {
            name: distances(agent["features"][name], human["features"][name])
            if sufficient
            else {"ks": None, "wasserstein": None}
            for name in agent["features"]
        },
        "weighted_score": None,
        "note": "No calibrated rubric score. Smaller empirical distances mean closer distributions, not proof of human identity. Samples are temporally correlated; no independence-based p-values are reported.",
    }
