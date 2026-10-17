# Optimization review and stopping record

Date: 2026-10-17, Asia/Singapore. Environment: macOS 26.4 ARM64, Python 3.14.6.

**The overall competition score cannot yet be called high:** the supplied weights do not define
calibrated scoring thresholds. The bounded workflow is verified; timing fit and sampler cost
have improved in the measurements below. Process-pattern similarity and population human likeness
remain unvalidated. The weighted grade stays null.

## Changes retained

- Frequent focus checks read application/window/document identity without copying the editor's
  complete focused text. Wrong-document checks and per-input authority fencing remain enforced.
- Page reading performs one GUI copy, and one clipboard snapshot supplies both verification and
  stored evidence. This removes duplicate copy commands and subprocess reads without weakening
  the source/file postconditions.
- The event store reuses its compact JSON encoder, preserving every event and durable action intent.
- Passive foreground monitoring now advances AppKit's main run loop. Samples carry source, age
  and observed/stale/unavailable status. Stale labels are not exposed as fresh focus observations.
- The sampler discovers PIDs every sample and still measures CPU/RSS/threads live. Stable names
  and creation metadata use a 5-second cache with recorded age; matched PID reuse is checked
  each sample and a new process gets a new CPU baseline. A nonmatching PID that changes identity
  between samples can take up to the metadata TTL to be reclassified. This limit is explicit.
- An **optional** persona exposes typing/hold dispersion and independent key-hold sampling.
  The old algorithm clipped holds in short intervals; the new mode extends a too-short onset
  instead. Legacy checkpoint personas still restore with their original default behaviour.

## Human timing: individual training fit

`configs/demo-human05.json` was fitted to the closed human-05 recording: reciprocal active
inter-key median, log standard deviations and key-hold median set the persona parameters.
No input events or timestamps were modified. `configs/demo.json` remains the separate generic
legacy configuration. Changing the seed checks generation variability, not independent human
validation. Serial delivery still cannot reproduce overlapping key holds.

| Descriptive distance | Original recorded agent | Personalised seed 17, run 01 | Seed 101, run 02 | Final seed 17, run 03 |
| --- | ---: | ---: | ---: | ---: |
| Active inter-key KS | 0.278 | 0.156 | 0.140 | 0.155 |
| Key-hold KS | 0.744 | 0.146 | 0.167 | 0.148 |
| Input-silence KS | 0.400 | 0.400 | 0.333 | 0.400 |
| Legacy inter-key idle KS | N/A | 0.900 | 0.600 | 0.900 |

The improved typing/hold distances are **in-sample fit**, not proof of a universal human persona.
The silence samples are sparse and legacy idle remains poorly matched. Raw pointer speeds are
sampling-sensitive diagnostics; different navigation/editing strategies remain unresolved.
People vary both across participants and across their own sessions. Human output correctness
and identical task text were not independently verified. New independent participants/sessions
are required to evaluate generalisation.

## Native correctness and resource diagnostics

All **three new review attempts completed**, each with **22 verified actions, 5 handoffs and
7/7 requested desktop activity checks**. Input lifecycles closed with zero reported gaps,
dropped events, recorder errors or invalid timestamps. All 20 cells, three tax formulas and the
report passed independent source/file checks. This three-attempt series does not erase earlier
development failures or establish a population success rate.

| Native diagnostic | Personalised run 01 | Seed confirmation 02 | Final collector 03 |
| --- | ---: | ---: | ---: |
| Seed | 17 | 101 | 17 |
| Capture window (s) | 248.013 | 250.255 | 247.365 |
| Estimated runner CPU-seconds | 12.934 | 13.404 | 7.832 |
| Runner peak RSS (MiB) | 137.109 | 139.141 | 136.328 |
| Recorded runtime overhead (s) | 11.857 | 10.944 | 10.785 |

Runs 01/02 precede the metadata-cache optimization; run 03 includes it. The same-persona,
same-seed comparison (01 → 03) shows approximately **39% less estimated runner CPU-time**.
This is a descriptive native observation with uncontrolled background work and app sessions,
not an isolated causal estimate. CPU-seconds are integrated from periodic CPU-percent samples,
not measured by a hardware energy counter. RAM is approximately flat.

The personalised capture is longer than the original generic trace (159.624 s). It has slower,
more variable typing. Capture duration is not independently bounded task time. The original
trace also recorded video, so it is not a controlled resource baseline for these new runs.
Zero model calls/tokens reflects bounded code policies, not efficient arbitrary LLM planning.

Fresh foreground statuses were observed throughout the new runs. Historical human-05 foreground
samples still report Code and remain excluded from dwell/completion inference; new code does
not retroactively repair those measurements. Actual process I/O remains unavailable on this
machine, and kernel/network traces are not implemented.

## Sampler CPU microbenchmark

Both batches contain nine pairs with alternating baseline/optimized order. Each batch times
ten real OS samples; one metadata refresh per ten optimized samples models the normal 5-second
TTL at 0.5-second configured sampling. No sleeps are included. Process CPU/RSS/thread calls
remain live. Input/foreground work is excluded from this isolated sampler benchmark.

| CPU cost per sample (median of batches) | Baseline `111bf38` | Optimized | Reduction |
| --- | ---: | ---: | ---: |
| First nine pairs | 6.914 ms | 1.880 ms | 72.8% |
| Confirmation nine pairs | 6.397 ms | 1.827 ms | 71.4% |

These are sampler savings, **not whole-agent or whole-computer CPU savings**. Warmed, rapid
microbenchmarks approximate scheduled metadata expiry; the native final run separately checks
integration. Both raw paired batches and source hashes are retained.

## Repeated simulation core and stopping condition

These batches use the benchmark's generic legacy persona, not the personalised GUI profile.
Simulation skips realtime behavioural sleeps and excludes the OS collector. Every supplied
trial remains in the denominator, and all six batches completed **9/9**.

| Batch | Core wall median (ms) | Core CPU median (ms) |
| --- | ---: | ---: |
| Before review | 63.047 | 46.918 |
| Round 1 | 60.884 | 45.521 |
| Intermediate confirmation | 63.513 | 48.163 |
| Intermediate holdout seeds | 64.863 | 49.283 |
| Final, after GUI completion | 60.720 | 46.108 |
| Final holdout seeds, after GUI completion | 63.252 | 47.737 |

Some intermediate batches overlapped native work and background load was uncontrolled; slower
results are retained. Final/holdout medians differ by less than 5% in wall and CPU time. Core
cost is approximately at the existing local plateau; no substantial core speedup is claimed.
Removing duplicate copies reduces generic simulation dispatches from a median 916 to 908 while
preserving semantic actions and all postcondition checks.

Optimization stops here because the identified correctness/measurement issues are fixed,
three native workflows and the full tests pass, the sampler improvement repeats in a second
paired batch, and core variations remain near the local plateau. This is **not** proof of a
global maximum, a high official score, or a human-population match. Further progress needs
held-out people/sessions, isolated repeated native controls and a calibrated scoring rubric.

## Reproduce and present

```bash
uv run --extra desktop sha run --backend macos --config configs/demo-human05.json --output runs/personalised-new
uv run sha benchmark --runs 9 --output runs/benchmarks/core-new.json
uv run sha evaluate --agent runs/personalised-new --human runs/human-05 --core runs/benchmarks/core-new.json --comparison-scope personalization_training --output runs/benchmarks/review-new
uv run python scripts/benchmark_sampler.py --output runs/benchmarks/sampler-new.json
```

Use fresh output paths. Human-05 is local; a clone needs its own consented, closed reference.
The sampler benchmark requires the full repository history containing `111bf38`.

- [All retained aggregate measurements and agent-produced files](../examples/optimization-review/README.md)
- [Generated final four-criterion report](../examples/optimization-review/four-criteria-report.md)
- [Earlier four-criterion baseline](FOUR_CRITERIA_BENCHMARK.md)

The full suite passes **74 tests**, with lint/format checks across **47 Python files**. Tests
cover legacy persona restoration, independent hold bounds and unchanged prose, wrong-document
rejection, one-snapshot clipboard verification, main-loop focus refresh/stale rejection, immediate
new-PID discovery, periodic metadata expiry and matched PID reuse. Raw human traces stay local.
