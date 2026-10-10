# Stage 6 Guardrail Architecture

Stage 6 has one executable input contract: a Stage 5 Query Plan whose `status` is `ready` and whose validation result is valid. `SQLGenerator` independently runs the Stage 4 validator again, so a forged or stale validation flag cannot bypass the boundary.

```text
Validated Query Plan
  -> LogicalPlanner (registry IDs and dependency graph only)
  -> SQLGenerator (deterministic CTE compiler + named parameters)
  -> SQL AST parser
  -> SecurityGuard + SchemaGuard + CostGuard + ParameterGuard
  -> read-only ExecutionManager
  -> ResultValidator
  -> audit trace
```

## Compiler design

- Every requested leaf metric is compiled from `metadata/metrics.yaml` into a customer-grain CTE.
- Derived metrics are compiled only from their declared `derived_from` dependencies.
- Multiple fact tables are never joined directly. Each fact is first grouped to `pty_id`; metric CTEs are then joined at that shared grain.
- Dimensions are resolved through `metadata/dimensions.yaml`. The current customer-grain compiler accepts only dimensions safely projected from `ads_cust_info_d`; an unknown route is blocked instead of guessed.
- Product-category metrics join `dim_product` only through a verified entry in `metadata/joins.yaml`.
- Query Plan values, time boundaries, internal metric category values, entity IDs and limits are named parameters. SQL text contains no user value.
- SQL generation never receives the original user utterance and never calls an LLM.

## Execution boundary

`ExecutionManager.dry_run()` is the default demonstration path. Real execution requires an explicitly injected DB-API connection. The connection must support `set_session(readonly=True)` or expose `read_only=True`. Production deployment must additionally use a database account such as `agent_readonly_user` whose database grants allow only `SELECT`.

The trace records the query ID, complete Query Plan, SQL text, parameter names (not secret values), all guard results, attempt count, elapsed time, result validation and classified execution errors.

## Run locally

Interactive Stage 5 -> Stage 6 dry-run:

```powershell
python scripts/run_guardrail_demo.py
```

Single question:

```powershell
python scripts/run_guardrail_demo.py "2026年Q1南京客户的日均资产是多少？"
```

Run Stage 6 tests:

```powershell
python -m pytest tests/guardrail -q
```
