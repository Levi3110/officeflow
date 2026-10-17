"""Measure all four assignment dimensions without inventing calibrated grades."""

from __future__ import annotations

import csv
import io
import json
import math
import statistics
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .assessment import assess
from .benchmark import percentile
from .evaluation import compare, distances, distribution, read_inputs, recording_problems
from .reporting import digest, number, resources

DIMENSIONS = (
    ("process_telemetry_authenticity", "Process Telemetry Authenticity", 0.30, "unspecified"),
    ("human_entropy_timing", "Human Entropy & Timing", 0.30, "unspecified"),
    ("complexity_of_action", "Complexity of Action", 0.20, "Secondary"),
    ("resource_efficiency", "Resource Efficiency", 0.20, "Primary"),
)


def entropy(values, bin_seconds=0.025):
    """Fixed-width observed-interval entropy; descriptive, not a realism objective."""
    bins = Counter(math.floor(value / bin_seconds) for value in values)
    return (
        -sum((count / len(values)) * math.log2(count / len(values)) for count in bins.values())
        if values
        else None
    )


def process_profile(data):
    records = [json.loads(line) for line in data.decode().splitlines() if line.strip()]
    samples = [row for row in records if row.get("kind") == "os.sample"]
    errors = sum(row.get("kind") == "collector.error" for row in records)
    families, sources, backends = Counter(), Counter(), Counter()
    intervals, app_threads = [], []
    io_available = process_rows = 0
    cpu_seconds = covered_seconds = 0.0
    previous = None
    for sample in samples:
        sources[sample.get("source", "unknown")] += 1
        backends[sample.get("backend", "unknown")] += 1
        current = sample.get("monotonic", sample["timestamp"])
        delta = current - previous if previous is not None else None
        if delta is not None and delta > 0:
            intervals.append(delta)
        seen = set()
        threads = 0
        for row in sample.get("processes", []):
            process_rows += 1
            io_available += row.get("io") is not None
            name = row.get("name", "").lower()
            family = (
                "runner"
                if row.get("runner")
                else "Chrome"
                if "chrome" in name
                else "LibreOffice"
                if any(x in name for x in ("libreoffice", "soffice"))
                else "other"
            )
            seen.add(family)
            if not row.get("runner"):
                threads += row.get("threads", 0)
            elif delta is not None and delta > 0 and not row.get("cpu_first_sample", False):
                cpu_seconds += row["cpu_percent"] * delta / 100
                covered_seconds += delta
        families.update(seen)
        app_threads.append(threads)
        previous = current
    return {
        **resources(data),
        "collector_errors": errors,
        "sample_sources": dict(sources),
        "sample_backends": dict(backends),
        "family_sample_presence": dict(families),
        "sampling_interval_seconds": distribution(intervals),
        "app_threads_per_sample": distribution(app_threads),
        "process_rows": process_rows,
        "io_available_rows": io_available,
        "runner_cpu_seconds_estimate": cpu_seconds if covered_seconds else None,
        "runner_cpu_estimate_covered_seconds": covered_seconds,
        "cpu_estimate_method": "Right-endpoint sum(cpu_percent / 100 * elapsed sample interval), excluding first CPU observations; diagnostic estimate, not a hardware counter or energy measure.",
    }


def app_features(data):
    """Whole-app-scope diagnostics, not isolated task costs or population samples."""
    features = {key: [] for key in ("cpu_percent", "rss_mib", "threads")}
    for line in data.decode().splitlines():
        sample = json.loads(line)
        if sample.get("kind") != "os.sample":
            continue
        rows = [row for row in sample.get("processes", []) if not row.get("runner")]
        if not rows:
            continue
        features["rss_mib"].append(sum(row["rss_bytes"] for row in rows) / 1024**2)
        features["threads"].append(sum(row.get("threads", 0) for row in rows))
        valid_cpu = [row["cpu_percent"] for row in rows if not row.get("cpu_first_sample", False)]
        if valid_cpu:
            features["cpu_percent"].append(sum(valid_cpu))
    return features


def input_sources(input_data, telemetry_data):
    """Publish only attribution groups; never expose raw human PIDs or coordinates."""
    runner_pids = {
        process["pid"]
        for line in telemetry_data.decode().splitlines()
        for process in json.loads(line).get("processes", [])
        if process.get("runner")
    }
    counts = Counter()
    for line in input_data.decode().splitlines():
        row = json.loads(line)
        if row.get("kind") == "input.observed":
            source = row.get("source_pid")
            counts["runner" if source in runner_pids else "unknown" if not source else "other_process"] += 1
    return dict(counts)


def core_summary(report):
    if report.get("kind") != "simulation.core.benchmark" or not report.get("runs"):
        raise ValueError("Expected a nonempty fresh-process simulation.core.benchmark")
    rows = report["runs"]
    names = (
        "workflow_seconds",
        "workflow_cpu_seconds",
        "maxrss_bytes",
        "import_seconds",
        "export_seconds",
        "input_dispatches",
        "actions",
        "audit_bytes",
        "database_bytes",
    )
    return {
        "kind": report["kind"],
        "platform": report["platform"],
        "python": report["python"],
        "trial_count": len(rows),
        "completed_trials": sum(row["status"] == "completed" for row in rows),
        "summary": {
            name: {
                "median": statistics.median(row[name] for row in rows),
                "p95": percentile([row[name] for row in rows], 0.95),
            }
            for name in names
        },
        "scope": "Fresh-process simulation core only. No GUI, realtime behaviour sleeps or OS collector. Every supplied trial remains in the denominator and summaries, including failures.",
    }


def evaluate(agent, human, core_path):
    sources = {}
    for role, directory, names in (
        (
            "agent",
            agent,
            (
                "inputs.jsonl",
                "telemetry.jsonl",
                "metrics.json",
                "audit.jsonl",
                "comparison.ods",
                "report.odt",
                "state.sqlite",
            ),
        ),
        ("human", human, ("inputs.jsonl", "telemetry.jsonl")),
    ):
        for name in names:
            path = directory / name
            sources[(role, name)] = (path, path.read_bytes())
    wal = agent / "state.sqlite-wal"
    if wal.exists():
        sources[("agent", wal.name)] = (wal, wal.read_bytes())
    sources[("core", core_path.name)] = (core_path, core_path.read_bytes())
    comparison = compare(agent / "inputs.jsonl", human / "inputs.jsonl")
    assessment = assess(agent)  # Read-only: independently rechecks files and source consistency.
    saved = json.loads(sources[("agent", "metrics.json")][1])
    profiles = {role: process_profile(sources[(role, "telemetry.jsonl")][1]) for role in ("agent", "human")}
    observations = {
        role: read_inputs(path / "inputs.jsonl") for role, path in (("agent", agent), ("human", human))
    }
    native = (
        assessment["backend"] == "macos"
        and assessment["desktop_checks_passed"] == assessment["criteria_count"]
    )
    statuses = {
        "process_telemetry_authenticity": "independent_native_observations; similarity_unvalidated"
        if native
        and all(
            profile["sample_count"]
            and not profile["collector_errors"]
            and profile["sample_sources"] == {"psutil": profile["sample_count"]}
            and profile["sample_backends"] == {"macos": profile["sample_count"]}
            for profile in profiles.values()
        )
        else "insufficient_native_process_evidence",
        "human_entropy_timing": "single_participant_descriptive"
        if comparison["status"] == "descriptive_comparison"
        else "insufficient_evidence",
        "complexity_of_action": "native_workflow_verified" if native else "native_workflow_not_verified",
        "resource_efficiency": "native_single_run_and_repeated_simulation"
        if native
        else "simulation_core_and_unvalidated_run_diagnostics",
    }
    for role, observed in observations.items():
        if recording_problems(observed) or observed["recording_roles"] != [role]:
            statuses["process_telemetry_authenticity"] = "incomplete_input_capture"
    app_vectors = {role: app_features(sources[(role, "telemetry.jsonl")][1]) for role in ("agent", "human")}
    app_comparison = {
        key: {
            "agent": distribution(app_vectors["agent"][key]),
            "human": distribution(app_vectors["human"][key]),
            "distance": distances(app_vectors["agent"][key], app_vectors["human"][key]),
        }
        for key in app_vectors["agent"]
    }
    event_counts = Counter()
    handoffs = 0
    for line in sources[("agent", "audit.jsonl")][1].decode().splitlines():
        row = json.loads(line)
        if row["kind"] == "action.verified":
            event_counts[row["body"]["kind"]] += 1
        handoffs += row["kind"] == "handoff.committed"
    report = {
        "kind": "four_criterion_evidence_benchmark",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "native_verified": native,
        "agent_label": agent.name,
        "human_label": human.name,
        "dimensions": [
            {
                "id": key,
                "name": name,
                "weight": weight,
                "priority": priority,
                "status": statuses[key],
                "score_0_100": None,
                "weighted_points": None,
            }
            for key, name, weight, priority in DIMENSIONS
        ],
        "weighted_score": None,
        "weighted_formula": "0.30*A + 0.30*H + 0.20*C + 0.20*R; all four calibrated scores required",
        "priority_note": "Primary/Secondary are emphasis labels; they do not change the supplied weights.",
        "process_telemetry": {
            "profiles": profiles,
            "all_matching_app_feature_comparison": app_comparison,
            "agent_observed_source_groups": input_sources(
                sources[("agent", "inputs.jsonl")][1], sources[("agent", "telemetry.jsonl")][1]
            ),
        },
        "human_entropy_timing": {
            "comparison": comparison,
            "observed_inter_key_entropy_bits_25ms_bins": {
                role: entropy(observation["features"]["inter_key_seconds"])
                for role, observation in observations.items()
            },
        },
        "complexity": {
            "assessment": assessment,
            "verified_actions": dict(event_counts),
            "verified_action_total": sum(event_counts.values()),
            "handoffs": handoffs,
            "cell_edits": saved["verified_cell_edits"],
            "gui_saves": saved["gui_save_count"],
        },
        "resource_efficiency": {
            "native_runner": profiles["agent"]["statistics"],
            "native_runner_cpu_seconds_estimate": profiles["agent"]["runner_cpu_seconds_estimate"],
            "timing_seconds": saved["timing_seconds"],
            "model_calls": saved["model_calls"],
            "input_tokens": saved["model_input_tokens"],
            "output_tokens": saved["model_output_tokens"],
            "core": core_summary(json.loads(core_path.read_text())),
        },
        "limitations": [
            "One selected agent trace and one participant/session. People differ in typing, editing, shortcuts, navigation and problem-solving; no universal human baseline or close-match claim follows.",
            "Independent sampler provenance is evidence of real measurements, not proof of human-like process patterns. Source metadata exposes generated input; no hardware-origin disguise is attempted.",
            "All matching app processes include unrelated sessions, and RSS may double-count shared memory. Foreground labels can be stale; they are excluded from dwell/completion conclusions. Process I/O may be unavailable; kernel/network traces are absent.",
            "Human runner observes only; agent runner plans and executes too. Human/agent runner CPU and RSS are not like-for-like cognitive efficiency measures.",
            "Small silence samples, unequal event cadences, correlated events and unmatched manual text limit inference. More entropy is not automatically better.",
            "Native resource diagnostics are one selected run, with video/screenshot overhead and uncontrolled background load. Core trials are simulation, not desktop throughput or a native success rate.",
            "The retained successful native demo does not supply an all-attempt reliability denominator. Earlier development failures exist. Human task completion is user-reported; manual output correctness was not independently verified.",
            "No calibrated 0-100 scoring thresholds, process baseline population or isolated native efficiency baseline were supplied. Weights alone cannot produce a valid competition grade; every grade remains null.",
        ],
        "provenance": {
            f"{role}/{name}": {"sha256": digest(data), "bytes": len(data)}
            for (role, name), (_, data) in sources.items()
        },
        "analysis_code_sha256": {
            name: digest(Path(__file__).with_name(name).read_bytes())
            for name in ("rubric.py", "evaluation.py", "assessment.py", "reporting.py", "benchmark.py")
        },
    }
    if any(path.read_bytes() != data for path, data in sources.values()):
        raise RuntimeError("Evidence changed during analysis; use closed, stable recordings")
    return report


def render(report):
    lines = [
        "# Four-criterion benchmark",
        "",
        f"Analysis: {report['created_at']}. Agent: `{report['agent_label']}`; human reference: `{report['human_label']}`.",
        "",
        "All four criteria are measured below. Weights are not achieved scores. Resource Efficiency is Primary; Complexity is Secondary. Priority labels do not alter the 30/30/20/20 formula.",
        "",
        "| Criterion | Weight | Priority | Evidence status | Grade |",
        "| --- | ---: | --- | --- | --- |",
    ]
    for row in report["dimensions"]:
        lines.append(
            f"| {row['name']} | {row['weight']:.0%} | {row['priority']} | {row['status']} | Uncalibrated |"
        )
    profiles = report["process_telemetry"]["profiles"]
    lines += [
        "",
        "## Process Telemetry Authenticity — 30%",
        "",
        "Independent OS samples exist; process-pattern similarity to humans remains unvalidated. Hashes establish stored-file integrity, not trusted hardware attestation.",
        "",
        "| Measurement | Agent | Human |",
        "| --- | ---: | ---: |",
    ]
    for label, key in (
        ("OS samples", "sample_count"),
        ("Collector errors", "collector_errors"),
        ("Process rows with I/O available", "io_available_rows"),
        ("Estimated runner CPU-seconds (diagnostic)", "runner_cpu_seconds_estimate"),
    ):
        lines.append(f"| {label} | {number(profiles['agent'][key])} | {number(profiles['human'][key])} |")
    lines += [
        "",
        "| All matching app processes (diagnostic only) | Agent median | Human median | KS | Wasserstein |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for feature, values in report["process_telemetry"]["all_matching_app_feature_comparison"].items():
        lines.append(
            f"| {feature} | {number(values['agent']['median'])} | {number(values['human']['median'])} | {number(values['distance']['ks'])} | {number(values['distance']['wasserstein'])} |"
        )
    lines += [
        "",
        "The table compares entire matching app scopes at unequal sampling times, without task-phase alignment. KS/Wasserstein are descriptive distances only; unrelated sessions and shared memory confound them. They are not an isolated task or population process-pattern benchmark.",
        "",
    ]
    for role in ("agent", "human"):
        profile = profiles[role]
        lines += [
            f"- {role.title()} source counts: `{json.dumps(profile['sample_sources'])}`; family sample presence: `{json.dumps(profile['family_sample_presence'])}`."
        ]
    lines += [
        f"- Agent observed input source groups: `{json.dumps(report['process_telemetry']['agent_observed_source_groups'])}`. Automation provenance is preserved.",
        "",
        "CPU/RSS describe real sampled activity, but app totals include unrelated processes. Missing I/O, kernel/network traces and validated dwell limit authenticity conclusions.",
        "",
        "## Human Entropy & Timing — 30%",
        "",
        "**People differ in typing and task-solving strategy. One person's session is an individual reference, not a universal human standard.**",
        "",
        "| Observed feature | Agent n | Human n | Agent median | Human median | Agent CV | Human CV | KS |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    comparison = report["human_entropy_timing"]["comparison"]
    for key, unit, scale in (
        ("inter_key_seconds", "ms", 1000),
        ("key_hold_seconds", "ms", 1000),
        ("input_silence_seconds", "s", 1),
    ):
        a, h = (comparison[role]["statistics"][key] for role in ("agent", "human"))
        lines.append(
            f"| {key} ({unit}) | {a['count']} | {h['count']} | {number(a['median'], scale)} | {number(h['median'], scale)} | {number(a['cv'])} | {number(h['cv'])} | {number(comparison['distances'][key]['ks'])} |"
        )
    entropy_rows = report["human_entropy_timing"]["observed_inter_key_entropy_bits_25ms_bins"]
    lines += [
        "",
        f"Observed inter-key entropy (fixed 25 ms bins): agent {number(entropy_rows['agent'])} bits; human {number(entropy_rows['human'])} bits. Higher entropy is not automatically more realistic. Raw event-wise pointer speeds are sampling-sensitive diagnostics only.",
        "",
        "## Complexity of Action — 20%, Secondary",
        "",
    ]
    complexity = report["complexity"]
    lines += [
        f"- Fresh read-only assessment: {complexity['assessment']['desktop_checks_passed']}/{complexity['assessment']['criteria_count']} desktop activity checks; this is a functional checklist, not 20/20 points.",
        f"- {complexity['verified_action_total']} verified actions, {len(complexity['verified_actions'])} action types, {complexity['handoffs']} handoffs, {complexity['cell_edits']} cell edits and {complexity['gui_saves']} GUI saves.",
        f"- Action mix: `{json.dumps(complexity['verified_actions'])}`.",
        "- Scenario: bounded three-product localhost catalog, Calc spreadsheet/formulas and Writer report. General websites, Microsoft Office and open-ended planning remain unevaluated.",
        "",
        "## Resource Efficiency — 20%, Primary",
        "",
        "### Selected real desktop run"
        if report["native_verified"]
        else "### Unvalidated run diagnostics (not native evidence)",
        "",
        "| Runner diagnostic | Value |",
        "| --- | ---: |",
    ]
    efficiency = report["resource_efficiency"]
    for label, key, statistic in (
        ("RSS median (MiB)", "runner_rss_mib", "median"),
        ("RSS p95 (MiB)", "runner_rss_mib", "p95"),
        ("RSS peak (MiB)", "runner_rss_mib", "peak"),
        ("Sampled CPU p95 (%)", "runner_cpu_percent", "p95"),
        ("Sampled CPU peak (%)", "runner_cpu_percent", "peak"),
    ):
        lines.append(f"| {label} | {number(efficiency['native_runner'][key][statistic])} |")
    lines += [
        f"| Estimated CPU-seconds | {number(efficiency['native_runner_cpu_seconds_estimate'])} |",
        f"| Model calls / input tokens / output tokens | {efficiency['model_calls']} / {efficiency['input_tokens']} / {efficiency['output_tokens']} |",
        "",
        "Default routing uses code policies, so zero model cost is specific to this bounded MVP, not arbitrary LLM planning. Sampled CPU-seconds are an estimate, not energy or hardware accounting. The elapsed timing-category breakdown is in benchmark.json. Behavioural waits, application wait/verification and runtime overhead remain separate categories; behavioural sleep is not treated as pure execution overhead.",
        "",
        "| Elapsed timing category | Seconds |",
        "| --- | ---: |",
        *[f"| {key} | {number(value)} |" for key, value in efficiency["timing_seconds"].items()],
        "",
        "### Fresh-process simulation core",
        "",
        f"{efficiency['core']['completed_trials']}/{efficiency['core']['trial_count']} trials completed. All supplied trials remain in the denominator. Core wall/CPU time excludes realtime behavioural sleeping, application execution and the OS sampler.",
        "",
        "| Measurement | Median | p95 |",
        "| --- | ---: | ---: |",
    ]
    for key, label, scale in (
        ("workflow_seconds", "Core wall time (ms)", 1000),
        ("workflow_cpu_seconds", "Core CPU time (ms)", 1000),
        ("maxrss_bytes", "Process lifetime peak RSS (MiB)", 1 / 1024**2),
        ("import_seconds", "Imports (ms)", 1000),
        ("export_seconds", "Audit export (ms)", 1000),
    ):
        values = efficiency["core"]["summary"][key]
        lines.append(f"| {label} | {number(values['median'], scale)} | {number(values['p95'], scale)} |")
    lines += [
        "",
        "These repeated trials measure simulation-core efficiency. They do not establish native desktop efficiency, a population success rate, or a speed advantage over a human observer. A controlled repeated native baseline is still needed.",
        "",
        "## Interpretation and missing evidence",
        "",
    ]
    lines += [f"- {item}" for item in report["limitations"]]
    lines += [
        "",
        "**Weighted score: unassigned (`null`).** Formula: `0.30*A + 0.30*H + 0.20*C + 0.20*R`, once independently calibrated scores exist. Do not convert a checklist, entropy, KS distance or low memory into competition points.",
        "",
    ]
    return "\n".join(lines)


def save(report, directory):
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "benchmark.json").write_text(json.dumps(report, indent=2) + "\n")
    (directory / "report.md").write_text(render(report))
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(["criterion", "weight", "priority", "evidence_status", "score_0_100", "weighted_points"])
    for row in report["dimensions"]:
        writer.writerow(
            [
                row["name"],
                row["weight"],
                row["priority"],
                row["status"],
                row["score_0_100"],
                row["weighted_points"],
            ]
        )
    (directory / "rubric.csv").write_text(stream.getvalue())
