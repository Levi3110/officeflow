# Assessment against the requested activities

The supplied criteria are browsing websites, scrolling, clicking links, interacting with
applications, natural pauses, occasional corrected typing errors, and varied delays.
Capability presence can be checked without a human dataset. Human similarity cannot.

The full native GUI run `runs/desktop-native-final` passed **7/7 policy checks and 7/7 desktop
checks**. This is an engineering checklist, not a competition score. The saved report is
[`examples/native/activity-assessment.json`](../examples/native/activity-assessment.json).

| Criterion | Verified native evidence |
| --- | --- |
| Browsing | 4 navigations and 4 page reads in actual Chrome; fictional localhost catalog |
| Scrolling | 4 scroll actions, 10 OS wheel events; all 4 show AX content movement relative to viewport |
| Clicking links | 3 mouse activations with verified target pages; no keyboard fallback |
| Applications | 20 Calc cells, 3 recalculated formulas, Writer report; file/source consistency passes |
| Contextual pauses | Actual planning, reading, scroll and application-switch waits recorded separately |
| Corrected typos | 4 notices and 4 independently observed corrections; final report matches exactly |
| Varied delays | 833 native active inter-key intervals; median 123.99 ms, p95 393.75 ms, CV 0.645 |

Simulation evidence remains labelled separately: it passes 7/7 policy checks and 0/7 desktop
checks. Simulation skips behavioural sleeps and cannot validate native input timing.

Recompute on a fresh run with its database and artifacts:

```bash
uv run sha assess runs/desktop-native-final --output runs/desktop-native-final/activity-assessment.json
```

The evaluator rechecks saved files, formulas and source hashes. It credits mouse link activation
only when the corresponding action verified. Native scroll evidence needs common AX anchors
moving relative to the same page viewport; wheel dispatch by itself cannot pass. Missing or
changed artifacts prevent credit for correct output and corrected final text.

Input recording covers the login session. Source/target PIDs are retained, and the sample's
provenance lists runner and unattributed events. All recorded keys/clicks/scrolls in the successful
run came from the runner; three pointer moves had source PID 0. No human baseline was collected.
Nonconstant timing and occasional corrections demonstrate capability, not authenticity.
