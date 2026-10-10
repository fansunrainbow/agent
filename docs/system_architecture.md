# System Architecture

## 1. Architecture overview

```text
User / React UI
    │ Natural language only
    ▼
FastAPI → Semantic Grounding → Business Dictionary / Entity Resolver
    ▼
Structured Query Plan → Stage 4/5 Validation
    ▼
Deterministic SQL Compiler → Parameterized SQL Artifact
    ▼
Security Guard → Schema Guard → Join Guard → Cost Guard + EXPLAIN
    ▼
Read-only MySQL → Result Validator → Result Normalizer
    ▼
Customer 360 → Segment → Opportunity → Strategy → Trace / UI
```

The system deliberately does not use direct NL2SQL. Natural language is first bound to registered business semantics; SQL is produced only from a validated, typed Query Plan.

## 2. Stage architecture

### Stage 1 — Data Model

`metadata/tables.yaml` and `metadata/joins.yaml` register tables, columns, grains, time fields, entity keys, and verified join paths. Unknown tables, columns, or joins cannot be introduced by free-form generation.

### Stage 2 — Metrics

`metadata/metrics.yaml` and `metadata/metric_constraints.yaml` define formulas, sources, aggregation, grain, time semantics, null behavior, and legal dimensions. Examples include natural-calendar average assets, flow metrics, snapshots, ratios, and period boundaries.

### Stage 3 — Business Dictionary

`metadata/business_dictionary.yaml`, `value_mappings.yaml`, and `entity_rules.yaml` map business language to canonical concepts. The value path is raw input → canonical semantic value → real database storage value.

### Stage 4 — Query Plan

The Query Plan is a typed intermediate representation containing intent, subject, metrics, dimensions, filters, entity references, time range, grouping, HAVING, ordering, limit, output shape, ambiguity, and confidence. It separates language interpretation from database execution.

### Stage 5 — Agent Core

The Agent performs condition grounding, concept expansion, entity resolution, tool routing, deterministic planning, validation, and multi-turn Patch. Unknown or ambiguous requests return clarification or unsupported rather than invented semantics.

### Stage 6 — Guardrail and SQL

The deterministic compiler consumes only validated plans and emits parameterized SQL. The execution path applies Security, Schema, Join, Cost, parameter, EXPLAIN, timeout, and Result guards. The database account is SELECT-only.

### Stage 7 — Marketing

Only Stage 6 safe results enter feature building, tags, segments, opportunity rules, and strategy rules. Output preserves three layers: FACT, RULE_DECISION, and SUGGESTION. Missing evidence does not become a fabricated recommendation.

### Stage 8 — Benchmark

Dry-run evaluation measures semantic, plan, SQL, Guardrail, marketing, multi-turn, hallucination, stability, and coverage behavior. The independent 40-case Real DB Gold measures end-to-end execution equivalence against real MySQL.

### Real DB

`database/` owns connection pooling, read-only capability checks, parameter binding, EXPLAIN JSON, query timeout, and result extraction. No browser raw-SQL API exists.

### Frontend

React/Vite provides Chat, Segment, Customer 360, Marketing, Benchmark, and Trace pages. REAL_DB mode explicitly requests execution and displays Query Plan, SQL, parameters, Guardrail status, result validation, final result, latency, and trace.

## 3. Two governing principles

### Generalization

- Metadata-driven metrics, dimensions, mappings, relations, and rules.
- Generic output-shape, ranking, time, HAVING, EXISTS, and result-normalization contracts.
- No case-ID branches or query-string-specific SQL.
- Separate loaders for legacy dry-run datasets and Real DB Gold.

### Low hallucination

- Retrieval is restricted to registered semantics and real entity datasets.
- Query Plan validation rejects ungrounded fields.
- SQL compiler has no free-form table/column invention path.
- Schema and Join guards verify physical validity.
- Cost Guard fails closed even when blocking lowers Benchmark accuracy.
- Result Validator checks returned shape and size before downstream use.

## 4. Why not direct NL2SQL

Direct NL2SQL mixes language ambiguity, business definitions, physical schema, and safety into one probabilistic step. That makes it difficult to prove which metric definition was selected, whether a join changes grain, or whether a query is safe. This project introduces explicit semantic and execution contracts so each transition is independently inspectable and testable.

## 5. Trust boundaries

| Boundary | Enforcement |
|---|---|
| User → Agent | Natural language schema; no raw SQL field |
| Agent → Query Plan | Grounded IDs and typed schema |
| Query Plan → SQL | Independent validation and deterministic compiler |
| SQL → DB | Parameterization, Guardrails, EXPLAIN, timeout, SELECT-only user |
| DB → Marketing | Result validation and normalization |
| Marketing → UI | Fact/rule/suggestion separation and traceability |
