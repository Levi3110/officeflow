"""Repeatable core benchmarks in fresh subprocesses; never an authenticity score."""

from __future__ import annotations

import argparse
import asyncio
import json
import platform
import resource
import statistics
import subprocess
import sys
import time
from pathlib import Path


def percentile(values, fraction):
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def worker(directory, seed):
    started = time.perf_counter()
    from .authority import AuthorityManager
    from .desktop import SimulationDesktop
    from .fixture import Catalog
    from .models import Persona, Settings
    from .runtime import Runtime
    from .store import Store
    from .telemetry import export_audit
    from .workflow import Workflow

    loaded = time.perf_counter()
    directory.mkdir(parents=True)
    store = Store(directory / "state.sqlite")
    settings = Settings(persona=Persona(seed=seed, characters_per_second=9))
    backend = SimulationDesktop(settings)
    runtime = Runtime(store, AuthorityManager(store, settings), backend, settings, directory)
    with Catalog() as catalog:
        task_started = time.perf_counter()
        cpu_started = time.process_time()
        outcome = asyncio.run(Workflow(runtime, catalog.url).run())
        workflow_seconds = time.perf_counter() - task_started
        workflow_cpu = time.process_time() - cpu_started
    export_started = time.perf_counter()
    export_audit(store, directory / "audit.jsonl")
    export_seconds = time.perf_counter() - export_started
    result = {
        "seed": seed,
        "status": outcome.get("status"),
        "import_seconds": loaded - started,
        "workflow_seconds": workflow_seconds,
        "workflow_cpu_seconds": workflow_cpu,
        "export_seconds": export_seconds,
        "maxrss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        * (1 if sys.platform == "darwin" else 1024),
        "input_dispatches": backend.inputs,
        "actions": store.db.execute("SELECT COUNT(*) FROM actions WHERE status='done'").fetchone()[0],
        "audit_events": store.db.execute("SELECT COUNT(*) FROM events").fetchone()[0],
        "audit_bytes": (directory / "audit.jsonl").stat().st_size,
    }
    store.close()
    result["database_bytes"] = (directory / "state.sqlite").stat().st_size
    return result


def benchmark(output, runs=9, seeds=None):
    if not 3 <= runs <= 100:
        raise ValueError("benchmark runs must be 3..100")
    seeds = seeds or [17 + i * 13 for i in range(runs)]
    directory = output.parent / (output.stem + "-runs")
    if output.exists() or directory.exists():
        raise FileExistsError("use a fresh benchmark output path")
    output.parent.mkdir(parents=True, exist_ok=True)
    records = []
    for index, seed in enumerate(seeds):
        process = subprocess.run(
            [
                sys.executable,
                "-m",
                "synthetic_human.benchmark",
                "--worker",
                "--output",
                str(directory / str(index)),
                "--seed",
                str(seed),
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        )
        records.append(json.loads(process.stdout))
    names = (
        "import_seconds",
        "workflow_seconds",
        "workflow_cpu_seconds",
        "export_seconds",
        "maxrss_bytes",
        "audit_events",
        "audit_bytes",
        "database_bytes",
        "input_dispatches",
        "actions",
    )
    report = {
        "kind": "simulation.core.benchmark",
        "platform": platform.platform(),
        "python": platform.python_version(),
        "runs": records,
        "success_rate": sum(row["status"] == "completed" for row in records) / len(records),
        "summary": {
            name: {
                "median": statistics.median(row[name] for row in records),
                "p95": percentile([row[name] for row in records], 0.95),
            }
            for name in names
        },
        "note": "Fresh-process simulation; no behavioural realtime sleeps or live authenticity score. App collector excluded to isolate core costs.",
    }
    output.write_text(json.dumps(report, indent=2))
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runs", type=int, default=9)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--seed", type=int, default=17)
    args = parser.parse_args()
    result = worker(args.output, args.seed) if args.worker else benchmark(args.output, args.runs)
    print(json.dumps(result, indent=None if args.worker else 2))


if __name__ == "__main__":
    main()
