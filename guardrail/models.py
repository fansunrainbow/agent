from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


Severity = Literal["warning", "block"]


@dataclass
class GuardIssue:
    code: str
    message: str
    severity: Severity = "block"
    path: str | None = None
    evidence: Any | None = None

    def to_dict(self) -> dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if value is not None}


@dataclass
class GuardResult:
    guard: str
    allowed: bool
    issues: list[GuardIssue] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def errors(self) -> list[GuardIssue]:
        return [item for item in self.issues if item.severity == "block"]

    @property
    def warnings(self) -> list[GuardIssue]:
        return [item for item in self.issues if item.severity == "warning"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "guard": self.guard,
            "allowed": self.allowed,
            "issues": [item.to_dict() for item in self.issues],
            "details": self.details,
        }


@dataclass
class SQLArtifact:
    query_id: str
    sql: str
    params: dict[str, Any]
    query_plan: dict[str, Any]
    dialect: str = "mysql"
    logical_plan: dict[str, Any] = field(default_factory=dict)
    metric_aliases: list[str] = field(default_factory=list)
    selected_columns: list[str] = field(default_factory=list)
    source_tables: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ValidationReport:
    allowed: bool
    ast: Any | None
    checks: list[GuardResult]

    @property
    def issues(self) -> list[GuardIssue]:
        return [issue for check in self.checks for issue in check.issues]

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "checks": [check.to_dict() for check in self.checks],
            "issues": [issue.to_dict() for issue in self.issues],
            "ast": self.ast.to_dict() if self.ast is not None else None,
        }
