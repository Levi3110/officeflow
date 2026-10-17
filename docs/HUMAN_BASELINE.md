# Collect a human baseline

A baseline records **you manually performing the same task** as the agent. Video is optional
for input-timing comparison. The recorder listens to metadata, emits no mouse/keyboard input,
and stores no typed characters or raw key codes. Its scope is the login session: avoid other
work while recording. The desktop lock prevents simultaneous agent and human collection.

Human behaviour varies across people and across tasks, sessions, experience levels and devices.
One person's recording is a useful individual reference, not a universal human standard. See
the [human-05 benchmark and limitations](HUMAN_05_BENCHMARK.md).

## 1. Serve the demo website in the first terminal

From the project directory:

```bash
uv run python scripts/serve_catalog.py
```

Keep that terminal open. The catalog is at `http://127.0.0.1:8765` and contains the same three
fictional products. If the port is busy, use `--port 8766` and the printed URL.

## 2. Prepare the task

Use the same machine, Chrome/LibreOffice versions, layout and zoom as the agent run. Prepare
and save separate empty Calc/Writer files before collection. Read the task instructions first:

- Browse the catalog, scroll and click Details to obtain all three prices and warranties.
- Enter five columns: Product, Price USD, Warranty months, Price with 8% tax and Source.
- Use rows 2–4 in catalog order. D2 is `=B2*1.08`; use corresponding formulas in D3/D4.
- Write a report containing prices, tax-inclusive prices, warranties, source URLs and the lowest-price recommendation.
- Save both files. For a stricter workload comparison, match the demo report's content and length.

Work naturally. Type the corresponding content rather than pasting entire documents. Do not
manufacture mistakes, delays or an imitation of the agent's pace. Correct real mistakes as usual.

## 3. Record in the second terminal

```bash
uv run --extra desktop sha capture-human --seconds 600 --output runs/human-01
```

Start manual work when `Recording metadata only...` appears. The limit is ten minutes; you do
not need to use all ten. When finished, return to the **second terminal** and press Ctrl+C.
Recorded data is retained. Keep the website's terminal running until the task is finished.
An exit code of 130 after Ctrl+C is an intentional interruption, not evidence of data loss.

Output is `runs/human-01/inputs.jsonl` and `telemetry.jsonl`. Use a fresh directory for each
session (`human-02`, etc.). The collector does not verify manual documents: check their data,
formulas and report before using a session. Record failed tasks as well as successful ones.
Stop collection immediately after completion, **before** typing compare commands or reading
results. A valid stop marker establishes technical closure, not a task-only recording boundary.

## 4. Compare with the recorded agent

The handoff machine already has the following agent trace. A fresh clone does not include
`runs/`; execute a native agent run first and substitute its input path.

```bash
uv run sha compare --agent runs/recorded-native-demo-final/inputs.jsonl --human runs/human-01/inputs.jsonl --output runs/baseline-comparison-01.json
```

The tool reports median/p95 and descriptive KS/Wasserstein distances for inter-key intervals,
key holds, gaps and pointer speeds. Smaller distances mean closer sampled distributions;
there is no automatic threshold for declaring human likeness. At least 30 valid active intervals
per side and error-free coverage are minimum tool checks, not a sufficient statistical sample.
Both recordings need valid start/stop lifecycles and `coverage.completed = true`. Live/partial
JSON traces and lifecycle errors produce `insufficient_evidence` with explicit reasons. The
weighted score remains null: the tool does not invent a 30/30/20/20 competition grade.

Begin with one session to check the collection process. For stronger evaluation, collect
multiple sessions per person, multiple participants and repeated agent runs under matched
conditions. For example, 3–5 sessions per person can be an initial collection plan, not a proven
adequate sample size. Keep tuning data separate from held-out evaluation sessions. CPU/RAM
telemetry is saved, but `compare` itself compares input features; resources and output accuracy
need separate checks. Repeated sessions from one person remain one participant; record workload and participant identity separately.

## Save an immutable comparison report

```bash
uv run python scripts/benchmark_report.py \
  --agent runs/recorded-native-demo-final \
  --human runs/human-01 \
  --output runs/benchmarks/human-01 \
  --archive-raw
```

This writes an English report, CSV, comparison/resource JSON and a SHA256 provenance manifest.
With `--archive-raw`, exact input/OS snapshots are copied into this **local** ignored folder.
Sources are not changed and an existing report directory is rejected. Omit the flag for an
aggregate-only report. Add `--study-note 'English protocol note'` for explicit collection context.
Publish selected aggregates only; raw human session metadata stays local.

## Interpret the measurements conservatively

`idle_seconds` is the legacy gap-between-keys measure, reset by shortcuts. Zero does not mean
no pauses occurred. `input_silence_seconds` measures gaps above two seconds between any input
events, without identifying reading, thought or off-task activity. `corrections` counts Backspace/
Delete, including repeats; `nonrepeat_corrections` removes repeats but still includes deliberate
editing. Neither is a verified typo count. Pointer velocity is event-wise without resampling;
different event cadences can distort means and tails.

The passive foreground sampler can report stale application state. Do not infer application
dwell or lack of task completion from it without independent validation. Closed capture files
and high event counts do not establish identical text, task difficulty, skill or cognitive effort.
The human-05 report retains these limitations and does not portray timing differences as a
universal failure of the person or proof of agent superiority.
