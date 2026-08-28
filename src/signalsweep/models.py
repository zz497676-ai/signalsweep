"""Small, dependency-light data models used by the local MVP."""

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class DatasetProfile:
    name: str
    row_count: int
    columns: list[str]
    numeric_columns: list[str]
    missing_by_column: dict[str, int]
    duplicate_rows: int
    sample_rows: list[dict[str, str]]


@dataclass(frozen=True)
class QualityIssue:
    code: str
    column: str
    count: int
    severity: str
    message: str


@dataclass(frozen=True)
class Anomaly:
    row_number: int
    column: str
    value: str
    score: float
    reason: str


@dataclass(frozen=True)
class ActionDecision:
    """A routing decision made after the data findings are known."""

    action: str
    decision: str
    priority: str
    reason: str
    requires_human_review: bool = False


@dataclass(frozen=True)
class WorkflowEvent:
    """An append-only event that makes a Taskmaster run inspectable."""

    sequence: int
    step: str
    status: str
    message: str


@dataclass
class RunResult:
    dataset_name: str
    plan: list[str]
    profile: DatasetProfile
    issues: list[QualityIssue] = field(default_factory=list)
    anomalies: list[Anomaly] = field(default_factory=list)
    cleaned_csv: str = ""
    report_markdown: str = ""
    workflow_status: str = "complete"
    actions: list[ActionDecision] = field(default_factory=list)
    events: list[WorkflowEvent] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Return a JSON-friendly snapshot for CLI, ADK, and Firestore later."""

        return asdict(self)
