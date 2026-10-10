# Final System Acceptance Report

## Executive result

The second frozen 40-case Real DB Benchmark completed against the read-only MySQL account. Gold integrity, full regression, frontend REAL_DB E2E, minute-level latency, and the 90% final-execution target all passed. Final execution accuracy is **36/40 (90.00%)** with no PASS-to-FAIL regression.

`AGENT_FINAL_READY = YES`

## Submission Freeze — 2026-10-08

| Gate | Final state |
|---|---|
| REAL_DB_GATE | PASS |
| GOLD_FREEZE | PASS |
| SECOND_FROZEN_BENCHMARK | PASS |
| FINAL_EXECUTION_ACCURACY | 36/40 = 90.00% |
| MINUTE_LEVEL_REQUIREMENT | PASS |
| FRONTEND_REAL_DB_E2E | PASS (14/14) |
| FULL_REGRESSION | PASS (Python 241/241; frontend 14/14; build PASS) |
| UI_PRESENTATION_AUDIT | PASS |
| SECRET_PRIVACY_AUDIT | PASS |
| RELEASE_INTEGRITY_CHECK | PASS (`mode=full`; Real DB benchmark not executed) |
| SUBMISSION_PACKAGE_AUDIT | PASS |
| AGENT_FINAL_READY | YES |

Frozen Gold SHA-256: `602496D8308DD391F4184F2A63A256E6942AF21F3FE3A1D6111987B3EAEB4FCD`.

Post-freeze delivery remediation added one packaging/deployment-boundary test, so
the current source total is 241 rather than the 240 recorded inside the immutable
Second Frozen benchmark artifact. No Agent, Query Plan, SQL compiler, Guardrail,
Gold, or measured Real DB result was changed.

No third Frozen Real DB Benchmark is authorized or required. The four remaining cases are transparently retained as `COST_BLOCK`: RDB_M06, RDB_M07, RDB_C01, and RDB_C11.

## MT_009 Hotfix

PASS. Explicit mutations now succeed or fail closed. MT_009 returns `needs_clarification`; Patch audit records operation, target, old value, requested value, resolution, Patch status, and status transition. No case-ID or fixed-query branch was added.

## Real DB configuration and verification (superseded)

- Environment contract, `.env.example`, and `.env` exclusion: complete.
- SQLAlchemy/PyMySQL pool adapter: complete.
- Read-only session, timeout, parameter binding, EXPLAIN JSON, real-cost estimate, and Result Validator: complete.
- DBA user template: complete.
- Live connection and read-only grants: **PASS**.

## Earlier Real DB Benchmark status (superseded)

The earlier unmeasured status below is superseded by the measured final section appended to this report.

## Frontend

Stack: FastAPI + React + Vite. Pages: 智能问数、智能圈客、Customer 360、营销洞察、Benchmark、Trace / Guardrail. SQL/params are separate; Query Plan has structured/raw views; Guardrail has PASS/WARN/BLOCK; FACT/RULE_DECISION/SUGGESTION are visually separate; identity is masked; modes are explicit.

API: `POST /api/chat`, `GET /api/conversations/{id}`, `GET /api/query/{id}/plan`, `GET /api/query/{id}/sql`, `GET /api/query/{id}/trace`, `GET /api/customer/{id}/profile`, `POST /api/segments/evaluate`, `GET /api/opportunities`, `GET /api/benchmark/summary`, `GET /api/health`.

The request schema forbids extra fields, so clients cannot submit raw SQL.

Verification: Python `205/205`; frontend `12/12`; Vite production build PASS; CLI dry-run PASS; `/api/health` and built `/` both return HTTP 200.

## Historical pre-remediation E2E status

Dry-run semantic/plan/SQL/Guardrail flows are covered, including clarification, unsupported boundaries, multi-turn Patch, MT_009, marketing, Guardrail blocking, and Benchmark presentation. True User → Real DB → Result → Marketing cases require a live database and are not marked PASS.

## Earlier known limitations (superseded)

The earlier missing-database, missing-Gold, and disconnected Customer 360/Marketing limitations are superseded by the Second Frozen section below.

## Checklist

- [x] MT_009 silent-ignore fixed
- [x] Guardrail remains mandatory
- [x] Read-only integration and self-check implemented
- [x] Stage 9 frontend implemented
- [x] Real DB / Dry-run clearly distinguished
- [x] Real read-only MySQL connected and grants observed
- [x] Real execution benchmark completed
- [x] Final real End-to-End acceptance passed

---

## First Frozen Real DB Benchmark — measured 2026-10-08 (historical baseline)

- Gold: **40 reviewed**; 12 simple / 16 medium / 12 complex.
- Frozen SHA-256: `602496D8308DD391F4184F2A63A256E6942AF21F3FE3A1D6111987B3EAEB4FCD` — **PASS**.
- SQL Execution Success: **30/40 (75.00%)**.
- Scalar: **10/19 (52.63%)**; Set: **5/11 (45.45%)**; Grouped: **3/6 (50.00%)**; Ranking: **0/3**; Time Series: **0/1**.
- Result Equivalence / Final Execution Accuracy: **18/40 (45.00%)**.
- `NATURAL_LANGUAGE_FINAL_EXECUTION_ACCURACY_TARGET = FAIL`.

Agent-generated SQL—not Gold SQL—went through semantic grounding, Query Plan validation, SQL compilation, Guardrail, EXPLAIN, read-only MySQL, Result Validator, and type-aware Gold comparison.

### End-to-end latency (ms)

| Difficulty | Avg | P50 | P95 | Max |
|---|---:|---:|---:|---:|
| Simple | 4478.372 | 4297.125 | 6958.247 | 6958.247 |
| Medium | 4815.758 | 4420.027 | 8090.417 | 8090.417 |
| Complex | 4665.236 | 4442.070 | 7444.090 | 7444.090 |

All maxima are below 60 seconds: `MINUTE_LEVEL_REQUIREMENT = PASS`.

### Failure distribution and root causes

- `RESULT_MISMATCH` 9: RDB_S01, RDB_S02, RDB_S03, RDB_S09, RDB_M01, RDB_M02, RDB_C04, RDB_C09, RDB_C11.
- `RANKING_MISMATCH` 3: RDB_M11, RDB_M12, RDB_C10.
- `SQL_COMPILE_ERROR` 3: RDB_S12, RDB_M13, RDB_C12.
- `GUARDRAIL_BLOCK` 4: RDB_M06, RDB_M07, RDB_M08, RDB_C08.
- `COST_BLOCK` 3: RDB_C01, RDB_C02, RDB_C05.

Root causes cluster into dictionary/canonical-value normalization, incorrect output shape and aggregation, misplaced HAVING semantics, incomplete end-of-period/month compilation, compiler/Guardrail disagreement over generated `EXISTS`, and join plans exceeding the one-million-row cost ceiling.

### First-run Frontend E2E

Fourteen application/API steps covered the required 13 scenarios. Backend health and query responses reported `REAL_DB`, but `FRONTEND_REAL_DB_E2E = FAIL`:

- browser chat hard-codes `execute: false`;
- Query Plan, SQL, Params, Guardrail, and Trace are visible, but Result rows are not rendered;
- Customer 360 and Marketing are not API-wired and their endpoints return `requires_real_db`;
- Benchmark dashboard is available and reads the measured summary.

### First-run full regression

- Frontend tests: **12/12 PASS**.
- Frontend production build: **PASS** (third-party non-blocking warnings only).
- Python: **223 passed, 3 failed, 4 errors**. The four temp-directory permission errors passed **4/4** when rerun with a workspace-local temp root.
- The three remaining failures are legacy benchmark-loader integration failures: generic suite discovery treats `real_db_gold.jsonl` as the incompatible older `BenchmarkCase` schema.
- Stage 4–8 tests ran without an indicated Stage-specific failure, but overall `FULL_REGRESSION = FAIL` while those three failures remain.

### First-run decision and limitations (superseded)

No production code or Frozen Gold was changed after the first final run. Accuracy is below 90%; Ranking and Time Series are 0%; `EXISTS` compiler/Guardrail compatibility, complex-query cost, browser real execution/result display, Customer 360, Marketing, and loader isolation remain unresolved.

`AGENT_FINAL_READY = NO`

## Second Frozen Real DB Benchmark

- First Frozen Benchmark: **18/40 = 45.00%**
- Second Frozen Benchmark: **36/40 = 90.00%**
- Remediation delta: **+18 correct cases**
- SQL execution success: **36/40 = 90.00%**
- Failure count: **4** (`{"COST_BLOCK": 4}`)
- Critical regression: **NO**
- NATURAL_LANGUAGE_FINAL_EXECUTION_ACCURACY_TARGET: **PASS**
- AGENT_FINAL_READY: **YES**
