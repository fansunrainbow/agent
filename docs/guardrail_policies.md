# Stage 6 Guardrail Policies

The executable policy files are under `guardrail/policies/`.

## SQL AST and security

- Allow only one `SELECT` statement; a `WITH` clause must resolve to `SELECT`.
- Block DML, DDL, privilege, procedure and outfile keywords.
- Block comments, multiple statements, wildcard selection and functions outside the allowlist.
- Block quoted business literals and numeric literals other than the metadata formula constant zero.
- Require an exact match between named placeholders in the AST and the parameter dictionary.

The parser tokenizes SQL and extracts statement type, CTEs, tables, aliases, columns, joins, functions, parameters, literals, wildcard and limit. Guards inspect this AST; they do not rely only on substring matching.

## Schema and Join Guard

- Every physical table and qualified column must exist in `metadata/tables.yaml`.
- Unqualified identifiers must resolve to a registered column or an explicitly selected output alias.
- Physical table joins must match both the table pair and key columns in a verified join registry entry.
- Direct fact-to-fact joins are blocked. Cross-fact metrics require preaggregation provenance at a shared key.
- Metric source tables, source fields and aggregation contracts are copied into the logical plan and compared with `metadata/metrics.yaml` before execution.

## Cost Guard

- Maximum joins: 8.
- Maximum returned rows: 10,000; default detail limit: 1,000.
- Maximum metadata-estimated scan: 1,000,000 rows.
- Every fact table must have a registered time-column predicate.
- Configured execution timeout: 30 seconds. A production DB adapter must apply this as a driver/server statement timeout; elapsed time remains in the trace.

## Result Validator

- Empty results are explicit warnings, never fabricated into data.
- Results above the maximum row count are blocked.
- NaN and Infinity are blocked.
- `customer_count` must be a non-negative integer.
- Ratio/rate metrics must remain in `[0, 1]`.
- Repeated `pty_id` beyond the configured amplification threshold is treated as probable Join amplification and blocked.

## Error policy

Database exceptions are mapped to stable codes (`DB_TIMEOUT`, `DB_PERMISSION_DENIED`, `DB_SCHEMA_MISMATCH`, `DB_SQL_SYNTAX`, `DB_EXECUTION_ERROR`). They are never sent to an LLM for free-form SQL repair. A new SQL artifact must pass the complete validator again before any retry.
