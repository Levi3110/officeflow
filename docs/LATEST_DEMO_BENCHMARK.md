# Four-criterion benchmark

Analysis: 2026-10-17T14:01:42+00:00. Agent: `user-recording-demo-20261017-01`; human reference: `human-05`.

**In-sample personalisation:** this human reference was used to fit the persona. Lower distances are training fit, not independent human validation.

All four criteria are measured below. Weights are not achieved scores. Resource Efficiency is Primary; Complexity is Secondary. Priority labels do not alter the 30/30/20/20 formula.

| Criterion | Weight | Priority | Evidence status | Grade |
| --- | ---: | --- | --- | --- |
| Process Telemetry Authenticity | 30% | unspecified | independent_native_observations; similarity_unvalidated | Uncalibrated |
| Human Entropy & Timing | 30% | unspecified | in_sample_personalization_comparison | Uncalibrated |
| Complexity of Action | 20% | Secondary | native_workflow_verified | Uncalibrated |
| Resource Efficiency | 20% | Primary | native_single_run_and_repeated_simulation | Uncalibrated |

## Process Telemetry Authenticity — 30%

Independent OS samples exist; process-pattern similarity to humans remains unvalidated. Hashes establish stored-file integrity, not trusted hardware attestation.

| Measurement | Agent | Human |
| --- | ---: | ---: |
| OS samples | 484.000 | 581.000 |
| Collector errors | 0.000 | 0.000 |
| Process rows with I/O available | 0.000 | 0.000 |
| Estimated runner CPU-seconds (diagnostic) | 7.642 | 13.992 |

| All matching app processes (diagnostic only) | Agent median | Human median | KS | Wasserstein |
| --- | ---: | ---: | ---: | ---: |
| cpu_percent | 15.800 | 16.400 | 0.090 | 1.397 |
| rss_mib | 6842.047 | 5829.844 | 0.981 | 1052.393 |
| threads | 1330.000 | 1256.000 | 1.000 | 84.399 |

The table compares entire matching app scopes at unequal sampling times, without task-phase alignment. KS/Wasserstein are descriptive distances only; unrelated sessions and shared memory confound them. They are not an isolated task or population process-pattern benchmark.

- Agent source counts: `{"psutil": 484}`; family sample presence: `{"LibreOffice": 484, "runner": 484, "Chrome": 484}`. Foreground statuses: `{"observed": 484}`.
- Human source counts: `{"psutil": 581}`; family sample presence: `{"LibreOffice": 581, "runner": 581, "Chrome": 581}`. Foreground statuses: `{"legacy_unvalidated": 581}`.
- Agent observed input source groups: `{"runner": 1992}`. Automation provenance is preserved.

CPU/RSS describe real sampled activity, but app totals include unrelated processes. Missing I/O, kernel/network traces and validated dwell limit authenticity conclusions.

## Human Entropy & Timing — 30%

**People differ in typing and task-solving strategy. One person's session is an individual reference, not a universal human standard.**

| Observed feature | Agent n | Human n | Agent median | Human median | Agent CV | Human CV | KS |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| inter_key_seconds (ms) | 832 | 663 | 184.351 | 151.252 | 0.760 | 1.132 | 0.156 |
| key_hold_seconds (ms) | 849 | 682 | 86.513 | 86.960 | 0.433 | 0.527 | 0.152 |
| input_silence_seconds (s) | 4 | 5 | 3.636 | 3.223 | 0.110 | 0.289 | 0.400 |

Observed inter-key entropy (fixed 25 ms bins): agent 4.388 bits; human 4.262 bits. Higher entropy is not automatically more realistic. Raw event-wise pointer speeds are sampling-sensitive diagnostics only.

## Complexity of Action — 20%, Secondary

- Fresh read-only assessment: 7/7 desktop activity checks; this is a functional checklist, not 20/20 points.
- 22 verified actions, 7 action types, 5 handoffs, 20 cell edits and 5 GUI saves.
- Action mix: `{"navigate": 4, "scroll": 4, "read_page": 4, "follow_link": 3, "open_file": 2, "set_cells": 4, "write_document": 1}`.
- Scenario: bounded three-product localhost catalog, Calc spreadsheet/formulas and Writer report. General websites, Microsoft Office and open-ended planning remain unevaluated.

## Resource Efficiency — 20%, Primary

### Selected real desktop run

| Runner diagnostic | Value |
| --- | ---: |
| RSS median (MiB) | 69.562 |
| RSS p95 (MiB) | 114.281 |
| RSS peak (MiB) | 136.234 |
| Sampled CPU p95 (%) | 5.800 |
| Sampled CPU peak (%) | 25.200 |
| Estimated CPU-seconds | 7.642 |
| Model calls / input tokens / output tokens | 0 / 0 / 0 |

Default routing uses code policies, so zero model cost is specific to this bounded MVP, not arbitrary LLM planning. Sampled CPU-seconds are an estimate, not energy or hardware accounting. The elapsed timing-category breakdown is in benchmark.json. Behavioural waits, application wait/verification and runtime overhead remain separate categories; behavioural sleep is not treated as pure execution overhead.

| Elapsed timing category | Seconds |
| --- | ---: |
| behaviour.plan | 3.934 |
| behaviour.switch | 0.819 |
| behaviour.key_hold | 77.659 |
| behaviour.typing | 127.931 |
| application_wait_and_verification | 3.989 |
| runtime_overhead | 11.010 |
| behaviour.pointer | 4.954 |
| behaviour.scroll | 1.498 |
| behaviour.read | 12.930 |
| behaviour.typo_notice | 1.021 |

### Fresh-process simulation core

9/9 trials completed. All supplied trials remain in the denominator. Core wall/CPU time excludes realtime behavioural sleeping, application execution and the OS sampler.

| Measurement | Median | p95 |
| --- | ---: | ---: |
| Core wall time (ms) | 60.720 | 61.555 |
| Core CPU time (ms) | 46.108 | 46.959 |
| Process lifetime peak RSS (MiB) | 89.438 | 89.478 |
| Imports (ms) | 191.342 | 236.275 |
| Audit export (ms) | 7.650 | 11.088 |

These repeated trials measure simulation-core efficiency. They do not establish native desktop efficiency, a population success rate, or a speed advantage over a human observer. A controlled repeated native baseline is still needed.

## Interpretation and missing evidence

- Human reference data was used to fit this persona. Comparison is in-sample training evidence, not held-out human evaluation or generalisation.
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

- [Aggregate measurements and provenance](../examples/latest-demo-benchmark/benchmark.json)
- [Weights and evidence-status CSV](../examples/latest-demo-benchmark/rubric.csv)
- [Activity assessment](../examples/latest-demo-benchmark/activity-assessment.json)
- [GUI-produced spreadsheet](../examples/latest-demo-benchmark/comparison.ods)
- [GUI-produced report](../examples/latest-demo-benchmark/report.odt)
- [Reused nine-trial simulation-core batch](../examples/latest-demo-benchmark/core-trials.json)
- [Earlier generic-persona benchmark](FOUR_CRITERIA_BENCHMARK.md)
- [Sampler optimisation and calibration evidence](OPTIMIZATION_REVIEW.md)

This report analyses the completed native run `user-recording-demo-20261017-01`.
The nine simulation-core trials were reused from the earlier optimisation review, not
rerun during this analysis. The provenance key `core/optimization-review-final-core.json`
refers to the same bytes archived here as `core-trials.json`.

The Python runner's mean sampled CPU usage was **3.089%**. Its peak sampled RSS was
**136.234 MiB**. These exclude Chrome and LibreOffice resource costs. The 71–73% sampler
CPU-cost reduction comes from the separate paired microbenchmarks in the optimisation review,
not a controlled before/after comparison of this native run.

To reproduce with newly collected local evidence:

```bash
uv run --extra desktop sha run --backend macos --config configs/demo-human05.json --output runs/new-personalised-demo
uv run sha benchmark --runs 9 --output runs/benchmarks/new-core.json
uv run sha evaluate \
  --agent runs/new-personalised-demo \
  --human runs/human-05 \
  --core runs/benchmarks/new-core.json \
  --comparison-scope personalization_training \
  --output runs/benchmarks/new-personalised-demo
```

`runs/human-05` is a private local recording and is absent from a fresh clone. Use the
[manual baseline guide](HUMAN_BASELINE.md) to collect your own reference, and choose the
comparison scope according to whether that recording also calibrated the persona.
`sha evaluate` reads existing evidence and does not send desktop input.
Raw human recordings, screenshot pixels, presentation materials, and videos remain outside Git.
