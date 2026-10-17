"""Save an English, conservative benchmark report from closed agent/human run directories."""

import argparse
import json
from pathlib import Path

from synthetic_human.reporting import build_report

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", type=Path, required=True)
    parser.add_argument("--human", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--archive-raw", action="store_true", help="Keep exact raw snapshots in the local report folder"
    )
    parser.add_argument(
        "--study-note", action="append", default=[], help="Explicit English protocol or interpretation note"
    )
    args = parser.parse_args()
    manifest = build_report(
        args.agent, args.human, args.output, archive_raw=args.archive_raw, study_notes=args.study_note
    )
    print(json.dumps({"output": str(args.output.resolve()), "manifest": manifest}, indent=2))
