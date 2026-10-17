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

Do not present a simulation recording as live GUI evidence. This repository includes a runnable
simulation and recording instructions. A desktop video has **not** been produced: the latest
preflight has Accessibility/Input Monitoring but Screen Recording remains unavailable. Use
Cmd+Shift+5 to record a new full run after enabling screen capture for the launcher.

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
passed both Ubuntu/Python **3.11 and 3.14** jobs: 53 tests, lint and format checks. The final
follow-up changes only document this result and do not alter tested source code.

Place the repository URL and your separately recorded video URL in the submission. Evaluators
need access to the private repository or a visibility change made by its owner. No video was
recorded during this task because Screen Recording remained unavailable.

## Suggested narration

“The controller delegates task authority according to expertise. Browser and Office hand off
directly with versioned data and a resume point. Workers return plans without taking authority.
The runtime grants one desktop lease, checks each input's epoch/token, and verifies saved output.
A shared persona controls context-dependent timing. Independent OS samples are kept separately
from action logs. Unknown mutation outcomes are reconciled before retrying.”
