from __future__ import annotations

import argparse
import asyncio
import json
import platform
import shutil
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from .authority import AuthorityManager
from .desktop import MacDesktop, SimulationDesktop
from .fixture import Catalog
from .models import Settings
from .runtime import Runtime
from .store import Store
from .telemetry import TelemetryCollector, export_audit, metrics


def progress_event(kind, body):
    if kind == "handoff.committed":
        packet = body["packet"]
        print(
            json.dumps(
                {
                    "event": "handoff",
                    "from": packet["sender"],
                    "to": packet["receiver"],
                    "reason": packet["reason"],
                    "resume_at": packet["resume_at"],
                }
            ),
            flush=True,
        )
    elif kind in ("action.verified", "action.retry", "action.uncertain", "workflow.failed"):
        print(json.dumps({"event": kind, **body}), flush=True)


@contextmanager
def desktop_lock(directory):
    # Per-login-user lock across all run databases. The OS releases it on process death.
    if platform.system() == "Windows":
        raise RuntimeError("Windows executor is not supported in this MVP")
    import fcntl

    # TMPDIR may differ between Terminal/Codex: every launcher must use the same per-user path.
    lock_path = Path.home() / ".cache" / "synthetic-human-agent" / "desktop.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as stream:
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("another Synthetic Human runtime owns the desktop") from None
        try:
            stream.seek(0)
            stream.truncate()
            stream.write(str(directory))
            stream.flush()
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def doctor(settings):
    result = {
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "backend": settings.backend,
        "checks": {},
        "ready": True,
    }
    if settings.backend == "simulation":
        result["checks"] = {
            "desktop": "not used",
            "telemetry": "runner/app OS samples only; no real agent input",
        }
        return result
    if platform.system() != "Darwin":
        result.update(ready=False, checks={"platform": "macos backend requires macOS"})
        return result
    try:
        import ApplicationServices as AX
        import Quartz

        result["checks"]["accessibility"] = bool(AX.AXIsProcessTrusted())
        result["checks"]["screen_recording"] = bool(Quartz.CGPreflightScreenCaptureAccess())
        result["checks"]["input_monitoring"] = bool(Quartz.CGPreflightListenEventAccess())
        result["ready"] &= result["checks"]["accessibility"]
    except ImportError as exc:
        result["checks"]["desktop_dependencies"] = str(exc)
        result["ready"] = False
    for name in (settings.browser_app, settings.office_app):
        found = any(
            (root / f"{name}.app").exists() for root in (Path("/Applications"), Path.home() / "Applications")
        )
        if not found:
            # Spotlight lookup is read-only and supports nonstandard installation paths.
            lookup = subprocess.run(
                ["mdfind", f"kMDItemFSName == '{name}.app'"], capture_output=True, text=True, timeout=10
            )
            found = bool(lookup.stdout.strip())
        result["checks"][name] = found
        result["ready"] &= found
    result["checks"]["ocr"] = shutil.which("tesseract") or "not installed (optional screenshot OCR helper)"
    return result


async def execute(settings, directory, resume=False):
    from .workflow import Workflow

    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "evidence").mkdir(exist_ok=True)
    exists = (directory / "state.sqlite").exists()
    if exists != resume:
        raise RuntimeError("use --resume for an existing run; omit it for a new directory")
    check = doctor(settings)
    if not check["ready"]:
        raise RuntimeError("desktop preflight failed: " + json.dumps(check))
    with desktop_lock(directory):
        store = Store(directory / "state.sqlite")
        store.event_sink = progress_event
        collector = None
        recorder = None
        try:
            prior = store.get("settings")
            if prior and prior["backend"] != settings.backend:
                raise RuntimeError("cannot change backend on an existing run")
            store.put("settings", settings.model_dump())
            if resume:
                # Exclusive OS lock proves no previous CLI executor is alive. Fence every previous command.
                store.db.execute(
                    "UPDATE authority SET epoch=epoch+1,lease=NULL,lease_until=0 WHERE singleton=1"
                )
            backend = MacDesktop(settings) if settings.backend == "macos" else SimulationDesktop(settings)
            authority = AuthorityManager(store, settings)
            runtime = Runtime(store, authority, backend, settings, directory)
            collector = TelemetryCollector(
                directory / "telemetry.jsonl", settings.backend, settings.sample_interval
            )
            collector.start()
            if settings.backend == "macos":
                from .input_recorder import InputRecorder

                recorder = InputRecorder(directory / "inputs.jsonl")
                recorder.start()
            port = store.get("catalog_port", 0)
            with Catalog(port) as catalog:
                store.put("catalog_port", urlparse(catalog.url).port)
                store.put("catalog_url", catalog.url)
                print(
                    json.dumps(
                        {
                            "status": "running",
                            "backend": settings.backend,
                            "directory": str(directory),
                            "catalog": catalog.url,
                        }
                    ),
                    flush=True,
                )
                outcome = await Workflow(runtime, catalog.url).run()
            collector.stop()
            if recorder:
                recorder.stop()
            export_audit(store, directory / "audit.jsonl")
            summary = metrics(store, directory / "telemetry.jsonl")
            summary.update(
                backend=settings.backend,
                outcome=outcome,
                real_desktop_verified=settings.backend == "macos" and outcome.get("status") == "completed",
                simulation_artifacts=settings.backend == "simulation",
            )
            if recorder:
                from .evaluation import read_inputs

                observation = read_inputs(directory / "inputs.jsonl")
                summary["input_observation"] = {
                    key: value for key, value in observation.items() if key != "features"
                }
            (directory / "metrics.json").write_text(json.dumps(summary, indent=2))
            (directory / "settings.json").write_text(settings.model_dump_json(indent=2))
            print(json.dumps(summary, indent=2))
            return 0 if outcome.get("status") == "completed" else 1
        finally:
            if recorder:
                recorder.stop()
            if collector:
                collector.stop()
            export_audit(store, directory / "audit.jsonl")
            store.close()


async def capture_human(directory, seconds):
    from .input_recorder import InputRecorder

    if not 10 <= seconds <= 3600:
        raise ValueError("recording duration must be 10..3600 seconds")
    directory.mkdir(parents=True, exist_ok=False)
    with desktop_lock(directory):
        recorder = InputRecorder(directory / "inputs.jsonl", role="human")
        collector = TelemetryCollector(directory / "telemetry.jsonl", "macos")
        try:
            if not recorder.start():
                raise RuntimeError(f"cannot record baseline: {recorder.reason}")
            collector.start()
            print(
                f"Recording metadata only for {seconds}s. Perform the same office task manually; Ctrl+C to stop.",
                flush=True,
            )
            await asyncio.sleep(seconds)
        finally:
            recorder.stop()
            collector.stop()


def main():
    parser = argparse.ArgumentParser(description="Synthetic Human Agent — bounded three-product desktop demo")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("run", "doctor"):
        item = sub.add_parser(command)
        item.add_argument("--config", type=Path, default=Path("configs/demo.json"))
        item.add_argument("--backend", choices=("simulation", "macos"))
        if command == "run":
            item.add_argument("--output", type=Path)
            item.add_argument("--resume", action="store_true")
    inspect = sub.add_parser("inspect")
    inspect.add_argument("run", type=Path)
    assessment = sub.add_parser(
        "assess", help="check evidence for the requested activities and timing features"
    )
    assessment.add_argument("run", type=Path)
    assessment.add_argument("--output", type=Path)
    ocr = sub.add_parser("ocr", help="read an existing checkpoint screenshot with optional tesseract")
    ocr.add_argument("image", type=Path)
    bench = sub.add_parser("benchmark", help="repeat core simulation in fresh subprocesses")
    bench.add_argument("--output", type=Path, required=True)
    bench.add_argument("--runs", type=int, default=9)
    comparison = sub.add_parser("compare", help="compare independently observed agent/human input streams")
    comparison.add_argument("--agent", type=Path, required=True)
    comparison.add_argument("--human", type=Path, required=True)
    comparison.add_argument("--output", type=Path)
    human = sub.add_parser("capture-human", help="passively record a manual baseline; never sends input")
    human.add_argument("--output", type=Path, required=True)
    human.add_argument("--seconds", type=int, default=180)
    args = parser.parse_args()
    try:
        if args.command == "assess":
            from .assessment import assess

            result = assess(args.run)
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(result, indent=2))
            print(json.dumps(result, indent=2))
            return
        if args.command == "benchmark":
            from .benchmark import benchmark

            result = benchmark(args.output, args.runs)
            print(json.dumps({key: value for key, value in result.items() if key != "runs"}, indent=2))
            return
        if args.command == "compare":
            from .evaluation import compare

            result = compare(args.agent, args.human)
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(result, indent=2))
            print(json.dumps(result, indent=2))
            return
        if args.command == "capture-human":
            asyncio.run(capture_human(args.output, args.seconds))
            return
        if args.command == "inspect":
            if not (args.run / "state.sqlite").exists():
                raise FileNotFoundError(f"run database does not exist: {args.run}")
            store = Store(args.run / "state.sqlite", readonly=True)
            try:
                print(
                    json.dumps(
                        {
                            "authority": AuthorityManager(store, Settings()).current(),
                            "continuation": store.get("continuation"),
                            "uncertain": store.uncertain(),
                            "verification": store.get("verification"),
                            "metrics": metrics(store, args.run / "telemetry.jsonl"),
                        },
                        indent=2,
                    )
                )
            finally:
                store.close()
            return
        if args.command == "ocr":
            if not shutil.which("tesseract"):
                raise RuntimeError("optional OCR requires tesseract (brew install tesseract)")
            subprocess.run(["tesseract", str(args.image.resolve()), "stdout"], check=True)
            return
        settings = (
            Settings.model_validate_json(args.config.read_text()) if args.config.exists() else Settings()
        )
        if args.backend:
            settings = Settings.model_validate({**settings.model_dump(), "backend": args.backend})
        if args.command == "doctor":
            result = doctor(settings)
            print(json.dumps(result, indent=2))
            raise SystemExit(0 if result["ready"] else 1)
        output = args.output or Path("runs") / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        if args.resume and not args.output:
            raise ValueError("--resume requires --output pointing at the existing run")
        raise SystemExit(asyncio.run(execute(settings, output, args.resume)))
    except KeyboardInterrupt:
        if args.command == "capture-human":
            print("Baseline recording stopped; observed metadata saved.", file=sys.stderr)
        else:
            print("Interrupted. Inspect and reconcile the saved run before resuming.", file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
