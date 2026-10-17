# Optimization review evidence

Read [OPTIMIZATION_REVIEW.md](../../docs/OPTIMIZATION_REVIEW.md) and the generated
[four-criterion report](four-criteria-report.md). All three new native attempts are retained in
`review.json`; earlier historical development failures are not part of that three-attempt series.

`benchmark.json` and `rubric.csv` describe the final native run against human-05 and the final
simulation-core batch. The comparison is explicitly **in-sample personalisation**, not independent
human evaluation. The calibrated configuration is optional; the legacy generic demo remains separate.
`persona-calibration-provenance.json` records the fit method, parameters and unchanged input hash.

`sampler-optimization-*.json` retain both alternating nine-pair real OS sampler microbenchmarks.
They measure sampler cost, not whole-agent CPU savings. `optimization-review-*.json` retain all
six nine-trial core batches, including slower intermediate results and held-out agent seeds.
These trials use the benchmark's generic simulation persona and exclude real-time behavioural sleeps.

`comparison.ods` and `report.odt` were entered and saved through actual Calc/Writer GUI input in
`optimized-human05-native-03`. `settings.json` and `activity-assessment.json` describe that run.
The fictional catalog URLs require the corresponding local server. General websites and Microsoft
Office remain outside the verified MVP. Raw input/OS traces, personal PIDs and screenshots remain
in local ignored `runs/`; this bundle publishes aggregates, hashes and agent-produced artifacts only.
