from __future__ import annotations

from .models import GuardIssue, GuardResult
from .parser.sql_ast import SQLAst
from .policy import load_policy


class SecurityGuard:
    def __init__(self) -> None:
        self.policy = load_policy("sql_policy.yaml")

    def check(self, ast: SQLAst) -> GuardResult:
        issues: list[GuardIssue] = []
        if ast.statement_type not in set(self.policy["allowed_statements"]):
            issues.append(GuardIssue("SQL_STATEMENT_FORBIDDEN", f"仅允许 SELECT，收到 {ast.statement_type}。"))
        if ast.forbidden_keywords:
            issues.append(GuardIssue("SQL_KEYWORD_FORBIDDEN", "SQL 包含写入或管理类关键字。", evidence=ast.forbidden_keywords))
        if ast.statement_count != 1:
            issues.append(GuardIssue("MULTI_STATEMENT_FORBIDDEN", "禁止执行多语句 SQL。", evidence=ast.statement_count))
        if ast.has_comments and not self.policy.get("allow_comments", False):
            issues.append(GuardIssue("SQL_COMMENT_FORBIDDEN", "SQL 注释可能隐藏指令，已拒绝。"))
        if ast.has_wildcard and not self.policy.get("allow_wildcard", False):
            issues.append(GuardIssue("WILDCARD_FORBIDDEN", "禁止 SELECT *，必须显式列出输出字段。"))
        disallowed_functions = sorted(set(ast.functions) - set(self.policy["allowed_functions"]))
        if disallowed_functions:
            issues.append(GuardIssue("FUNCTION_NOT_ALLOWED", "SQL 使用了未列入白名单的函数。", evidence=disallowed_functions))
        if ast.literals and not self.policy.get("allow_string_literals", False):
            string_literals = [value for value in ast.literals if value.startswith("'")]
            if string_literals:
                issues.append(GuardIssue("UNPARAMETERIZED_LITERAL", "业务值必须通过参数传入。", evidence=string_literals))
            allowed_numeric = {str(item) for item in self.policy.get("allowed_numeric_literals", [])}
            numeric_literals = [value for value in ast.literals if not value.startswith("'") and value not in allowed_numeric]
            if numeric_literals:
                issues.append(GuardIssue("UNPARAMETERIZED_LITERAL", "数值业务参数必须通过参数传入。", evidence=numeric_literals))
        return GuardResult("security", not any(item.severity == "block" for item in issues), issues)
