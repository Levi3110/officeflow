# Exploratory benchmark: recorded-native-demo-final vs human-05

Analysis date: 2026-10-17T19:13:55+08:00.

**Human behaviour varies across people and within the same person across tasks and sessions.**
Typing speed, key holds, pauses, editing, shortcut preferences, navigation and problem-solving
strategies differ. This benchmark compares one agent recording with one person's recording.
It cannot establish a universal human baseline, general human likeness, a maximum score or
a calibrated competition grade. Differences from this participant do not prove that the
agent is implausible for every other person, or that either participant performed better.

**Observed limitation:** agent key holds are shorter and less variable than this participant's (median 55.055 vs 86.960 ms; KS 0.744). The result does not demonstrate a close match.

For the complete 30/30/20/20 assessment, see the [four-criterion benchmark](FOUR_CRITERIA_BENCHMARK.md).
This report focuses on input distributions and collection context.

## Design and capture quality

- Agent: `recorded-native-demo-final`; human reference: `human-05`.
- One participant and one recording per side; keystrokes are correlated events, not independent participants.
- Both streams have closed start/stop lifecycles, sufficient active intervals and no reported gaps/drops/errors.
- This tool validates recording quality and compares distributions. Output correctness, identical task text and
  task-only boundaries require separate verification; capture completeness alone does not establish them.
- Original events and timestamps are preserved. A recording role is a collection label, not independent proof of identity.

| Recording window | Agent | Human |
| --- | ---: | ---: |
| Start-to-stop duration (s) | 159.624 | 304.704 |

Recording-window duration includes observer startup/teardown and terminal interaction. It is not independently
timed task completion, and is not used to claim a speedup or an efficiency win.

## Observed input distributions

| Feature | Unit | Agent n | Human n | Agent median | Human median | Agent p95 | Human p95 | KS | Wasserstein |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Active inter-key interval | ms | 833 | 663 | 122.487 | 151.252 | 387.291 | 775.154 | 0.278 | 98.003 |
| Key hold | ms | 849 | 682 | 55.055 | 86.960 | 75.609 | 135.927 | 0.744 | 36.028 |
| Input silence above 2 seconds | s | 4 | 5 | 3.623 | 3.223 | 3.929 | 4.442 | 0.400 | 0.634 |
| Legacy inter-key idle | s | 0 | 10 | N/A | 3.119 | N/A | 6.964 | N/A | N/A |
| Event-wise pointer speed (diagnostic only) | px/s | 170 | 10742 | 591.573 | 360.557 | 927.664 | 7106.696 | 0.386 | 3215.383 |

KS is a dimensionless empirical CDF distance. Wasserstein has the units shown for its feature; values across
different units should not be ranked against each other. Smaller distances describe closer sampled distributions,
not percentages of human likeness. N/A means no two nonempty comparable feature sets, not a zero distance.

Input-silence samples: agent 4; human 5. Small pause samples limit distribution conclusions.

| Input events | Agent | Human |
| --- | ---: | ---: |
| key_down | 896 | 708 |
| key_up | 896 | 698 |
| repeat_key_downs | 0 | 9 |
| move | 171 | 10743 |
| mouse_down | 3 | 62 |
| scroll | 10 | 51 |
| corrections | 4 | 92 |
| nonrepeat_corrections | 4 | 83 |

Backspace/Delete includes intentional editing and autorepeat; it is not a verified typo count. The difference
in click counts can reflect shortcut use, navigation strategy, edits and experience. Event-wise mouse speed is
especially sampling-sensitive: physical devices and generated paths can emit samples at different cadences.
The raw pointer distribution is retained as a diagnostic, not used as an authenticity grade or a calibration target.
Legacy inter-key idle resets at shortcuts; zero legacy idle does not mean no pauses. Input silence measures
absence of observed input above two seconds without identifying reading, thought or off-task activity.

## OS resource diagnostics

These sampler observations are not a controlled, isolated resource-efficiency comparison.

| Measurement | Agent | Human |
| --- | ---: | ---: |
| Runner peak RSS (MiB) | 135.734 | 79.812 |
| Runner sampled CPU peak (%) | 22.800 | 7.400 |
| All matching apps peak RSS (MiB) | 5234.781 | 6315.312 |
| All matching apps sampled CPU p95 (%) | 51.600 | 46.700 |

The human-side Python process is a passive observer; the agent-side process also plans and executes the workflow.
Its memory/CPU difference does not measure human computational effort. App totals include unrelated sessions,
shared memory can be counted repeatedly, and capture windows differ. Video/screenshots can also change resource costs.

Passive-only AppKit foreground sampling can remain cached when its main run loop is not advanced. Foreground
samples are excluded from dwell-time and task-completion interpretation. Independent, validated focus instrumentation
is needed for dwell analysis; the diagnostic name counts are retained in resources.json.

## Limits and next evaluation

1. This is a single-participant case study. Skill, typing style, device, language, familiarity, shortcut habits and
   task interpretation vary. Earlier practice can change performance. No population-level conclusion follows.
2. Capture quality is necessary but does not verify identical output, text length, task difficulty or task-only boundaries.
3. Samples are temporally correlated; no independence-based p-values, population confidence intervals or invented scores are reported.
4. The five-feature summaries omit higher-level action sequences, semantic correctness of human outputs, conditional
   behaviour by application/context and independently grounded app dwell. They are not a complete authenticity evaluation.
5. For stronger evidence, define output/phase checks, collect multiple participants and repeated sessions, control
   device/layout and background load, validate focus, and compare pointer gestures at matched sampling rates.
6. Separate personalisation/training sessions from held-out evaluation. Report per-person results and variability
   rather than optimising one average persona to one person's trace. Include failed runs in completion-rate denominators.

The 30/30/20/20 rubric remains unscored (`weighted_score: null`). This report is not evidence of maximum realism
or universal human imitation. Published benchmark files contain aggregates and provenance hashes; raw human
pointer coordinates and process IDs belong only in the optional local archive.
Exact raw snapshots are retained only in the local `runs/benchmarks/human-05-vs-recorded-agent-final/raw/` archive and excluded from Git.

Machine-readable artifacts: [comparison.json](../examples/human-05-benchmark/comparison.json), [summary.csv](../examples/human-05-benchmark/summary.csv), [resources.json](../examples/human-05-benchmark/resources.json) and [manifest.json](../examples/human-05-benchmark/manifest.json).

## Study notes

- The user reports completing all three phases: browsing three products, entering the Calc comparison, and writing the Writer report. Human output correctness and identical task text were not independently verified. Human-05 followed an earlier manual practice attempt; learning and task interpretation can affect the comparison.
- The retained agent trace predates human-05. No behaviour parameters, timestamps or events were changed to improve this result. Human-04 is not pooled into this analysis or counted as another participant.
- The agent has shorter active inter-key median/p95 (122.487/387.291 ms versus 151.252/775.154 ms) and shorter key-hold median/p95 (55.055/75.609 ms versus 86.960/135.927 ms). Key-hold variability is also lower (CV 0.198 versus 0.527). The key-hold KS distance is 0.744: the measured distributions differ substantially. These findings do not support claiming a close match to this participant.
- There are only four agent and five human input-silence gaps above two seconds. A KS distance of 0.400 from these small samples is not strong pause-similarity evidence. Different editing, shortcut and navigation strategies also limit the interpretation of event-count differences.
- All 581 human foreground samples report Code. This is treated as a potentially stale passive-sampler result, excluded from dwell and completion conclusions; it does not establish that the human used only Code. The recorded agent run included display recording and screenshots, so background/capture costs were not controlled.
- The retained agent artifacts were rechecked with sha assess: all seven activity checks passed, including source/file consistency. This functional checklist is separate from human similarity and is not a calibrated competition grade.
