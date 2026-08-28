"""Google ADK hook for the agentic milestone.

The local MVP remains usable when google-adk is not installed. Once the
dependencies and Gemini credentials are available, ``root_agent`` exposes a
small ADK agent whose tools call the same deterministic Python functions used
by the local workflow.
"""

from __future__ import annotations

import os

from .pipeline import run_pipeline

try:  # Keep the local data workflow dependency-light.
    from google.adk.agents.llm_agent import Agent
except ModuleNotFoundError:  # pragma: no cover - depends on optional install.
    Agent = None


def profile_csv_tool(csv_text: str) -> dict:
    result = run_pipeline(csv_text)
    return {
        "dataset": result.dataset_name,
        "rows": result.profile.row_count,
        "columns": result.profile.columns,
        "numeric_columns": result.profile.numeric_columns,
        "missing_by_column": result.profile.missing_by_column,
        "duplicate_rows": result.profile.duplicate_rows,
    }


def quality_report_tool(csv_text: str) -> dict:
    result = run_pipeline(csv_text)
    return {
        "issues": [issue.__dict__ for issue in result.issues],
        "anomalies": [anomaly.__dict__ for anomaly in result.anomalies],
        "workflow_status": result.workflow_status,
        "actions": [action.__dict__ for action in result.actions],
        "events": [event.__dict__ for event in result.events],
        "report_markdown": result.report_markdown,
        "cleaned_csv": result.cleaned_csv,
    }


def taskmaster_workflow_tool(
    csv_text: str, dataset_name: str = "uploaded.csv"
) -> dict:
    """Run the complete inspectable Taskmaster workflow."""

    return run_pipeline(csv_text, dataset_name).to_dict()


AGENT_INSTRUCTION = """
You are SignalSweep, an autonomous data-quality agent.

Given a messy CSV, make a plan before acting. Use the Python tools to profile
the data, check quality, detect explainable anomalies, route the next action,
and produce a report.
Do not invent values or silently overwrite data. Explain what you found, show
which tools ran, and pause for human review when an action is uncertain.
""".strip()


def build_root_agent():
    if Agent is None:
        return None
    return Agent(
        name="signalsweep_agent",
        model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash"),
        description="Autonomous data-quality workflow agent for messy CSV files.",
        instruction=AGENT_INSTRUCTION,
        tools=[profile_csv_tool, taskmaster_workflow_tool],
    )


root_agent = build_root_agent()
