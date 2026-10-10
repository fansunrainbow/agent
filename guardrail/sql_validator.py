from __future__ import annotations

from .cost_guard import CostGuard
from .models import GuardIssue, GuardResult, SQLArtifact, ValidationReport
from .parser.sql_ast import SQLParseError, parse_sql
from .schema_guard import SchemaGuard
from .security_guard import SecurityGuard


class SQLValidator:
    def __init__(self) -> None:
        self.security = SecurityGuard()
        self.schema = SchemaGuard()
        self.cost = CostGuard(self.schema.catalog)

    def validate(self, value: SQLArtifact | str) -> ValidationReport:
        artifact = value if isinstance(value, SQLArtifact) else None
        sql = artifact.sql if artifact else value
        try:
            ast = parse_sql(sql)
        except SQLParseError as exc:
            result = GuardResult("parser", False, [GuardIssue("SQL_PARSE_ERROR", str(exc))])
            return ValidationReport(False, None, [result])
        checks = [self.security.check(ast), self.schema.check(ast, artifact), self.cost.check(ast, artifact)]
        if artifact:
            expected, actual = set(ast.parameters), set(artifact.params)
            issues = []
            if expected - actual:
                issues.append(GuardIssue("MISSING_SQL_PARAMETER", "SQL 参数未提供。", evidence=sorted(expected - actual)))
            if actual - expected:
                issues.append(GuardIssue("UNUSED_SQL_PARAMETER", "参数字典包含 SQL 未引用的值。", evidence=sorted(actual - expected)))
            checks.append(GuardResult("parameters", not issues, issues))
        return ValidationReport(all(check.allowed for check in checks), ast, checks)
