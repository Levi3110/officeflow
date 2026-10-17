# Demo and submission

## GUI recording (suggested 4–6 minutes)

1. Show `sha doctor --backend macos`, config, app versions and `git rev-parse HEAD` after committing.
2. Start screen recording using macOS Cmd+Shift+5. Keep the terminal, Chrome and LibreOffice visible.
3. Run `uv run --extra desktop sha run --backend macos --output runs/video-demo`.
4. Show the catalog browsing and detail links. Explain the five handoffs:
   Supervisor → Browser → Office → Browser → Office → Supervisor.
5. Show Office asking for missing warranty data in `sha inspect runs/video-demo` from another
   terminal, or inspect the final audit after completion. The runtime may finish some phases
   too quickly for manual inspection; audit contains their persisted records.
6. Show actual Calc cell entry, calculated tax-inclusive values and Writer typing/corrections.
   Keep the complete uncut task recording as evidence; a shorter narrated cut can be submitted too.
7. Show `metrics.json`, the final saved files, source evidence and `telemetry.jsonl`. Explain
   which measurements are independent OS samples and which are audit/dispatch diagnostics.
   If Input Monitoring is enabled, also show `inputs.jsonl`, coverage metadata and a comparison
   against a separately recorded manual baseline. Missing baseline leaves the score unassigned.
8. Show the relevant tests with `uv run pytest -q`. State supported apps and current limitations.

Do not present a simulation recording as live GUI evidence. Accessibility, Input Monitoring
and Screen Recording are now granted on the development machine, and a real screenshot was
captured successfully after the latest permission change.

## Delivered local video

The complete verified demo is `dist/synthetic-human-agent-demo.mp4` (189.998 seconds, 1080p).
The original MOV is `runs/recorded-native-demo-final/demo.mov`. Four sampled frames were visually
checked; the full recorded workflow and output files passed. Metadata, digests and selected
verification results are in [`examples/recorded-demo/`](../examples/recorded-demo/README.md).

## Automated local recording

Put Chrome and LibreOffice on the selected display before starting. The script records the
actual desktop and invokes the existing runtime; it does not synthesize demonstration frames.

```bash
uv run --extra desktop python scripts/record_demo.py --output runs/recorded-demo --seconds 190
swift scripts/video_artifact.swift runs/recorded-demo/demo.mov dist/my-demo.mp4 runs/recorded-demo/video-qa
```

The first command records display 1 by default; `--display 2` selects display 2. Leave input
idle for the entire requested duration. Use a new run directory and an unused MP4 filename.
The duration must exceed workflow time, including startup. The recording includes a final
static hold if the task finishes early. It stops normally using `screencapture -V`; on this
macOS version, stopping early with SIGINT discarded the movie, so the helper waits for normal
completion. Ctrl+C cancels the task and recording rather than producing a usable full video.

The Swift helper uses the native AVFoundation exporter, preserves the full duration, writes
MP4 and samples four frames for visual review. It also writes duration/resolution/size metadata.
It requires the macOS command-line developer tools. No microphone/audio capture is requested.
Raw movies, screenshots and frames stay in ignored `runs/`/`dist/` folders; they are not pushed
with source code. Select and submit the reviewed video separately.

## Four-criterion evidence report

The [four-criterion benchmark](FOUR_CRITERIA_BENCHMARK.md) documents Process Telemetry Authenticity
30%, Human Entropy & Timing 30%, Complexity 20% (Secondary) and Resource Efficiency 20% (Primary).
Use `sha evaluate` with closed native/manual recordings and a fresh `sha benchmark` core batch.
Submit the report with the demonstration; do not present its functional checklist or simulation
core timings as a calibrated competition score. Raw human input/OS traces stay local.

## GitHub handoff

Source, lockfile, tests, config, documentation and labelled simulation/native evidence are
committed and pushed to [Levi3110/synthetic-human-agent](https://github.com/Levi3110/synthetic-human-agent).
Visibility is **private**. Review it before changing visibility or inviting evaluators. The ignored
`runs/` folders retain development checkpoints; selected native evidence is in `examples/native/`.

```bash
gh repo clone Levi3110/synthetic-human-agent
cd synthetic-human-agent
uv sync --locked --extra dev
uv run pytest -q
```

[CI run 39020181384](https://github.com/Levi3110/synthetic-human-agent/actions/runs/39020181384)
passed both Ubuntu/Python **3.11 and 3.14** jobs: 53 tests, lint and format checks.
[CI run 39021741456](https://github.com/Levi3110/synthetic-human-agent/actions/runs/39021741456)
also passed both jobs after adding the recording helpers and their lint/format checks.
The recording/export helpers were additionally executed and verified on macOS.

Place the repository URL and your separately recorded video URL in the submission. Evaluators
need access to the private repository or a visibility change made by its owner. The original native example predates the Screen Recording grant; the new recording workflow
and its local artifacts are documented above.

## Suggested narration

“The controller delegates task authority according to expertise. Browser and Office hand off
directly with versioned data and a resume point. Workers return plans without taking authority.
The runtime grants one desktop lease, checks each input's epoch/token, and verifies saved output.
A shared persona controls context-dependent timing. Independent OS samples are kept separately
from action logs. Unknown mutation outcomes are reconciled before retrying.”
