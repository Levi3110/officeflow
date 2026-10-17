"""Record one real GUI workflow on macOS; place Chrome/Office on the selected display first."""

import argparse
import asyncio
import json
import time
from pathlib import Path

from synthetic_human.cli import doctor, execute
from synthetic_human.models import Settings


async def record(args):
    settings = Settings.model_validate_json(args.config.read_text())
    settings = Settings.model_validate({**settings.model_dump(), "backend": "macos"})
    check = doctor(settings)
    if not check["ready"] or not check["checks"].get("screen_recording"):
        raise RuntimeError("Desktop and Screen Recording access are required; run sha doctor --backend macos")
    directory = args.output.resolve()
    if directory.exists():
        raise FileExistsError("Use a new output directory so recording cannot overwrite an earlier run")
    directory.mkdir(parents=True)
    video = directory / "demo.mov"
    with (directory / "recording.log").open("wb") as log:
        capture = await asyncio.create_subprocess_exec(
            "screencapture",
            "-v",
            "-D",
            str(args.display),
            "-V",
            str(args.seconds),
            str(video),
            stdout=log,
            stderr=log,
        )
        started = time.monotonic()
        (directory / "recording-session.json").write_text(
            json.dumps(
                {
                    "started_unix_seconds": time.time(),
                    "requested_seconds": args.seconds,
                    "display": args.display,
                }
            )
        )
        try:
            await asyncio.sleep(1)
            if capture.returncode is not None:
                raise RuntimeError("Screen recorder stopped early; inspect recording.log")
            result = await execute(settings, directory)
            if capture.returncode is not None:
                raise RuntimeError("Recording stopped before the workflow finished")
            # screencapture discards the recording on SIGINT on this macOS version.
            # Let its duration timer stop normally so it finalizes the movie.
            remaining = max(1, args.seconds + 15 - (time.monotonic() - started))
            await asyncio.wait_for(capture.wait(), timeout=remaining)
            if capture.returncode:
                raise RuntimeError("Screen recorder failed; inspect recording.log")
        finally:
            if capture.returncode is None:
                capture.terminate()
                try:
                    await asyncio.wait_for(capture.wait(), timeout=5)
                except TimeoutError:
                    capture.kill()
                    await capture.wait()
    if not video.exists() or not video.stat().st_size:
        raise RuntimeError("Recorder did not produce a video")
    print(json.dumps({"video": str(video), "bytes": video.stat().st_size, "workflow_exit_code": result}))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--config", type=Path, default=Path("configs/demo.json"))
    parser.add_argument("--display", type=int, default=1)
    parser.add_argument("--seconds", type=int, default=190)
    raise SystemExit(asyncio.run(record(parser.parse_args())))
