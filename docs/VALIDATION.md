# Validation record

Date: **2026-10-17**, client timezone Asia/Singapore. Environment: macOS 26.4 ARM64,
Python 3.14.6. Dependency versions are recorded in `uv.lock`.

## Executed successfully

```text
uv sync --locked --extra dev --extra desktop
pytest -q                         62 passed
ruff check src tests scripts      All checks passed
ruff format --check src tests scripts  43 files already formatted
sha run --output runs/final-optimized-demo
sha inspect runs/final-optimized-demo
sha run --output runs/final-optimized-demo --resume
```

Optimized simulation completed with **22 verified actions**, **5 authority handoffs**, zero unresolved
actions, and final source/file consistency checks passing. The action mix was 4 navigations,
4 scroll actions, 4 page reads, 3 link activations, 2 file opens, 4 row edits (20 cells), and 1 report edit.
The completed-run resume reverified artifacts without executing additional desktop operations.
Default policy used zero model calls. Simulation skips wall-clock behavioural sleeps.

The test suite covers:

- Committed handoff updates owner/epoch/continuation and re-observes as receiver.
- Rejected acceptance, stale input, changed data/file versions, and held/expired lease rejection.
- Waiting for the current action to drain; no-progress escalation; global desktop lock exclusion.
- Rechecking authority between individual input events and rejecting wrong-document focus.
- Duplicate operation IDs, lost acknowledgments after save, restart reconciliation, and unresolved input.
- Emergency STOP before input and detection of changed/deleted output or source evidence.
- Missing-information Browser ↔ Office handoff with the correct continuation, complete file workflow,
  formula/calculated-value checks, and exact report/source consistency.
- Context-dependent timing variation, corrected prose typos, and command/formula typing integrity.
- Model HTTP/schema/token-accounting contract using a local fake server, including invalid-role rejection.
- Validation of externally extracted values against Product schema constraints.
- Row-level intent/postcondition checks after lost acknowledgments, persistent persona RNG,
  protected URLs/emails, cancellation-safe key release, trace batch ordering and empirical-distance math.
- Incomplete/mislabeled telemetry rejection; no fabricated input when native permission is absent.
- Whole-workflow variants with reordered products, decimal prices, tied prices, zero/long warranties
  and wide price ranges; report/formulas use the actually observed values.
- Activity-checklist evidence never promotes simulation to native GUI; changed output and missing
  pause evidence are detected. A separate realtime engine-only test verifies actual context waits.

Fresh-process benchmark raw trials and measured reductions are in [OPTIMIZATION.md](OPTIMIZATION.md).
Benchmark success is not evidence of live GUI or human authenticity. The original implementation
completed the same task with 38 logical actions; row batching reduces action/save overhead while
retaining all 20 cell edits and every final verification criterion.

## First native desktop result (before Screen Recording grant)

```text
Google Chrome:     installed
LibreOffice:       26.8.1.1 installed
Accessibility:     granted
Screen Recording:  not granted (optional screenshots/video unavailable)
Input Monitoring:  granted
Desktop ready:     true
```

`runs/desktop-native-final` completed the full workflow through real GUI input: **22 verified
actions, 5 handoffs, 20 cells, 3 native recalculated formulas and 1 report**. All source, value,
formula and report checks passed. Four scrolls moved matching AX content anchors by -45 px
relative to the viewport; three links were activated with real mouse clicks. Native input
recording had zero gaps, errors, dropped events or invalid timestamps. Four corrected typos
were observed and final prose matched exactly. The requested activity checklist passed **7/7**.

The passive recording window lasted 160.31 seconds. Native inter-key median was 123.99 ms,
p95 393.75 ms and CV 0.645 (833 active intervals); hold median was 55.25 ms. These describe
one run, not similarity to a human population. Python peaked at 127.58 MiB RSS and sampled
12.5% CPU; default policy used zero model calls/tokens. All-app RSS includes unrelated sessions.

A subsequent completed-run restart independently reverified the files with the dispatch count
unchanged at **1092**: no repeated editing. Evidence, actual files and provenance are in
[examples/native](../examples/native/README.md). The GUI ran across two monitors, with Chrome
at negative X coordinates and LibreOffice on the primary display.

Development failures are retained locally and summarized in the native record: initial focus
activation/cache issues, onboarding dialogs and incompatible keyboard delivery. The retained
fixes advance the Cocoa run loop for focus reads, enforce full AXDocument URLs, use bounded
Supervisor recovery, and send private-source Quartz keys with explicit flags and matching
physical/text data. Unit tests verify release of keys/modifiers on cancellation/error.
The final successful run does not erase earlier failed attempts or establish a success rate.

## Screen Recording follow-up (executed)

After the user's permission change, all three checks passed. Native screenshots were captured,
and `runs/recorded-native-demo-final` completed with **22 verified actions and 7/7 activity checks**
while recording the display. The finalized native MOV and exported MP4 both have duration
189.998 seconds at 1920×1080. Four actual video frames were reviewed across browser, Calc,
Writer typing and the completed report. Export preserved full duration and requested no audio.

The local MP4 is `dist/synthetic-human-agent-demo.mp4`; metadata/digests and the recorded run's
measurements are in `examples/recorded-demo/`. An earlier capture was discarded when stopped
with SIGINT, although its workflow passed. The retained helper now waits for normal timed
recorder completion. The original no-video run above remains labelled with its original grants.

## LibreOffice engine compatibility (executed after installation)

LibreOffice reports `26.8.1.1 bf6ef2662401c7d6dce671ab4deb26ee0af3a7c1`.
Using a separate profile and `--headless --convert-to`:

- Both empty ODS/ODT templates opened and saved successfully.
- The populated comparison and report opened and saved successfully.
- All 20 spreadsheet cells were checked after the native round trip, with zero mismatches.
- LibreOffice recalculated the three tax formulas to 129.6, 102.6 and 156.6.
- Report text was preserved exactly.

This verifies native file/engine compatibility, not GUI automation or human-like telemetry.
Results are saved in `examples/libreoffice-validation/verification.json`; full conversion
logs and outputs remain in the ignored local `runs/libreoffice-validation/` folder.
The running process ancestry identifies Visual Studio Code as the launcher; its
Accessibility and Input Monitoring grants are now available. Screen capture was unavailable
at that stage; it has since been granted and validated in the recorded-demo follow-up above.

## Not executed or not implemented

- No population-level human benchmark or calibrated authenticity score; the single-person comparison is recorded below.
- No real-model inference session; the Ollama-compatible gateway was tested against a local stub.
- Repository publication, recording artifacts and CI execution are recorded in the submission notes.
- No Microsoft Office, Pages/Numbers, Windows/Linux native GUI adapter or arbitrary website parser.
- No automatic OCR target grounding, full kernel/network event tracing, advanced document formatting
  or GUI DOCX/XLSX export. Optional OCR reads an existing screenshot via a separate helper command.

The passive input recorder ran on the native desktop. Baseline comparison math and missing-
permission behavior were tested with explicitly labelled fixtures. A later manual reference is described below.

Remote CI passed on Ubuntu with Python 3.11 and 3.14: 53 tests plus lint/format checks
on both jobs. See the linked run in `docs/DEMO.md`. Files under `examples/simulation/` were generated by the
test double; files under `examples/native/` were typed and saved through the GUI. OS samples
are independently measured in both bundles and do not assign all matching app activity to the agent.

## Comparison quality follow-up

A real user ran compare before capture-human had stopped. The former evaluator accepted the
sample count without checking closure. The updated evaluator requires balanced, valid recording
start/stop events and rejects truncated/live traces; it preserves descriptive statistics for
diagnostics but does not return distances for insufficient evidence. Regression tests cover live
captures, partial JSON, valid resumed sessions, missing earlier stops, repeat correction accounting
and shortcut-separated input silence. At that stage, the full local suite passed **58 tests**, with lint and
format checks passing across source, tests and scripts. Human traces remain in ignored `runs/`;
no raw personal baseline was added to the repository.

## Human-05 descriptive comparison (executed)

The manual capture has a closed start/stop lifecycle and no reported gaps, dropped events,
recorder errors or invalid timestamps. Its 304.704-second capture window is not independently
verified task-only completion time. The user reports completing browsing, Calc and Writer;
manual output correctness and identical workload/text were not independently verified.

`sha compare` ran against the retained `recorded-native-demo-final` trace. Active inter-key
medians are 122.487 vs 151.252 ms (agent vs human); key-hold medians are 55.055 vs 86.960 ms,
with key-hold KS 0.744. These differences do not establish a close match. There are only four
vs five input-silence samples. All 581 human foreground samples report Code; potentially stale
passive focus labels are excluded from dwell/task-completion interpretation.

Human typing and task-solving strategies vary across people and sessions. One participant's
trace is an exploratory individual reference, not a universal baseline or competition grade.
No timings were modified or persona parameters tuned for this report. Human-04 is not pooled
or counted as another participant. The 30/30/20/20 weighted score remains null.

Original input and OS files are unchanged and byte-identical local snapshots have SHA256
manifests. Published [aggregates](../examples/human-05-benchmark/README.md) exclude raw human
coordinates/process records; the full [English report](HUMAN_05_BENCHMARK.md) retains limitations.
The agent's saved outputs were rechecked: all seven activity checks pass, separately from similarity.

The report/archive utility is tested for exact-byte preservation, source hashes, unscored
variability warnings, active-capture rejection, overwrite prevention, aggregate-only export,
and exclusion of initial CPU samples. The full suite passes **62 tests**; lint and format checks
pass across **43 Python files**. These checks validate software/reporting, not general human likeness.
