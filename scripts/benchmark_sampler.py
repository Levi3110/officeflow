"""Compare real OS sampling cost with a frozen repository revision; no GUI input or fake telemetry."""

import argparse
import json
import platform
import statistics
import subprocess
import time
from pathlib import Path

from synthetic_human.reporting import digest
from synthetic_human.telemetry import TelemetryCollector


def run(output, baseline_ref, pairs=9, samples_per_batch=10):
    if output.exists():
        raise FileExistsError("Use a new sampler benchmark output")
    code = subprocess.check_output(
        ["git", "show", f"{baseline_ref}:src/synthetic_human/telemetry.py"], text=True
    )
    namespace = {"__name__": "frozen_sampler_baseline"}
    exec(compile(code, "frozen-sampler-baseline.py", "exec"), namespace)
    samplers = {
        "baseline": namespace["TelemetryCollector"](Path("unused-baseline.jsonl"), "simulation"),
        "optimized": TelemetryCollector(Path("unused-optimized.jsonl"), "simulation"),
    }
    for sampler in samplers.values():
        sampler._sample()  # Prime process CPU observations and metadata before steady-state timing.
    records = []
    for pair in range(pairs):
        for label in ("baseline", "optimized") if pair % 2 == 0 else ("optimized", "baseline"):
            sampler = samplers[label]
            # One full metadata refresh per ten samples models the 5s TTL at 0.5s cadence.
            # PID discovery and live CPU/RSS/thread calls still happen in every iteration.
            for metadata in getattr(sampler, "process_metadata", {}).values():
                metadata["checked_at"] = 0
            started, cpu_started = time.perf_counter(), time.process_time()
            counts = []
            for _ in range(samples_per_batch):
                sample = sampler._sample()
                counts.append(len(sample["processes"]))
            records.append(
                {
                    "pair": pair,
                    "variant": label,
                    "samples": samples_per_batch,
                    "cpu_ms_per_sample": (time.process_time() - cpu_started) * 1000 / samples_per_batch,
                    "wall_ms_per_sample": (time.perf_counter() - started) * 1000 / samples_per_batch,
                    "observed_process_rows_per_sample": counts,
                }
            )
    summary = {
        label: {
            key: statistics.median(row[key] for row in records if row["variant"] == label)
            for key in ("cpu_ms_per_sample", "wall_ms_per_sample")
        }
        for label in samplers
    }
    result = {
        "kind": "real_os_sampler_microbenchmark",
        "platform": platform.platform(),
        "baseline_ref": baseline_ref,
        "baseline_code_sha256": digest(code.encode()),
        "optimized_code_sha256": digest(Path("src/synthetic_human/telemetry.py").read_bytes()),
        "pairs": pairs,
        "samples_per_batch": samples_per_batch,
        "records": records,
        "summary": summary,
        "note": "Real process APIs, alternating variant order. Simulation mode here excludes GUI/Quartz/focus work only; no simulated process measurements are emitted. Warmed microbenchmark without sleeps; optimized metadata expiry is forced once per ten samples to model normal cadence. This is sampler CPU cost, not desktop throughput, human authenticity, or total native agent cost.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline-ref", default="111bf38")
    args = parser.parse_args()
    run(args.output, args.baseline_ref)
