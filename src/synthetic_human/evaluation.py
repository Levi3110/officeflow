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
    intervals, holds, pauses, speeds = [], [], [], []
    downs = {}
    previous_key = previous_move = None
    counts = Counter()
    coverage = {"enabled": False, "gaps": 0, "errors": 0, "dropped_events": 0, "invalid_timestamps": 0}
    roles = set()
    last_native = 0
    for line in path.open():
        if not line.strip():
            continue
        event = json.loads(line)
        kind = event.get("kind")
        if kind == "recorder.status":
            if event.get("recording_role"):
                roles.add(event["recording_role"])
            if event.get("phase") == "start":
                previous_key = previous_move = None
                last_native = 0
                downs.clear()
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
        native = event["native_timestamp_ns"]
        if native <= 0 or native < last_native:
            coverage["invalid_timestamps"] += 1
            previous_key = previous_move = None
            continue
        last_native = native
        timestamp = native / 1e9
        if name == "key_down":
            if event.get("is_correction"):
                counts["corrections"] += 1
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
        "pointer_pixels_per_second": speeds,
    }
    return {
        "coverage": coverage,
        "recording_roles": sorted(roles),
        "event_counts": dict(counts),
        "features": features,
        "statistics": {name: distribution(values) for name, values in features.items()},
    }


def compare(agent_path, human_path):
    agent, human = read_inputs(agent_path), read_inputs(human_path)
    sufficient = (
        agent["recording_roles"] == ["agent"]
        and human["recording_roles"] == ["human"]
        and all(
            data["coverage"]["enabled"] and len(data["features"]["inter_key_seconds"]) >= 30
            for data in (agent, human)
        )
    )
    uninterrupted = all(
        not any(data["coverage"][key] for key in ("gaps", "errors", "dropped_events", "invalid_timestamps"))
        for data in (agent, human)
    )
    return {
        "status": "descriptive_comparison" if sufficient and uninterrupted else "insufficient_evidence",
        "agent": {key: value for key, value in agent.items() if key != "features"},
        "human": {key: value for key, value in human.items() if key != "features"},
        "distances": {
            name: distances(agent["features"][name], human["features"][name]) for name in agent["features"]
        },
        "weighted_score": None,
        "note": "No calibrated rubric score. Smaller empirical distances mean closer distributions, not proof of human identity. Samples are temporally correlated; no independence-based p-values are reported.",
    }
