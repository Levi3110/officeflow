# Four-criterion evidence benchmark

Read the [English report](../../docs/FOUR_CRITERIA_BENCHMARK.md).

- `benchmark.json`: measured evidence for Process Telemetry Authenticity (30%), Human Entropy &
  Timing (30%), Complexity of Action (20%, Secondary) and Resource Efficiency (20%, Primary).
- `rubric.csv`: those weights, priority labels and evidence statuses. Blank grades mean uncalibrated,
  not zero and not a claimed full score.
- `core-trials.json`: all nine newly executed fresh-process simulation trials, including raw per-trial
  CPU, wall time, RSS, import/export costs and action counts. These are not GUI throughput trials.

The report rechecks saved agent artifacts and compares the retained native recording with
human-05. No new GUI workflow was run for this report. Sampled native CPU/RSS include observer
cost and uncontrolled background effects. The human recorder does less work than the agent
runner, and one person's timing/task strategy does not represent all people.

Process CPU/RSS/thread distances compare all matching app processes, including unrelated
sessions. Large differences are retained. They do not isolate task activity or establish human
identity. Passive focus labels may be stale and are excluded from dwell/completion conclusions.

Source hashes and analysis-code hashes are recorded in `benchmark.json`; raw human PIDs,
coordinates and OS/input traces remain local. No raw human trace is included here. The full
local report is `runs/benchmarks/four-criteria-human-05-final/`. Weights alone do not supply
calibrated 0–100 scoring rules, so all grades and the weighted total remain null.
