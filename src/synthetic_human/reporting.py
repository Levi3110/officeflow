"""Archive a closed pair of traces and report a conservative, single-participant comparison."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .evaluation import compare, distribution

FEATURES = {
    "inter_key_seconds": ("Active inter-key interval", "ms", 1000),
    "key_hold_seconds": ("Key hold", "ms", 1000),
    "input_silence_seconds": ("Input silence above 2 seconds", "s", 1),
    "idle_seconds": ("Legacy inter-key idle", "s", 1),
    "pointer_pixels_per_second": ("Event-wise pointer speed (diagnostic only)", "px/s", 1),
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def recording_duration(data):
    total, opened = 0.0, None
    for line in data.decode().splitlines():
        event = json.loads(line)
        if event.get("kind") != "recorder.status":
            continue
        if event.get("phase") == "start":
            opened = event.get("timestamp")
        elif event.get("phase") == "stop":
            closed = event.get("timestamp")
            if opened is None or closed is None or closed < opened:
                return None
            total += closed - opened
            opened = None
    return total if opened is None else None


def resources(data):
    """Descriptive sampler summaries; observer overhead is not the human's computational cost."""
    values = {
        name: [] for name in ("runner_cpu_percent", "runner_rss_mib", "apps_cpu_percent", "apps_rss_mib")
    }
    foreground = Counter()
    timestamps = []
    for line in data.decode().splitlines():
        record = json.loads(line)
        if record.get("kind") != "os.sample":
            continue
        timestamps.append(record["timestamp"])
        foreground[record.get("foreground", {}).get("name", "unknown")] += 1
        for prefix, runner in (("runner", True), ("apps", False)):
            rows = [row for row in record.get("processes", []) if bool(row.get("runner")) == runner]
            if rows:
                values[prefix + "_rss_mib"].append(sum(row["rss_bytes"] for row in rows) / 1024**2)
            cpu = [row["cpu_percent"] for row in rows if not row.get("cpu_first_sample", False)]
            if cpu:
                values[prefix + "_cpu_percent"].append(sum(cpu))
    return {
        "sample_count": len(timestamps),
        "sample_window_seconds": timestamps[-1] - timestamps[0] if timestamps else None,
        "statistics": {
            key: {**distribution(samples), "peak": max(samples) if samples else None}
            for key, samples in values.items()
        },
        "foreground_samples_diagnostic_only": dict(foreground),
        "limitations": [
            "Runner means agent workflow plus observer on the agent side, but observer only on the human side.",
            "App totals include unrelated Chrome/LibreOffice sessions and may double-count shared memory.",
            "Initial per-process CPU samples are excluded; short spikes between samples remain unobserved.",
            "Passive-only AppKit foreground sampling may be stale; foreground samples are not validated dwell time.",
            "These are different capture windows, not an isolated efficiency experiment or a cost of human cognition.",
        ],
    }


def number(value, scale=1):
    return "N/A" if value is None else f"{value * scale:.3f}"


def markdown(result, manifest, resource_data):
    lines = [
        f"# Exploratory benchmark: {manifest['inputs']['agent']['recording_label']} vs {manifest['inputs']['human']['recording_label']}",
        "",
        f"Analysis date: {manifest['created_at']}.",
        "",
        "**Human behaviour varies across people and within the same person across tasks and sessions.**",
        "Typing speed, key holds, pauses, editing, shortcut preferences, navigation and problem-solving",
        "strategies differ. This benchmark compares one agent recording with one person's recording.",
        "It cannot establish a universal human baseline, general human likeness, a maximum score or",
        "a calibrated competition grade. Differences from this participant do not prove that the",
        "agent is implausible for every other person, or that either participant performed better.",
        "",
        "## Design and capture quality",
        "",
        f"- Agent: `{manifest['inputs']['agent']['recording_label']}`; human reference: `{manifest['inputs']['human']['recording_label']}`.",
        "- One participant and one recording per side; keystrokes are correlated events, not independent participants.",
        "- Both streams have closed start/stop lifecycles, sufficient active intervals and no reported gaps/drops/errors.",
        "- This tool validates recording quality and compares distributions. Output correctness, identical task text and",
        "  task-only boundaries require separate verification; capture completeness alone does not establish them.",
        "- Original events and timestamps are preserved. A recording role is a collection label, not independent proof of identity.",
        "",
        "| Recording window | Agent | Human |",
        "| --- | ---: | ---: |",
        f"| Start-to-stop duration (s) | {number(manifest['inputs']['agent']['recording_duration_seconds'])} | {number(manifest['inputs']['human']['recording_duration_seconds'])} |",
        "",
        "Recording-window duration includes observer startup/teardown and terminal interaction. It is not independently",
        "timed task completion, and is not used to claim a speedup or an efficiency win.",
        "",
        "## Observed input distributions",
        "",
        "| Feature | Unit | Agent n | Human n | Agent median | Human median | Agent p95 | Human p95 | KS | Wasserstein |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for key, (label, unit, scale) in FEATURES.items():
        a, h, distance = (
            result["agent"]["statistics"][key],
            result["human"]["statistics"][key],
            result["distances"][key],
        )
        lines.append(
            f"| {label} | {unit} | {a['count']} | {h['count']} | {number(a['median'], scale)} | {number(h['median'], scale)} | "
            f"{number(a['p95'], scale)} | {number(h['p95'], scale)} | {number(distance['ks'])} | {number(distance['wasserstein'], scale)} |"
        )
    lines += [
        "",
        "KS is a dimensionless empirical CDF distance. Wasserstein has the units shown for its feature; values across",
        "different units should not be ranked against each other. Smaller distances describe closer sampled distributions,",
        "not percentages of human likeness. N/A means no two nonempty comparable feature sets, not a zero distance.",
        "",
        f"Input-silence samples: agent {result['agent']['statistics']['input_silence_seconds']['count']}; "
        f"human {result['human']['statistics']['input_silence_seconds']['count']}. Small pause samples limit distribution conclusions.",
        "",
        "| Input events | Agent | Human |",
        "| --- | ---: | ---: |",
    ]
    for key in (
        "key_down",
        "key_up",
        "repeat_key_downs",
        "move",
        "mouse_down",
        "scroll",
        "corrections",
        "nonrepeat_corrections",
    ):
        lines.append(
            f"| {key} | {result['agent']['event_counts'].get(key, 0)} | {result['human']['event_counts'].get(key, 0)} |"
        )
    lines += [
        "",
        "Backspace/Delete includes intentional editing and autorepeat; it is not a verified typo count. The difference",
        "in click counts can reflect shortcut use, navigation strategy, edits and experience. Event-wise mouse speed is",
        "especially sampling-sensitive: physical devices and generated paths can emit samples at different cadences.",
        "The raw pointer distribution is retained as a diagnostic, not used as an authenticity grade or a calibration target.",
        "Legacy inter-key idle resets at shortcuts; zero legacy idle does not mean no pauses. Input silence measures",
        "absence of observed input above two seconds without identifying reading, thought or off-task activity.",
        "",
        "## OS resource diagnostics",
        "",
        "These sampler observations are not a controlled, isolated resource-efficiency comparison.",
        "",
        "| Measurement | Agent | Human |",
        "| --- | ---: | ---: |",
    ]
    resource_rows = (
        ("Runner peak RSS (MiB)", "runner_rss_mib", "peak"),
        ("Runner sampled CPU peak (%)", "runner_cpu_percent", "peak"),
        ("All matching apps peak RSS (MiB)", "apps_rss_mib", "peak"),
        ("All matching apps sampled CPU p95 (%)", "apps_cpu_percent", "p95"),
    )
    for label, key, statistic in resource_rows:
        row = [
            resource_data[role]["statistics"][key][statistic] if resource_data[role] else None
            for role in ("agent", "human")
        ]
        lines.append(f"| {label} | {number(row[0])} | {number(row[1])} |")
    lines += [
        "",
        "The human-side Python process is a passive observer; the agent-side process also plans and executes the workflow.",
        "Its memory/CPU difference does not measure human computational effort. App totals include unrelated sessions,",
        "shared memory can be counted repeatedly, and capture windows differ. Video/screenshots can also change resource costs.",
        "",
        "Passive-only AppKit foreground sampling can remain cached when its main run loop is not advanced. Foreground",
        "samples are excluded from dwell-time and task-completion interpretation. Independent, validated focus instrumentation",
        "is needed for dwell analysis; the diagnostic name counts are retained in resources.json.",
        "",
        "## Limits and next evaluation",
        "",
        "1. This is a single-participant case study. Skill, typing style, device, language, familiarity, shortcut habits and",
        "   task interpretation vary. Earlier practice can change performance. No population-level conclusion follows.",
        "2. Capture quality is necessary but does not verify identical output, text length, task difficulty or task-only boundaries.",
        "3. Samples are temporally correlated; no independence-based p-values, population confidence intervals or invented scores are reported.",
        "4. The five-feature summaries omit higher-level action sequences, semantic correctness of human outputs, conditional",
        "   behaviour by application/context and independently grounded app dwell. They are not a complete authenticity evaluation.",
        "5. For stronger evidence, define output/phase checks, collect multiple participants and repeated sessions, control",
        "   device/layout and background load, validate focus, and compare pointer gestures at matched sampling rates.",
        "6. Separate personalisation/training sessions from held-out evaluation. Report per-person results and variability",
        "   rather than optimising one average persona to one person's trace. Include failed runs in completion-rate denominators.",
        "",
        "The 30/30/20/20 rubric remains unscored (`weighted_score: null`). This report is not evidence of maximum realism",
        "or universal human imitation. Published benchmark files contain aggregates and provenance hashes; raw human",
        "pointer coordinates and process IDs belong only in the optional local archive.",
        "Raw snapshots are included in this local report folder."
        if manifest["raw_archived"]
        else "This report contains aggregates only; no raw snapshots were copied.",
        "",
        "Machine-readable artifacts: `comparison.json`, `summary.csv`, `resources.json` and `manifest.json`.",
    ]
    if manifest["study_notes"]:
        lines += ["", "## Study notes", ""]
        lines += [f"- {note}" for note in manifest["study_notes"]]
    return "\n".join(lines) + "\n"


def build_report(agent_directory, human_directory, output, archive_raw=False, study_notes=()):
    """Produce a report for the collected single-participant pair; never alter the observations."""
    if output.exists():
        raise FileExistsError("Use a new report directory to preserve earlier results")
    sources = {}
    for role, directory in (("agent", agent_directory), ("human", human_directory)):
        for name in ("inputs.jsonl", "telemetry.jsonl"):
            path = directory / name
            if path.exists():
                sources[(role, name)] = (path, path.read_bytes())
    result = compare(agent_directory / "inputs.jsonl", human_directory / "inputs.jsonl")
    if result["status"] != "descriptive_comparison":
        raise ValueError(
            "Capture quality checks failed: " + json.dumps(result["insufficient_evidence_reasons"])
        )
    resource_data = {
        role: resources(sources[(role, "telemetry.jsonl")][1])
        if (role, "telemetry.jsonl") in sources
        else None
        for role in ("agent", "human")
    }
    manifest = {
        "schema_version": 1,
        "created_at": datetime.now(ZoneInfo("Asia/Singapore")).isoformat(timespec="seconds"),
        "design": "One participant reference recording and one agent run; exploratory descriptive comparison.",
        "study_notes": list(study_notes),
        "inputs": {
            role: {
                "recording_label": directory.name,
                "recording_duration_seconds": recording_duration(sources[(role, "inputs.jsonl")][1]),
                "files": {
                    name: {"sha256": digest(data), "bytes": len(data)}
                    for (source_role, name), (_, data) in sources.items()
                    if source_role == role
                },
            }
            for role, directory in (("agent", agent_directory), ("human", human_directory))
        },
        "analysis_code_sha256": {
            name: digest(Path(__file__).with_name(name).read_bytes())
            for name in ("reporting.py", "evaluation.py")
        },
        "raw_archived": archive_raw,
        "weighted_score": None,
    }
    # Verify that a source did not change between capture validation and the snapshot.
    if any(path.read_bytes() != data for path, data in sources.values()):
        raise RuntimeError("A source trace changed during analysis; wait for collection to finish")
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".benchmark-", dir=output.parent))
    try:
        for name, body in (
            ("comparison.json", result),
            ("resources.json", resource_data),
            ("manifest.json", manifest),
        ):
            (staging / name).write_text(json.dumps(body, indent=2) + "\n")
        with (staging / "summary.csv").open("w", newline="") as stream:
            writer = csv.writer(stream, lineterminator="\n")
            writer.writerow(
                [
                    "feature",
                    "unit",
                    "agent_count",
                    "human_count",
                    "agent_median",
                    "human_median",
                    "agent_p95",
                    "human_p95",
                    "ks",
                    "wasserstein",
                ]
            )
            for key, (_, unit, scale) in FEATURES.items():
                a, h, distance = (
                    result["agent"]["statistics"][key],
                    result["human"]["statistics"][key],
                    result["distances"][key],
                )
                scaled = [
                    value * scale if value is not None else None
                    for value in (a["median"], h["median"], a["p95"], h["p95"])
                ]
                writer.writerow(
                    [
                        key,
                        unit,
                        a["count"],
                        h["count"],
                        *scaled,
                        distance["ks"],
                        distance["wasserstein"] * scale if distance["wasserstein"] is not None else None,
                    ]
                )
        (staging / "report.md").write_text(markdown(result, manifest, resource_data))
        if archive_raw:
            for (role, name), (_, data) in sources.items():
                target = staging / "raw" / role / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
        if output.exists():
            raise FileExistsError("Report directory appeared during analysis")
        staging.rename(output)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return manifest
