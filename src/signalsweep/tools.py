"""Real Python tools that the agent will call."""

from __future__ import annotations

import csv
import math
import statistics
from collections import Counter
from io import StringIO

from .models import ActionDecision, Anomaly, DatasetProfile, QualityIssue


def load_csv(csv_text: str) -> tuple[list[str], list[dict[str, str]]]:
    """Parse a CSV upload and normalize headers and cell whitespace."""

    if not csv_text.strip():
        raise ValueError("The uploaded CSV is empty.")

    reader = csv.DictReader(StringIO(csv_text.lstrip("\ufeff")))
    if not reader.fieldnames:
        raise ValueError("The CSV must contain a header row.")

    headers = [header.strip() for header in reader.fieldnames]
    if not all(headers):
        raise ValueError("CSV headers cannot be empty.")
    if len(set(headers)) != len(headers):
        raise ValueError("CSV headers must be unique.")

    rows: list[dict[str, str]] = []
    for raw_row in reader:
        row = {header: (raw_row.get(original) or "").strip() for header, original in zip(headers, reader.fieldnames)}
        if any(value for value in row.values()):
            rows.append(row)
    return headers, rows


def _to_number(value: str) -> float | None:
    cleaned = value.strip().replace(",", "")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _numeric_values(rows: list[dict[str, str]], column: str) -> list[tuple[int, float]]:
    values: list[tuple[int, float]] = []
    for row_number, row in enumerate(rows, start=2):
        number = _to_number(row.get(column, ""))
        if number is not None and math.isfinite(number):
            values.append((row_number, number))
    return values


def profile_dataset(name: str, headers: list[str], rows: list[dict[str, str]]) -> DatasetProfile:
    """Create a compact profile used by the planner and the UI."""

    missing_by_column = {
        column: sum(not row.get(column, "").strip() for row in rows)
        for column in headers
    }
    numeric_columns = []
    for column in headers:
        values = _numeric_values(rows, column)
        non_empty = sum(bool(row.get(column, "").strip()) for row in rows)
        if non_empty and len(values) / non_empty >= 0.6:
            numeric_columns.append(column)

    fingerprints = [tuple(row.get(column, "") for column in headers) for row in rows]
    duplicate_rows = len(fingerprints) - len(set(fingerprints))
    return DatasetProfile(
        name=name,
        row_count=len(rows),
        columns=headers,
        numeric_columns=numeric_columns,
        missing_by_column=missing_by_column,
        duplicate_rows=duplicate_rows,
        sample_rows=rows[:5],
    )


def run_quality_checks(profile: DatasetProfile, rows: list[dict[str, str]]) -> list[QualityIssue]:
    """Find issues that can be explained and fixed without guessing."""

    issues: list[QualityIssue] = []
    for column, count in profile.missing_by_column.items():
        if count:
            severity = "high" if count / max(profile.row_count, 1) >= 0.2 else "medium"
            issues.append(
                QualityIssue(
                    code="missing_values",
                    column=column,
                    count=count,
                    severity=severity,
                    message=f"{count} row(s) have no value in {column!r}.",
                )
            )

    if profile.duplicate_rows:
        issues.append(
            QualityIssue(
                code="duplicate_rows",
                column="*",
                count=profile.duplicate_rows,
                severity="medium",
                message=f"{profile.duplicate_rows} duplicate row(s) were detected.",
            )
        )

    for column in profile.columns:
        values = [row.get(column, "") for row in rows if row.get(column, "")]
        if values:
            counts = Counter(values)
            if len(counts) == 1 and profile.row_count >= 3:
                issues.append(
                    QualityIssue(
                        code="constant_column",
                        column=column,
                        count=profile.row_count,
                        severity="low",
                        message=f"{column!r} has the same value in every populated row.",
                    )
                )
    return issues


def detect_anomalies(profile: DatasetProfile, rows: list[dict[str, str]]) -> list[Anomaly]:
    """Detect simple, explainable numeric outliers with a z-score."""

    anomalies: list[Anomaly] = []
    for column in profile.numeric_columns:
        values = _numeric_values(rows, column)
        numbers = [number for _, number in values]
        if len(numbers) < 4:
            continue
        mean = statistics.mean(numbers)
        deviation = statistics.pstdev(numbers)
        if deviation == 0:
            continue
        for row_number, number in values:
            score = abs((number - mean) / deviation)
            if score >= 2.5:
                anomalies.append(
                    Anomaly(
                        row_number=row_number,
                        column=column,
                        value=str(number),
                        score=round(score, 2),
                        reason=f"Value is {score:.2f} standard deviations from the column mean ({mean:.2f}).",
                    )
                )
    return anomalies


def route_next_actions(
    issues: list[QualityIssue], anomalies: list[Anomaly]
) -> tuple[str, list[ActionDecision]]:
    """Choose safe next actions from explainable findings.

    SignalSweep never silently deletes or repairs user data. It can always
    create a normalized copy and a report, but it pauses for human review when
    quality findings or statistical anomalies need a business decision.
    """

    actions = [
        ActionDecision(
            action="export_normalized_copy",
            decision="execute",
            priority="medium",
            reason="Create a trimmed, blank-row-free copy without changing business values.",
        ),
        ActionDecision(
            action="generate_quality_report",
            decision="execute",
            priority="medium",
            reason="Record the findings, methods, and recommended follow-up actions.",
        ),
    ]

    high_or_medium_issues = [
        issue for issue in issues if issue.severity in {"high", "medium"}
    ]
    if high_or_medium_issues or anomalies:
        reasons: list[str] = []
        if high_or_medium_issues:
            reasons.append(f"{len(high_or_medium_issues)} material quality issue(s)")
        if anomalies:
            reasons.append(f"{len(anomalies)} explainable numeric anomaly/anomalies")
        actions.append(
            ActionDecision(
                action="request_human_review",
                decision="pause",
                priority="high",
                reason=" and ".join(reasons) + " require a human decision before any destructive fix.",
                requires_human_review=True,
            )
        )
        return "needs_review", actions

    actions.append(
        ActionDecision(
            action="mark_dataset_ready",
            decision="complete",
            priority="low",
            reason="No material quality issue or explainable anomaly requires escalation.",
        )
    )
    return "ready", actions


def export_cleaned_csv(headers: list[str], rows: list[dict[str, str]]) -> str:
    """Return a conservative cleaned copy: trim cells and remove blank rows."""

    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=headers, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        normalized = {header: (row.get(header) or "").strip() for header in headers}
        if any(normalized.values()):
            writer.writerow(normalized)
    return buffer.getvalue()


def remove_exact_duplicate_rows(
    headers: list[str], rows: list[dict[str, str]]
) -> tuple[list[dict[str, str]], int]:
    """Remove only byte-for-byte duplicate records after explicit approval."""

    seen: set[tuple[str, ...]] = set()
    unique_rows: list[dict[str, str]] = []
    removed = 0
    for row in rows:
        fingerprint = tuple((row.get(header) or "").strip() for header in headers)
        if fingerprint in seen:
            removed += 1
            continue
        seen.add(fingerprint)
        unique_rows.append(dict(row))
    return unique_rows, removed
