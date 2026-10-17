# Verified native GUI demonstration

Executed on 2026-10-17 on macOS 26.4 ARM64, Python 3.14.6, Google Chrome and LibreOffice
26.8.1.1. The launcher was Visual Studio Code. Accessibility/Input Monitoring were granted;
Screen Recording was unavailable during this original run. This folder contains actual GUI-produced ODS/ODT files,
independent OS/input measurements and the recorded assessment. No native content was written
through an Office API, document generator, clipboard paste or headless conversion. Code created
only empty seed documents; all task content was typed through the desktop executor.

## Outcome

- 22 verified logical actions; 5 committed expertise handoffs; zero unresolved actions.
- 4 navigations, 4 reads, 3 real mouse link activations, 4 verified scrolls.
- 20 Calc cells across 4 row edits; 3 formulas recalculated to 129.6, 102.6, 156.6.
- Writer report matches verified product/source data exactly; 5 GUI saves total.
- Checklist: **7/7** requested activities, not a calibrated competition grade.
- Four corrected typing errors; native active inter-key median 123.99 ms, p95 393.75 ms,
  CV 0.645; hold median 55.25 ms. No human baseline or authenticity percentage.
- Independent passive recording window: 160.31 seconds; 896 key-down/up pairs, 10 wheel
  events, 3 mouse click pairs; zero gaps, errors, drops or invalid timestamps.
- Source PID 89450 accounts for all keys/clicks/wheel events. Three pointer moves report PID 0;
  see `provenance.json`. Input metadata contains no characters or raw key codes.
- Runner peak RSS 127.58 MiB; sampled CPU peak 12.5%; zero model calls/tokens. App totals
  include existing unrelated Chrome/LibreOffice sessions, including development windows.
- Restart reverified final artifacts with input dispatch count unchanged at 1092. It did not retype.

Chrome ran on a secondary monitor with negative X coordinates; Office ran on the primary
monitor. Each scroll was grounded inside the web area; matching AX content positions moved
-45 px relative to that viewport. This excludes merely moving the app window as evidence.

## Files

`metrics.json` preserves the first completed run's summary. `resume-metrics.json`, the full
audit and telemetry also include the subsequent no-edit restart verification. `inputs.jsonl`
contains native observations and recorder lifecycle records. `settings.json` is the actual
configuration. `evidence/` contains selected page text, source URLs, digests and AX observations.
`activity-assessment.json` rechecks correctness before granting activity credit.

The original database/checkpoints remain locally in `runs/desktop-native-final/`; this selected
bundle has no database and is **not a resumable run**. To reproduce, use a new run directory:

```bash
uv sync --locked --extra desktop --extra dev
uv run --extra desktop sha doctor --backend macos
uv run --extra desktop sha run --backend macos --output runs/my-native-demo
uv run sha assess runs/my-native-demo
```

The demo catalog uses fictional products served on localhost. Its source links are reachable
only while the run's fixture server is active. It does not demonstrate arbitrary site/search
support. No Microsoft Office, advanced formatting, GUI XLSX/DOCX export, native non-English
input or real LLM planning was validated. This original run has no video; a subsequent
Screen Recording grant enabled the recording workflow in `docs/DEMO.md`.

## Development failures and fixes

Earlier attempts remain in ignored local run directories. They failed before or during Office
editing because of stale focus/activation state, first-launch dialogs, or incompatible keyboard
delivery. Some attempts also had external mouse activity; `desktop-clean-session` reproduced
the keyboard failure without external input, so external activity was not its sole cause.

Retained fixes: advance the Cocoa run loop for fresh foreground reads; identify documents by
full AXDocument URI; explicitly set Quartz event source, text, matching key code and modifier
flags; always release keys/modifiers; dismiss only the recognized Tip of the Day dialog;
recover read/open failures with a bounded Supervisor budget. Ambiguous edits remain blocked.
A private scratch sheet validated both the complete header and decimal/formula typing before
the final successful whole-workflow run. This record does not claim a repeated success rate.
