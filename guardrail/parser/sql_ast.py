from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Any


class SQLParseError(ValueError):
    pass


@dataclass(frozen=True)
class Token:
    kind: str
    value: str


@dataclass
class TableRef:
    name: str
    alias: str
    source: str


@dataclass
class ColumnRef:
    table_alias: str | None
    name: str


@dataclass
class JoinRef:
    right_table: str
    right_alias: str
    join_type: str
    left_alias: str | None = None
    left_column: str | None = None
    right_column: str | None = None


@dataclass
class SQLAst:
    statement_type: str
    tokens: list[Token]
    ctes: list[str] = field(default_factory=list)
    tables: list[TableRef] = field(default_factory=list)
    columns: list[ColumnRef] = field(default_factory=list)
    unqualified_identifiers: list[str] = field(default_factory=list)
    joins: list[JoinRef] = field(default_factory=list)
    functions: list[str] = field(default_factory=list)
    parameters: list[str] = field(default_factory=list)
    literals: list[str] = field(default_factory=list)
    forbidden_keywords: list[str] = field(default_factory=list)
    has_wildcard: bool = False
    has_comments: bool = False
    statement_count: int = 1
    limit: int | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("tokens", None)
        return data


TOKEN_RE = re.compile(
    r"(?P<SPACE>\s+)|(?P<COMMENT>--[^\r\n]*|/\*.*?\*/)|"
    r"(?P<PARAM>:[A-Za-z_][A-Za-z0-9_]*)|"
    r"(?P<STRING>'(?:''|[^'])*')|(?P<QUOTED>`[^`]+`)|"
    r"(?P<NUMBER>\d+(?:\.\d+)?)|(?P<OP><=|>=|<>|!=|=|<|>|\+|-|/|%)|"
    r"(?P<PUNCT>[(),.;])|(?P<STAR>\*)|(?P<IDENT>[A-Za-z_][A-Za-z0-9_$]*)|"
    r"(?P<OTHER>.)", re.DOTALL,
)

KEYWORDS = {
    "SELECT", "FROM", "WHERE", "JOIN", "LEFT", "RIGHT", "INNER", "OUTER", "FULL", "CROSS", "ON",
    "AS", "WITH", "GROUP", "BY", "HAVING", "ORDER", "LIMIT", "ASC", "DESC", "AND", "OR", "NOT",
    "IN", "IS", "NULL", "DISTINCT", "CASE", "WHEN", "THEN", "ELSE", "END", "BETWEEN", "LIKE",
    "UNION", "ALL", "OFFSET", "TRUE", "FALSE", "EXISTS",
}
FORBIDDEN = {"INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE", "REPLACE", "MERGE", "CALL", "GRANT", "REVOKE", "LOAD", "INTO", "OUTFILE"}


def tokenize(sql: str) -> tuple[list[Token], bool]:
    tokens: list[Token] = []
    has_comments = False
    for match in TOKEN_RE.finditer(sql):
        kind = match.lastgroup or "OTHER"
        value = match.group()
        if kind == "SPACE":
            continue
        if kind == "COMMENT":
            has_comments = True
            continue
        if kind == "OTHER":
            raise SQLParseError(f"unsupported SQL character: {value!r}")
        if kind == "QUOTED":
            kind, value = "IDENT", value[1:-1]
        tokens.append(Token(kind, value))
    if not tokens:
        raise SQLParseError("empty SQL")
    return tokens, has_comments


def _upper(token: Token) -> str:
    return token.value.upper() if token.kind == "IDENT" else token.value


def _next_ident(tokens: list[Token], start: int) -> tuple[str | None, int]:
    if start < len(tokens) and tokens[start].kind == "IDENT":
        return tokens[start].value, start + 1
    return None, start


def parse_sql(sql: str) -> SQLAst:
    tokens, has_comments = tokenize(sql)
    semicolons = [i for i, token in enumerate(tokens) if token.value == ";"]
    statement_count = 1 + sum(1 for i in semicolons if i != len(tokens) - 1)
    words = [_upper(token) for token in tokens]
    forbidden = sorted({word for word in words if word in FORBIDDEN})

    ctes: list[str] = []
    first = words[0]
    statement_type = first
    if first == "WITH":
        depth = 0
        index = 1
        while index < len(tokens):
            if depth == 0 and tokens[index].kind == "IDENT" and index + 1 < len(tokens) and words[index + 1] == "AS":
                ctes.append(tokens[index].value)
            if tokens[index].value == "(":
                depth += 1
            elif tokens[index].value == ")":
                depth = max(0, depth - 1)
            elif depth == 0 and words[index] == "SELECT":
                statement_type = "SELECT"
                break
            index += 1

    tables: list[TableRef] = []
    joins: list[JoinRef] = []
    aliases: dict[str, str] = {}
    for index, word in enumerate(words):
        if word not in {"FROM", "JOIN"} or index + 1 >= len(tokens):
            continue
        name, pos = _next_ident(tokens, index + 1)
        if name is None:
            continue
        alias = name
        if pos < len(tokens) and words[pos] == "AS":
            alias, pos = _next_ident(tokens, pos + 1)
            alias = alias or name
        elif pos < len(tokens) and tokens[pos].kind == "IDENT" and words[pos] not in KEYWORDS | FORBIDDEN:
            alias = tokens[pos].value
        aliases[alias] = name
        tables.append(TableRef(name=name, alias=alias, source=word.lower()))
        if word == "JOIN":
            join_type = "inner"
            if index > 0 and words[index - 1] in {"LEFT", "RIGHT", "INNER", "FULL", "CROSS"}:
                join_type = words[index - 1].lower()
            join = JoinRef(right_table=name, right_alias=alias, join_type=join_type)
            on_index = next((p for p in range(pos, min(len(tokens), pos + 20)) if words[p] == "ON"), None)
            if on_index is not None:
                qualified = []
                for p in range(on_index + 1, min(len(tokens) - 2, on_index + 14)):
                    if tokens[p].kind == "IDENT" and tokens[p + 1].value == "." and tokens[p + 2].kind == "IDENT":
                        qualified.append((tokens[p].value, tokens[p + 2].value))
                if len(qualified) >= 2:
                    (join.left_alias, join.left_column), (_, join.right_column) = qualified[:2]
            joins.append(join)

    functions = sorted({tokens[i].value.upper() for i in range(len(tokens) - 1) if tokens[i].kind == "IDENT" and tokens[i + 1].value == "(" and _upper(tokens[i]) not in KEYWORDS})
    columns: list[ColumnRef] = []
    for i in range(len(tokens) - 2):
        if tokens[i].kind == "IDENT" and tokens[i + 1].value == "." and tokens[i + 2].kind == "IDENT":
            columns.append(ColumnRef(tokens[i].value, tokens[i + 2].value))
    excluded = set(ctes) | set(aliases) | set(aliases.values()) | set(functions)
    unqualified: set[str] = set()
    for i, token in enumerate(tokens):
        if token.kind != "IDENT" or _upper(token) in KEYWORDS | FORBIDDEN:
            continue
        if token.value in excluded:
            continue
        previous = tokens[i - 1].value if i else None
        following = tokens[i + 1].value if i + 1 < len(tokens) else None
        if previous == "." or following in {".", "("} or (i and words[i - 1] == "AS"):
            continue
        if i and words[i - 1] in {"FROM", "JOIN"}:
            continue
        unqualified.add(token.value)
    parameters = [token.value[1:] for token in tokens if token.kind == "PARAM"]
    literals = [token.value for token in tokens if token.kind in {"STRING", "NUMBER"}]
    has_wildcard = any(token.kind == "STAR" for token in tokens)
    limit = None
    for i, word in enumerate(words[:-1]):
        if word == "LIMIT" and tokens[i + 1].kind == "NUMBER":
            limit = int(float(tokens[i + 1].value))
    return SQLAst(
        statement_type=statement_type, tokens=tokens, ctes=ctes, tables=tables, columns=columns,
        unqualified_identifiers=sorted(unqualified),
        joins=joins, functions=functions, parameters=parameters, literals=literals,
        forbidden_keywords=forbidden, has_wildcard=has_wildcard, has_comments=has_comments,
        statement_count=statement_count, limit=limit,
    )
