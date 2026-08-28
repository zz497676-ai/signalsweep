"""The end-to-end local workflow used by the UI and CLI."""

from .models import RunResult, WorkflowEvent
from .report import build_report
from .tools import (
    detect_anomalies,
    export_cleaned_csv,
    load_csv,
    profile_dataset,
    remove_exact_duplicate_rows,
    route_next_actions,
    run_quality_checks,
)

SAFE_APPROVED_ACTIONS = frozenset({"remove_exact_duplicates"})


def build_workflow_plan(profile) -> list[str]:
    return [
        "Profile the uploaded dataset and infer safe data types",
        "Check missing values, duplicates, and low-signal columns",
        "Detect explainable numeric outliers",
        "Route the next action from the findings",
        "Export a conservative cleaned CSV",
        "Write an action-oriented quality report",
    ]


def _record_event(
    events: list[WorkflowEvent], step: str, status: str, message: str
) -> None:
    events.append(
        WorkflowEvent(
            sequence=len(events) + 1,
            step=step,
            status=status,
            message=message,
        )
    )


def run_pipeline(
    csv_text: str,
    dataset_name: str = "uploaded.csv",
    approved_actions: list[str] | None = None,
) -> RunResult:
    approved_actions = list(approved_actions or [])
    unknown_actions = set(approved_actions) - SAFE_APPROVED_ACTIONS
    if unknown_actions:
        allowed = ", ".join(sorted(SAFE_APPROVED_ACTIONS))
        raise ValueError(f"Unsupported approved action(s); allowed: {allowed}.")

    events: list[WorkflowEvent] = []
    _record_event(events, "trigger", "completed", f"Received dataset {dataset_name!r}.")

    headers, rows = load_csv(csv_text)
    _record_event(events, "load_csv", "completed", f"Loaded {len(rows)} non-empty row(s).")

    if "remove_exact_duplicates" in approved_actions:
        rows, removed = remove_exact_duplicate_rows(headers, rows)
        _record_event(
            events,
            "apply_approved_actions",
            "completed",
            f"Removed {removed} exact duplicate row(s) after explicit approval.",
        )

    profile = profile_dataset(dataset_name, headers, rows)
    _record_event(
        events,
        "profile_dataset",
        "completed",
        f"Profiled {profile.row_count} row(s) across {len(profile.columns)} column(s).",
    )

    issues = run_quality_checks(profile, rows)
    _record_event(
        events,
        "run_quality_checks",
        "completed",
        f"Found {len(issues)} quality issue(s).",
    )

    anomalies = detect_anomalies(profile, rows)
    _record_event(
        events,
        "detect_anomalies",
        "completed",
        f"Found {len(anomalies)} explainable numeric anomaly/anomalies.",
    )

    workflow_status, actions = route_next_actions(issues, anomalies)
    _record_event(
        events,
        "route_next_actions",
        "completed",
        f"Routed workflow to {workflow_status!r}.",
    )

    cleaned_csv = export_cleaned_csv(headers, rows)
    _record_event(
        events,
        "export_normalized_copy",
        "completed",
        "Created a conservative normalized CSV without changing business values.",
    )

    report_markdown = build_report(
        profile,
        issues,
        anomalies,
        workflow_status=workflow_status,
        actions=actions,
    )
    _record_event(
        events,
        "generate_quality_report",
        "completed",
        "Generated an action-oriented Markdown report.",
    )

    final_action = actions[-1]
    final_status = "paused" if final_action.decision == "pause" else "completed"
    _record_event(events, final_action.action, final_status, final_action.reason)

    return RunResult(
        dataset_name=dataset_name,
        plan=build_workflow_plan(profile),
        profile=profile,
        issues=issues,
        anomalies=anomalies,
        cleaned_csv=cleaned_csv,
        report_markdown=report_markdown,
        workflow_status=workflow_status,
        actions=actions,
        events=events,
    )
