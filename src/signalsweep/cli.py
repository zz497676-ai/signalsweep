"""Command-line entry point for reproducible local runs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .pipeline import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Run SignalSweep on a CSV file.")
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path(".artifacts"))
    parser.add_argument(
        "--show-trace",
        action="store_true",
        help="Print the Taskmaster event trace after the run.",
    )
    args = parser.parse_args()

    result = run_pipeline(args.input_csv.read_text(encoding="utf-8"), args.input_csv.name)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "cleaned.csv").write_text(result.cleaned_csv, encoding="utf-8")
    (args.output_dir / "report.md").write_text(result.report_markdown, encoding="utf-8")
    (args.output_dir / "run.json").write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Dataset: {result.dataset_name}")
    print(f"Rows: {result.profile.row_count}")
    print(f"Issues: {len(result.issues)}")
    print(f"Anomalies: {len(result.anomalies)}")
    print(f"Workflow: {result.workflow_status}")
    print("Next actions:")
    for action in result.actions:
        print(f"- {action.action} [{action.decision}] — {action.reason}")
    if args.show_trace:
        print("Trace:")
        for event in result.events:
            print(f"{event.sequence}. {event.step} [{event.status}] — {event.message}")
    print(f"Artifacts: {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
