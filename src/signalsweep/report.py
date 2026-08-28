"""Human-readable output for the demo and eventual download."""

from .models import ActionDecision, Anomaly, DatasetProfile, QualityIssue


def build_report(
    profile: DatasetProfile,
    issues: list[QualityIssue],
    anomalies: list[Anomaly],
    workflow_status: str = "complete",
    actions: list[ActionDecision] | None = None,
) -> str:
    actions = actions or []
    lines = [
        f"# SignalSweep report: `{profile.name}`",
        "",
        "## Executive summary",
        "",
        f"- Rows analyzed: **{profile.row_count}**",
        f"- Columns: **{len(profile.columns)}**",
        f"- Numeric columns: **{', '.join(profile.numeric_columns) or 'none detected'}**",
        f"- Quality issues: **{len(issues)}**",
        f"- Potential anomalies: **{len(anomalies)}**",
        "",
        "## Taskmaster decision",
        "",
        f"- Workflow status: **{workflow_status}**",
        "",
    ]

    if actions:
        lines.extend(["| Action | Decision | Priority | Human review | Reason |", "| --- | --- | --- | --- | --- |"])
        for action in actions:
            review = "yes" if action.requires_human_review else "no"
            lines.append(
                f"| `{action.action}` | `{action.decision}` | `{action.priority}` | "
                f"{review} | {action.reason} |"
            )
        lines.append("")

    lines.extend(
        [
            "## Recommended actions",
            "",
        ]
    )

    if not issues and not anomalies:
        lines.append("No material issues were detected in the current MVP checks.")
    else:
        if issues:
            lines.append("### Quality issues")
            lines.append("")
            for issue in issues:
                lines.append(f"- **{issue.severity}** `{issue.code}` on `{issue.column}`: {issue.message}")
            lines.append("")
        if anomalies:
            lines.append("### Potential anomalies")
            lines.append("")
            for anomaly in anomalies:
                lines.append(
                    f"- Row {anomaly.row_number}, `{anomaly.column}` = `{anomaly.value}` "
                    f"(score {anomaly.score}): {anomaly.reason}"
                )
            lines.append("")

    lines.extend(
        [
            "## Method",
            "",
            (
                "SignalSweep used deterministic Python tools for profiling, quality checks, "
                "explainable numeric outlier detection, and safe action routing. The Gemini + "
                "Google ADK layer can call the same tools and expose this trace in the agentic version."
            ),
        ]
    )
    return "\n".join(lines) + "\n"
