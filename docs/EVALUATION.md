# Evaluation protocol

The assignment weights are **Process Telemetry Authenticity 30%, Human Entropy & Timing 30%,
Complexity of Action 20% (Secondary), Resource Efficiency 20% (Primary)**. They are evaluation weights, not scores achieved by
this repository. Simulation validates orchestration and correctness; it cannot validate authenticity.

| Criterion | Evidence implemented | Required evaluation |
| --- | --- | --- |
| Authenticity 30% | Independent process CPU/RSS/threads; I/O if supported; live session counters and passive input-event metadata; file/source evidence | Run real applications and compare OS measurements with consented human sessions |
| Entropy/timing 30% | Shared persisted persona; variable key holds; word-chunk pauses; corrected adjacent-key typos; curved mouse paths; scroll bursts | Compare measured inter-event distributions, burst/idle patterns and app dwell times against humans |
| Complexity 20% | Browsing, link activation, scroll, cross-app workflow, cell/formula editing, report, missing-data handoff | Review successful live task completion and action diversity; inspect errors and artifacts |
| Efficiency 20% | Runner/app CPU and RSS, action timing, model calls/tokens, completion status | Repeat identical scenarios and report medians/p95 plus outcome rates |

## Four-criterion benchmark

Read [FOUR_CRITERIA_BENCHMARK.md](FOUR_CRITERIA_BENCHMARK.md) for the executed four-dimension
report, measured native resources, process diagnostics and all nine new simulation-core trials.
The `Primary`/`Secondary` labels specify emphasis and preserve the supplied weights. The earlier
`sha compare` human-05 report covers input distributions; it is only part of this full rubric.

```bash
uv run sha benchmark --runs 9 --output runs/benchmarks/core-new.json
uv run sha evaluate --agent runs/recorded-native-demo-final --human runs/human-05 --core runs/benchmarks/core-new.json --output runs/benchmarks/rubric-new
```

`evaluate` reads existing evidence and rechecks artifacts without GUI input. `benchmark.json`
contains per-dimension measurements/statuses, source hashes and null grades. `rubric.csv` lists
weights/priorities/statuses; it does not convert observed telemetry into an invented score.
The core-trial batch uses fresh subprocesses and simulation; selected native telemetry remains
a single earlier GUI run with capture/background confounds. Process CPU/RSS/thread distances
compare whole matching app scopes, not isolated task processes or a human population.

## Current exploratory evidence

The [human-05 case study](HUMAN_05_BENCHMARK.md) compares one agent trace with one person's session.
Human behaviour varies both between people and within the same person: typing, deliberate editing,
shortcuts, navigation and task-solving strategy all differ. This is an individual reference, not
an estimate of a universal human distribution. The measured key-hold distributions differ substantially;
no close-match claim, population inference or calibrated weighted score follows. Raw human traces
remain local and published results retain unfavourable findings. Passive foreground samples in
this collection may be stale and are excluded from dwell/completion conclusions.

## Reproducible comparison

For executable manual-collection steps, see [HUMAN_BASELINE.md](HUMAN_BASELINE.md).

1. Use the same machine, app versions, catalog, window layout and initial documents for all runs.
2. Record at least several human runs and several agent runs; document sample counts. Reserve
   separate runs for tuning and evaluation. Avoid recording agent activity while a human uses
   other Chrome windows because process/session counters are shared.
3. Keep the same OS measurement method and sample cadence for both cohorts. The new
   `inputs.jsonl` recorder uses a passive macOS event tap for independent timestamps, key holds
   and pointer/scroll metadata. Use `sha capture-human` for the manual cohort and `sha compare`
   for empirical distances. The action audit remains dispatch timing and is kept separate.
4. Check correctness first: all products, prices, warranties, source evidence, formulas and
   calculated values, and report consistency must pass. Failed sessions still count in the
   completion-rate denominator.
5. Compare empirical distributions of typing/idle intervals, correction frequency, wheel bursts,
   app dwell time, CPU/RSS and task duration. Use KS/Wasserstein or another predeclared statistic;
   preserve units and avoid treating higher entropy as automatically better.
6. Report task success rate and uncertainty intervals along with timing/resource medians and
   p95. A single successful demo is evidence of functionality, not a population benchmark.

`metrics.json` reports requested-onset interval coefficient of variation and Shannon
entropy with 25 ms bins. These help catch constant timing, but do not measure actual hardware
input timing or similarity to humans. Simulation performs no real-time sleep, so its elapsed
timing is deliberately close to zero. `real_desktop_verified` stays false for simulation runs.

The passive recorder requires Input Monitoring and has now run successfully on the native
desktop; see `examples/native/`. Missing access creates a status record, never fabricated input
events. Its bounded queue, tap disablement, parse errors and dropped events are reported;
comparison refuses to mark insufficient/partial streams as a sufficient baseline. Native timestamps
are used for intervals rather than callback arrival time. Recording-role labels distinguish agent
and manual sessions. Actual source/target PIDs are retained where macOS supplies them, but the
session remains global and is not automatically attributable solely to the agent.

`compare` provides descriptive KS and Wasserstein distances, sample counts and medians/p95;
temporally correlated inputs do not justify naive independence-based p-values. Inter-key intervals
up to 2 seconds describe active typing; longer gaps between unmodified keys are reported
separately as legacy `idle_seconds`. Shortcuts reset that sequence; it does not measure every
reading/planning pause. `input_silence_seconds` additionally reports gaps over 2 seconds between
any observed input events inside a session, without inferring their purpose. Modifier
shortcuts and autorepeats are excluded from active typing intervals. At least 30 intervals in
each cohort are required for the comparison status, not a claim of statistical power or authenticity.
For high-confidence conclusions, collect multiple whole sessions from multiple users and evaluate
on held-out sessions. Do not tune toward maximal random entropy: match observed context instead.

CPU percentages can exceed 100% across cores/processes. RSS across processes can double count
shared memory; `runner_peak_*` isolates the Python process. The first `cpu_percent` sample can
be zero. App totals include existing Chrome/LibreOffice sessions. On macOS process I/O may be
null; no replacement values are invented. The first/last OS sample times include collector and
fixture lifecycle overhead and should not be interpreted as pure task time.

The weighted total may be computed only after the evaluator defines calibrated 0–100 scores
for all four dimensions: `0.30*A + 0.30*H + 0.20*C + 0.20*R`. This project does not auto-generate
an authenticity percentage from command logs or random delays.

A completed start/stop lifecycle is required before comparison. Active captures, truncated JSON,
misordered lifecycle records or events outside a session return `insufficient_evidence` with
explicit reasons and null distances. Previously, enough intervals in a still-active capture could
receive `descriptive_comparison`; the lifecycle gate corrects that false acceptance. Resumed
recordings with separately closed sessions remain supported.

A technically complete stream can still contain off-task activity. End manual capture before
invoking compare or reading its output. Correction events are Backspace/Delete actions, not
proven typos; autorepeats are counted separately. Event-wise pointer velocity is sensitive to
sampling cadence, so raw movement counts or mean speed should not be directly fitted between
a physical mouse and a low-frequency generated path without matched sampling/gesture analysis.
