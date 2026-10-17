from __future__ import annotations

import asyncio
import json
import math
import os
import platform
import statistics
import threading
import time
from collections import Counter

import psutil


def read_macos_foreground():
    """AppKit focus must be refreshed on the main run loop, including passive sessions."""
    import AppKit
    import CoreFoundation as CF

    CF.CFRunLoopRunInMode(CF.kCFRunLoopDefaultMode, 0.002, False)
    app = AppKit.NSWorkspace.sharedWorkspace().frontmostApplication()
    if app is None:
        raise RuntimeError("No foreground application was reported")
    return {"pid": int(app.processIdentifier()), "name": str(app.localizedName())}


class TelemetryCollector:
    """Independent OS sampler. It never consumes executor commands to invent activity."""

    def __init__(self, path, mode, interval=0.5, metadata_refresh_seconds=5.0):
        self.path, self.mode, self.interval = path, mode, interval
        self.stopped = threading.Event()
        self.thread = None
        self.processes = {}
        self.process_metadata = {}
        self.metadata_refresh_seconds = metadata_refresh_seconds
        self.foreground_task = None
        self.foreground_snapshot = None

    def _refresh_foreground(self):
        try:
            self.foreground_snapshot = (time.monotonic(), read_macos_foreground(), None)
        except Exception as exc:
            self.foreground_snapshot = (time.monotonic(), None, str(exc))

    async def _monitor_foreground(self):
        while not self.stopped.is_set():
            await asyncio.sleep(self.interval)
            self._refresh_foreground()

    def start(self):
        if self.mode == "macos" and platform.system() == "Darwin":
            # The OS sampler remains independent; this main-loop heartbeat refreshes only focus.
            # It emits no input and is needed when capture-human is otherwise just asyncio.sleep.
            try:
                loop = asyncio.get_running_loop()
                if threading.current_thread() is not threading.main_thread():
                    raise RuntimeError("Foreground monitoring requires the main thread")
                self._refresh_foreground()
                self.foreground_task = loop.create_task(self._monitor_foreground())
            except RuntimeError as exc:
                self.foreground_snapshot = (time.monotonic(), None, str(exc))
        self.thread = threading.Thread(target=self._run, name="os-telemetry", daemon=True)
        self.thread.start()

    def _sample(self):
        rows = []
        alive = set()
        sampled_at = time.monotonic()
        pids = set(psutil.pids())  # Discover new PIDs every sample; refresh stable names less often.
        for pid in pids:
            try:
                cached = self.process_metadata.get(pid)
                proc = self.processes.get((pid, cached["created"])) if cached else None
                if proc is not None and not proc.is_running():
                    cached = None  # PID reuse: never carry CPU history into a different process.
                if cached is None or sampled_at - cached["checked_at"] >= self.metadata_refresh_seconds:
                    candidate = psutil.Process(pid)
                    with candidate.oneshot():
                        name, created = candidate.name(), candidate.create_time()
                    cached = {"name": name, "created": created, "checked_at": sampled_at}
                    self.process_metadata[pid] = cached
                name = cached["name"]
                if pid != os.getpid() and not any(
                    x in name.lower() for x in ("chrome", "soffice", "libreoffice")
                ):
                    continue
                identity = (pid, cached["created"])
                alive.add(identity)
                first = identity not in self.processes
                if first:
                    self.processes[identity] = psutil.Process(pid)
                proc = self.processes[identity]
                with proc.oneshot():
                    io = None
                    if hasattr(proc, "io_counters"):
                        try:
                            io = proc.io_counters()._asdict()
                        except (psutil.AccessDenied, NotImplementedError):
                            pass
                    rows.append(
                        {
                            "pid": proc.pid,
                            "name": name,
                            "create_time": cached["created"],
                            "metadata_age_seconds": max(0, sampled_at - cached["checked_at"]),
                            "runner": proc.pid == os.getpid(),
                            "cpu_percent": proc.cpu_percent(),
                            "rss_bytes": proc.memory_info().rss,
                            "threads": proc.num_threads(),
                            "io": io,
                            "cpu_first_sample": first,
                        }
                    )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        self.processes = {identity: proc for identity, proc in self.processes.items() if identity in alive}
        self.process_metadata = {
            pid: metadata for pid, metadata in self.process_metadata.items() if pid in pids
        }
        sample = {
            "kind": "os.sample",
            "timestamp": time.time(),
            "monotonic": time.monotonic(),
            "backend": self.mode,
            "source": "psutil",
            "process_metadata_refresh_seconds": self.metadata_refresh_seconds,
            "process_discovery": "PID list every sample; new PIDs classified immediately; stable metadata refreshed periodically; matched PID reuse checked each sample",
            "processes": rows,
            "scope": "runner and all matching app processes; includes unrelated app sessions",
            "cpu_first_sample_may_be_zero": True,
        }
        if self.mode == "macos" and platform.system() == "Darwin":
            try:
                import Quartz as Q

                sample["input_counters"] = {
                    name: int(
                        Q.CGEventSourceCounterForEventType(Q.kCGEventSourceStateCombinedSessionState, kind)
                    )
                    for name, kind in (
                        ("key_down", Q.kCGEventKeyDown),
                        ("mouse_down", Q.kCGEventLeftMouseDown),
                        ("scroll", Q.kCGEventScrollWheel),
                    )
                }
                sample["input_scope"] = "entire login session, cumulative; not attributable solely to agent"
            except Exception as exc:
                sample["input_unavailable"] = str(exc)
            snapshot = self.foreground_snapshot
            sample["foreground_source"] = "NSWorkspace.main_run_loop"
            if snapshot is None or snapshot[1] is None:
                sample["foreground_status"] = "unavailable"
                sample["foreground_unavailable"] = snapshot[2] if snapshot else "Monitor not started"
            else:
                age = max(0, time.monotonic() - snapshot[0])
                sample["foreground_age_seconds"] = age
                sample["foreground_status"] = "observed" if age <= max(1, self.interval * 2) else "stale"
                if sample["foreground_status"] == "observed":
                    sample["foreground"] = dict(snapshot[1])
        return sample

    def _run(self):
        with self.path.open("a") as stream:
            while not self.stopped.is_set():
                try:
                    sample = self._sample()
                except Exception as exc:
                    sample = {"kind": "collector.error", "timestamp": time.time(), "error": str(exc)}
                stream.write(json.dumps(sample) + "\n")
                stream.flush()
                self.stopped.wait(self.interval)

    def stop(self):
        self.stopped.set()
        if self.foreground_task:
            self.foreground_task.get_loop().call_soon_threadsafe(self.foreground_task.cancel)
        if self.thread:
            self.thread.join(timeout=5)


def export_audit(store, path):
    store.flush_events()
    with path.open("w") as stream:
        for row in store.db.execute("SELECT * FROM events ORDER BY seq"):
            # body is already validated JSON at insertion. Preserve it without decode/re-encode.
            stream.write(
                f'{{"seq":{row["seq"]},"timestamp":{row["time"]},'
                f'"kind":{json.dumps(row["kind"])},"body":{row["body"]}}}\n'
            )


def metrics(store, telemetry_path):
    store.flush_events()
    timing, intervals, old_intervals = {}, [], []
    action_types, units = Counter(), Counter()
    handoffs = calls = input_tokens = output_tokens = dispatches = 0
    for row in store.db.execute("SELECT kind,body FROM events"):
        kind, body = row["kind"], json.loads(row["body"])
        if kind == "timing":
            category = body["category"]
            timing[category] = timing.get(category, 0) + body["elapsed_seconds"]
            if category == "behaviour.typing":
                old_intervals.append(body["requested_seconds"])
        elif kind == "input.dispatched":
            dispatches += 1
            if body.get("requested_onset_interval_seconds") is not None:
                intervals.append(body["requested_onset_interval_seconds"])
            if "hold_elapsed_seconds" in body:
                timing["behaviour.key_hold"] = (
                    timing.get("behaviour.key_hold", 0) + body["hold_elapsed_seconds"]
                )
        elif kind == "action.verified":
            action_types[body["kind"]] += 1
            units[body["kind"]] += body.get("semantic_units", 1)
        elif kind == "handoff.committed":
            handoffs += 1
        elif kind == "model.call":
            calls += 1
            input_tokens += body.get("input_tokens", 0)
            output_tokens += body.get("output_tokens", 0)
    intervals = intervals or old_intervals
    bins = Counter(int(value / 0.025) for value in intervals)
    entropy = (
        -sum((n / len(intervals)) * math.log2(n / len(intervals)) for n in bins.values()) if intervals else 0
    )
    peaks = {
        "peak_combined_app_rss_bytes": 0,
        "peak_combined_cpu_percent": 0,
        "runner_peak_rss_bytes": 0,
        "runner_peak_cpu_percent": 0,
    }
    samples = incomplete = 0
    if telemetry_path.exists():
        with telemetry_path.open() as stream:
            for line in stream:
                try:
                    sample = json.loads(line)
                except json.JSONDecodeError:
                    incomplete += 1
                    continue
                if sample.get("kind") != "os.sample":
                    continue
                samples += 1
                processes = sample["processes"]
                peaks["peak_combined_app_rss_bytes"] = max(
                    peaks["peak_combined_app_rss_bytes"], sum(p["rss_bytes"] for p in processes)
                )
                peaks["peak_combined_cpu_percent"] = max(
                    peaks["peak_combined_cpu_percent"], sum(p["cpu_percent"] for p in processes)
                )
                for process in processes:
                    if process.get("runner"):
                        peaks["runner_peak_rss_bytes"] = max(
                            peaks["runner_peak_rss_bytes"], process["rss_bytes"]
                        )
                        peaks["runner_peak_cpu_percent"] = max(
                            peaks["runner_peak_cpu_percent"], process["cpu_percent"]
                        )
    rows = {
        r["status"]: r["n"] for r in store.db.execute("SELECT status,COUNT(*) n FROM actions GROUP BY status")
    }
    return {
        "actions_by_status": rows,
        "handoffs": handoffs,
        "verified_action_types": dict(action_types),
        "semantic_units_by_action": dict(units),
        "verified_cell_edits": units["set_cell"] + units["set_cells"],
        "gui_save_count": action_types["set_cell"]
        + action_types["set_cells"]
        + action_types["write_document"],
        "input_dispatch_count": dispatches,
        "typing_requested_interval_cv": statistics.pstdev(intervals) / statistics.mean(intervals)
        if intervals and statistics.mean(intervals)
        else 0,
        "typing_requested_entropy_bits_25ms_bins": entropy,
        "typing_timing_note": "Requested onset intervals (legacy runs: post-key gaps); independent OS input observations are separate evidence.",
        "timing_seconds": timing,
        "model_calls": calls,
        "model_input_tokens": input_tokens,
        "model_output_tokens": output_tokens,
        "os_samples": samples,
        "telemetry_incomplete_lines": incomplete,
        **peaks,
        "evaluation_note": "Measured diagnostics, not a benchmark authenticity score.",
    }
