# Optimization results

Measured on 2026-10-17 (Asia/Singapore), macOS ARM64, Python 3.14.6.

Each batch contains 9 fresh-process runs. Baseline and optimization rounds use the same seeds.
Final holdout uses 9 different seeds. Behavioural sleeps and the OS sampler are excluded to isolate
core simulation overhead. These measurements do not score live GUI authenticity.

| Metric (median) | Baseline | Final confirmation | Change |
| --- | ---: | ---: | ---: |
| Core workflow | 163.00 ms | 61.99 ms | -62.0% |
| Core CPU time | 113.43 ms | 46.66 ms | -58.9% |
| Audit export | 26.97 ms | 7.65 ms | -71.6% |
| Input dispatches | 1024.00  | 916.00  | -10.5% |
| Peak process RSS | 89.52 MiB | 89.64 MiB | +0.1% |
| Audit size | 473.88 KiB | 495.11 KiB | +4.5% |

Task correctness and scope remain the same: 20 spreadsheet cells, tax formulas, report,
five expertise handoffs and source consistency. Calc saves fall from **20 to 4**; total GUI
saves fall from **21 to 5**. Logical actions fall from 38 to 22 by row batching, with each
cell still entered individually through the GUI in live mode. This is not a reduction of
semantic task complexity. Native execution has since passed the full GUI workflow; see `examples/native/README.md`.

## Iterations

| Batch | Success | Core median ms | CPU median ms | Export median ms |
| --- | ---: | ---: | ---: | ---: |
| baseline | 9/9 | 163.00 | 113.43 | 26.97 |
| round1 | 9/9 | 81.70 | 55.43 | 32.92 |
| round2 | 9/9 | 78.80 | 52.41 | 8.10 |
| round3 | 9/9 | 63.36 | 48.14 | 7.93 |
| round4 | 9/9 | 63.73 | 46.49 | 7.88 |
| round5 | 9/9 | 59.94 | 45.38 | 8.17 |
| confirmation | 9/9 | 61.99 | 46.66 | 7.65 |
| holdout | 9/9 | 62.37 | 46.32 | 7.46 |
| final-holdout | 9/9 | 61.35 | 45.56 | 7.72 |

Raw trials, medians and p95 values are included under `examples/optimization/`.
The earlier holdout preceded the final transaction coalescing; `final-holdout` validates the
final core implementation. Overall RSS is essentially unchanged at about 90 MiB. Audit size
increases slightly because it now records requested/elapsed key holds; trace coverage was not
removed to reduce resource numbers. Full GUI/app memory and throughput were not benchmarked.

## Changes retained

- One journaled row edit verifies all saved cells; Tab navigation replaces repeated A1 resets.
- SQLite batches high-frequency trace inserts, preserves original timestamps, and retains full
  action/authority durability. Lease+intent and persona+lease release each commit atomically.
- Audit export avoids JSON decode/re-encode. Metrics stream records. OS reads use oneshot and
  prune stale process cache entries. CLI imports the graph only when executing a workflow.
- Behaviour includes variable key holds with cancellation-safe release, word-chunk pacing,
  adjacent-key corrections, protected URLs/emails, scroll bursts and persisted persona RNG.
- Navigation validation no longer adds duplicate full-page reading pauses. Handoff receivers
  re-observe AX/focus without duplicating an unchanged sender screenshot.
- Passive native input recording and a manual-baseline comparator are implemented. Missing
  permission writes status only; incomplete input cannot receive a fabricated rubric score.

## Stopping condition and remaining evidence

The final confirmation differs from the preceding final candidate by less than 5% in both
median core wall time and median CPU time. Correctness remained 9/9 in each batch, including
final held-out seeds. This is a measured local plateau under the available simulation environment,
not proof of a global optimum or maximum competition score. Timing noise is visible in raw p95s.

The 30/30/20/20 rubric has no calibrated score formula. No human baseline was supplied during
core optimization. At benchmark time, LibreOffice and the three macOS permissions were unavailable. LibreOffice has since been
installed and Accessibility/Input Monitoring granted. A real GUI run passed all seven requested
activity checks with independent input telemetry; see `examples/native/README.md`. The native
run is a functionality demonstration, not a repeated resource benchmark. Screen capture has
since been granted and independently checked;
the later [human-05 comparison](HUMAN_05_BENCHMARK.md) now supplies one individual reference.
It shows substantial timing differences and cannot represent all people or task strategies. Further
authenticity evaluation requires multiple participants and held-out sessions; the measured core
plateau is not a maximum competition score.

## Reproduce

```bash
uv run sha benchmark --runs 9 --output runs/bench/fresh.json
uv run pytest -q
```

The exact initial core source, including the same benchmark harness, is frozen in
`examples/optimization/baseline-source.zip`. Extract it to a separate directory, set
`PYTHONPATH` to that directory and run `python -m synthetic_human.benchmark --runs 9 --output ...`
with the same environment/lockfile. Do not compare profiled runs to unprofiled trials.
