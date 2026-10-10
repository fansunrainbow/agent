# Competition Demo Script（3–5 分钟）

## Before the timer

- Confirm `/api/health` shows `REAL_DB`.
- Use the read-only account; do not display `.env` or database credentials.
- Start with `python scripts/run_web.py` and open `http://127.0.0.1:8000`.
- Keep Browser DevTools closed and clear any prior error state.

## 0:00–0:30 — Positioning

Explain: “这不是直接 NL2SQL。自然语言先进入语义归一和结构化 Query Plan，再由确定性编译器生成参数化 SQL，并经过 Guardrail、EXPLAIN 和只读数据库执行。” Point to the `REAL_DB` badge.

## 0:30–1:00 — Simple question

Ask: **“南京客户有多少？”**

Show Final Result, then briefly open Query Plan, generated SQL, parameters, Guardrail PASS, and latency. Emphasize that `南京` is normalized and SQL binds the real storage value.

## 1:00–1:30 — Metric plus time

Ask: **“2026年第一季度南京客户平均日均资产是多少？”**

Show the quarter boundary and metric contract. Explain that asset averages use the registered natural-calendar definition.

## 1:30–2:00 — Complex segment

Ask: **“2026年Q1南京女性钻石客户中，排除休眠和销户且净流入为正的客户”**

Show multiple canonical filters, safe result rows, and trace. This demonstrates dimensions, dictionary mappings, time, exclusion logic, and a fact metric together.

## 2:00–2:25 — Product category

Ask: **“2026年Q1股票产品交易额是多少？”**

Show canonical category `stock` in the plan and database value `股票` in parameters. Explain the deduplicated product semi-join.

## 2:25–2:50 — Ranking

Ask: **“2026年Q1日均资产最高的前20名客户”**

Show entity ID + metric, descending metric order, stable `pty_id ASC` tie-breaker, and parameterized limit.

## 2:50–3:15 — Multi-turn Patch

Ask: **“2026年Q1南京客户平均日均资产是多少？”**, then **“改成苏州。”**

Show the same conversation, retained metric/time, replaced city filter, and Patch trace.

## 3:15–3:45 — Customer 360

Open Customer 360 and query a real customer ID approved for the demo. Show real basic/asset/holding/trading/fund-flow profiles. Explain masking and traceability.

## 3:45–4:15 — Marketing

Open Marketing for the same customer. Show the strict separation:

- FACT: database-derived features
- RULE_DECISION: matched controlled rules
- SUGGESTION: evidence-backed strategies

No result is taken from a demo fixture in REAL_DB mode.

## 4:15–4:45 — Safety and trace

Open Trace / Guardrail. Point out the sequence from grounding to Result Validator. Optionally mention that four Frozen cases remain `COST_BLOCK`; the system did not bypass safety to improve its score.

## 4:45–5:00 — Benchmark dashboard

Show First Frozen **45.00%** → Second Frozen **90.00%**, current Python 241/241, Frontend 14/14, REAL_DB E2E PASS, and unchanged Frozen Gold SHA-256. The immutable Second Frozen artifact recorded 240 tests before the post-freeze packaging-boundary test was added.

## Demo rules

- Every displayed result must be generated in `REAL_DB` mode.
- Do not show `.env`, passwords, API keys, absolute local paths, stack traces, or fixture files.
- If an operation fails, show the explicit error or safe block; never claim an unexecuted answer is correct.
