# Four-criterion benchmark

Analysis: 2026-10-17T12:43:30+00:00. Agent: `recorded-native-demo-final`; human reference: `human-05`.

All four criteria are measured below. Weights are not achieved scores. Resource Efficiency is Primary; Complexity is Secondary. Priority labels do not alter the 30/30/20/20 formula.

| Criterion | Weight | Priority | Evidence status | Grade |
| --- | ---: | --- | --- | --- |
| Process Telemetry Authenticity | 30% | unspecified | independent_native_observations; similarity_unvalidated | Uncalibrated |
| Human Entropy & Timing | 30% | unspecified | single_participant_descriptive | Uncalibrated |
| Complexity of Action | 20% | Secondary | native_workflow_verified | Uncalibrated |
| Resource Efficiency | 20% | Primary | native_single_run_and_repeated_simulation | Uncalibrated |

## Process Telemetry Authenticity — 30%

Independent OS samples exist; process-pattern similarity to humans remains unvalidated. Hashes establish stored-file integrity, not trusted hardware attestation.

| Measurement | Agent | Human |
| --- | ---: | ---: |
| OS samples | 304.000 | 581.000 |
| Collector errors | 0.000 | 0.000 |
| Process rows with I/O available | 0.000 | 0.000 |
| Estimated runner CPU-seconds (diagnostic) | 9.320 | 13.992 |

| All matching app processes (diagnostic only) | Agent median | Human median | KS | Wasserstein |
| --- | ---: | ---: | ---: | ---: |
| cpu_percent | 22.400 | 16.400 | 0.321 | 5.097 |
| rss_mib | 4777.508 | 5829.844 | 0.985 | 1030.145 |
| threads | 1100.000 | 1256.000 | 1.000 | 152.302 |

The table compares entire matching app scopes at unequal sampling times, without task-phase alignment. KS/Wasserstein are descriptive distances only; unrelated sessions and shared memory confound them. They are not an isolated task or population process-pattern benchmark.

- Agent source counts: `{"psutil": 304}`; family sample presence: `{"LibreOffice": 304, "runner": 304, "Chrome": 304}`.
- Human source counts: `{"psutil": 581}`; family sample presence: `{"LibreOffice": 581, "runner": 581, "Chrome": 581}`.
- Agent observed input source groups: `{"runner": 1979}`. Automation provenance is preserved.

CPU/RSS describe real sampled activity, but app totals include unrelated processes. Missing I/O, kernel/network traces and validated dwell limit authenticity conclusions.

## Human Entropy & Timing — 30%

**People differ in typing and task-solving strategy. One person's session is an individual reference, not a universal human standard.**

| Observed feature | Agent n | Human n | Agent median | Human median | Agent CV | Human CV | KS |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| inter_key_seconds (ms) | 833 | 663 | 122.487 | 151.252 | 0.646 | 1.132 | 0.278 |
| key_hold_seconds (ms) | 849 | 682 | 55.055 | 86.960 | 0.198 | 0.527 | 0.744 |
| input_silence_seconds (s) | 4 | 5 | 3.623 | 3.223 | 0.100 | 0.289 | 0.400 |

Observed inter-key entropy (fixed 25 ms bins): agent 2.948 bits; human 4.262 bits. Higher entropy is not automatically more realistic. Raw event-wise pointer speeds are sampling-sensitive diagnostics only.

## Complexity of Action — 20%, Secondary

- Fresh read-only assessment: 7/7 desktop activity checks; this is a functional checklist, not 20/20 points.
- 22 verified actions, 7 action types, 5 handoffs, 20 cell edits and 5 GUI saves.
- Action mix: `{"navigate": 4, "scroll": 4, "read_page": 4, "follow_link": 3, "open_file": 2, "set_cells": 4, "write_document": 1}`.
- Scenario: bounded three-product localhost catalog, Calc spreadsheet/formulas and Writer report. General websites, Microsoft Office and open-ended planning remain unevaluated.

## Resource Efficiency — 20%, Primary

### Selected real desktop run

| Runner diagnostic | Value |
| --- | ---: |
| RSS median (MiB) | 72.141 |
| RSS p95 (MiB) | 114.641 |
| RSS peak (MiB) | 135.734 |
| Sampled CPU p95 (%) | 7.300 |
| Sampled CPU peak (%) | 22.800 |
| Estimated CPU-seconds | 9.320 |
| Model calls / input tokens / output tokens | 0 / 0 / 0 |

Default routing uses code policies, so zero model cost is specific to this bounded MVP, not arbitrary LLM planning. Sampled CPU-seconds are an estimate, not energy or hardware accounting. The elapsed timing-category breakdown is in benchmark.json. Behavioural waits, application wait/verification and runtime overhead remain separate categories; behavioural sleep is not treated as pure execution overhead.

| Elapsed timing category | Seconds |
| --- | ---: |
| behaviour.plan | 3.931 |
| behaviour.switch | 0.819 |
| behaviour.key_hold | 45.507 |
| behaviour.typing | 73.097 |
| application_wait_and_verification | 3.792 |
| runtime_overhead | 11.255 |
| behaviour.scroll | 1.436 |
| behaviour.read | 12.936 |
| behaviour.pointer | 4.244 |
| behaviour.typo_notice | 1.021 |

### Fresh-process simulation core

9/9 trials completed. All supplied trials remain in the denominator. Core wall/CPU time excludes realtime behavioural sleeping, application execution and the OS sampler.

| Measurement | Median | p95 |
| --- | ---: | ---: |
| Core wall time (ms) | 66.350 | 71.644 |
| Core CPU time (ms) | 49.173 | 50.260 |
| Process lifetime peak RSS (MiB) | 89.406 | 89.453 |
| Imports (ms) | 196.910 | 271.673 |
| Audit export (ms) | 7.794 | 10.552 |

These repeated trials measure simulation-core efficiency. They do not establish native desktop efficiency, a population success rate, or a speed advantage over a human observer. A controlled repeated native baseline is still needed.

## Interpretation and missing evidence

- One selected agent trace and one participant/session. People differ in typing, editing, shortcuts, navigation and problem-solving; no universal human baseline or close-match claim follows.
- Independent sampler provenance is evidence of real measurements, not proof of human-like process patterns. Source metadata exposes generated input; no hardware-origin disguise is attempted.
- All matching app processes include unrelated sessions, and RSS may double-count shared memory. Foreground labels can be stale; they are excluded from dwell/completion conclusions. Process I/O may be unavailable; kernel/network traces are absent.
- Human runner observes only; agent runner plans and executes too. Human/agent runner CPU and RSS are not like-for-like cognitive efficiency measures.
- Small silence samples, unequal event cadences, correlated events and unmatched manual text limit inference. More entropy is not automatically better.
- Native resource diagnostics are one selected run, with video/screenshot overhead and uncontrolled background load. Core trials are simulation, not desktop throughput or a native success rate.
- The retained successful native demo does not supply an all-attempt reliability denominator. Earlier development failures exist. Human task completion is user-reported; manual output correctness was not independently verified.
- No calibrated 0-100 scoring thresholds, process baseline population or isolated native efficiency baseline were supplied. Weights alone cannot produce a valid competition grade; every grade remains null.

**Weighted score: unassigned (`null`).** Formula: `0.30*A + 0.30*H + 0.20*C + 0.20*R`, once independently calibrated scores exist. Do not convert a checklist, entropy, KS distance or low memory into competition points.

## Artifacts and reproduction

- [Complete aggregate measurements and provenance](../examples/four-criteria-benchmark/benchmark.json)
- [Weights, priorities and evidence status CSV](../examples/four-criteria-benchmark/rubric.csv)
- [All nine fresh-process core trials](../examples/four-criteria-benchmark/core-trials.json)
- [Human-05 timing study and collection context](HUMAN_05_BENCHMARK.md)

```bash
uv run sha benchmark --runs 9 --output runs/benchmarks/fresh-core.json
uv run sha evaluate \
  --agent runs/recorded-native-demo-final \
  --human runs/human-05 \
  --core runs/benchmarks/fresh-core.json \
  --output runs/benchmarks/fresh-four-criteria
```

The native agent/human directories are local evidence, excluded from a fresh clone. Collect
new closed runs first if those directories are unavailable. `evaluate` reads evidence and
rechecks artifacts; it emits no desktop input. Use a fresh output folder to preserve prior results.
Native timings/resources come from the previously recorded demo; only the nine core trials
were executed again for this report. This does not count as a new GUI run.

The historical optimized confirmation had median core wall/CPU times of 61.993/46.664 ms;
this new batch measured 66.350/49.173 ms, about 7.0%/5.4% higher. Both batches completed 9/9
simulation trials. Background load and sampling time were not controlled between batches;
this is retained variability, not evidence that the new reporting code caused a slowdown.
The new result is published rather than choosing the fastest historical batch. The historical
core results and baseline source remain in [OPTIMIZATION.md](OPTIMIZATION.md).
