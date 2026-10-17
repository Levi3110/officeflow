# Human-05 exploratory benchmark

Read the [English analysis and limitations](../../docs/HUMAN_05_BENCHMARK.md).
This compares one agent trace with one person's session. People differ in typing,
editing, shortcuts, navigation and problem-solving. It is not a universal human
baseline or a calibrated 30/30/20/20 score. The observed timing differences are retained.

- `comparison.json`: exact descriptive evaluator output, including capture quality and feature definitions.
- `summary.csv`: feature counts, median/p95 and empirical distances; units are explicit.
- `resources.json`: sampled CPU/RSS diagnostics, with confounds and potentially stale focus labels.
- `manifest.json`: source byte counts/SHA256 hashes, analysis-code hashes, date and explicit study notes.

The manifest describes the original local report build: `raw_archived: true` means
raw snapshots were saved **locally**, not included in this repository. Human input coordinates,
process IDs and raw OS records are excluded from this published aggregate bundle. Original
human/agent traces remain unchanged. The local report archive is
`runs/benchmarks/human-05-vs-recorded-agent-final/`; `runs/` is ignored by Git.

The published Markdown adds relative artifact links and a prominent finding to the generated
local report; the numerical results and provenance are unchanged. Rebuild an English report
from closed local run directories using:

```bash
uv run python scripts/benchmark_report.py \
  --agent runs/recorded-native-demo-final \
  --human runs/human-05 \
  --output runs/benchmarks/human-05-reanalysis \
  --archive-raw
```

Use a fresh output directory; previous reports are not overwritten. For the original case-study
context and interpretation, pass each `manifest.json` study note as a `--study-note` argument.
These raw directories are not part of a fresh clone. New collection steps are in the
[baseline guide](../../docs/HUMAN_BASELINE.md).
