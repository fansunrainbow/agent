# Hallucination Control

The system treats hallucination control as a sequence of enforceable contracts, not a prompt-only instruction. When evidence is absent or ambiguous, the preferred behavior is clarification, unsupported, or fail closed.

| Risk | Primary controls | Failure behavior |
|---|---|---|
| Hallucinated Table | `tables.yaml`, deterministic compiler, Schema Guard | Unknown table blocked |
| Hallucinated Column | Dimension/metric source metadata, AST extraction, Schema Guard | Unknown column blocked |
| Hallucinated Metric | `metrics.yaml`, Metric Tool, grounded-ID check, Plan Validator | Unsupported or clarification |
| Hallucinated Entity | Entity Resolver over controlled data, ambiguity policy | Not-found/ambiguous; no guessed ID |
| Hallucinated Time | Typed time parser, metric constraints, effective fact-date selection | Clarification or compile failure |
| Hallucinated Relation | `entity_relations.yaml`, verified joins, Join Guard | Unknown/unverified relation blocked |
| Hallucinated Result | Real DB execution, Result Validator, Result Normalizer, FACT provenance | Result blocked; no demo fallback |

## Defense layers

1. **Metadata** registers the only legal physical and business vocabulary.
2. **Business Dictionary** expands controlled concepts and preserves source evidence.
3. **Entity Resolver** searches real entity data, requires uniqueness, and exposes candidates when ambiguous.
4. **Structured Query Plan** makes metrics, dimensions, filters, time, grouping, ordering, and output shape explicit.
5. **Stage 4/5 Validator** rejects ungrounded or unsupported semantics before SQL exists.
6. **Deterministic SQL Compiler** maps validated IDs to registered expressions and parameterized values.
7. **Security Guard** restricts statements and dangerous syntax.
8. **Schema Guard** checks every physical table and column.
9. **Join Guard** permits only verified paths and keys.
10. **Cost Guard** uses EXPLAIN and blocks excessive plans without raising thresholds for Benchmark score.
11. **Result Validator** checks row count and result safety.
12. **Result Normalizer** stabilizes Decimal/date/NULL/row representations and ordering.

## Clarification and fail-closed policy

- Unknown registered boundary → `unsupported`.
- Multiple entity candidates → `needs_clarification`.
- Required time absent → clarification; never invent a quarter.
- Unsafe or excessive SQL → `blocked`.
- Real DB failure → explicit error; never substitute fixture data.
- Missing marketing evidence → no fabricated tag, opportunity, or strategy.

## Measured evidence

- Frozen Dry-run hallucination suite: 20/20 handled correctly.
- Guardrail suite: unsafe block rate 100%; no recorded false negative.
- Second Frozen Real DB Benchmark: four high-cost queries remained failures because the system kept the safety boundary.
