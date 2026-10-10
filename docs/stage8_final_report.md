# Stage 8 Final Frozen Benchmark Report

## Real Database Execution Evaluation

Status: **NOT MEASURED** (`real_db = false`). The real-DB adapter and benchmark harness are implemented, but no database credentials/read-only grant evidence or independently reviewed Gold Result dataset was provided. The frozen dry-run score is not used as SQL Execution Success, Result Accuracy, Result Equivalence, or Natural Language Final Execution Accuracy. See `benchmark/reports/real_db_final/real_db_benchmark_report.md`.

## Executive conclusion

Stage 8.6 已完成冻结重测。原始 226 条 Benchmark 未修改，生产语义、Planner、Validator、Canonicalizer、SQL Generator、Guardrail、Patch Engine 和 Marketing Engine 均保持冻结。

- **Raw Frozen Score：172/226，76.11%，54 failures**
- **Adjudicated Score：206/226，91.15%，20 unresolved failures**
- **STAGE_9_READY = YES**

Adjudicated Score 仅对 34 条已有 CSV、`dim_public` 或现有 Metadata 合同证据支持、且没有并存真实系统缺陷的冲突计入信用。Raw Score 始终保留并优先展示。

## Stage 8 指标演进

| 阶段 | Total | Semantic | Generalization Component F1 | SQL | Multi-turn | End-to-End | Hallucination | Guardrail |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Stage 8 initial | 121/226 | 26.67% | 70.45% | 53.33% | 50% | 75% | 90% | 100% |
| Stage 8.2 | 157/226 | 83.33% | 87.27% | 53.33% | 50% | 60% | 100% | 100% |
| Stage 8.3 | 155/226 | 83.33% | 87.27% | 53.33% | 50% | 60% | 100% | 100% |
| Stage 8.4 | 166/226 | 83.33% | 87.27% | 93.33% | 50% | 85% | 100% | 100% |
| Stage 8.5 | 169/226 | 83.33% | 87.27% | 93.33% | 80% | 85% | 100% | 100% |
| Stage 8.6 Raw | 172/226 | 83.33% | 87.27% | 93.33% | 80% | 85% | 100% | 100% |
| Stage 8.6 Adjudicated | 206/226 | 100% | 87.27% | 93.33% | 80% | 100% | 100% | 100% |

Stage 8.3 的总通过数短暂下降，是因为引入了更严格的 canonical semantic comparison，不代表生产能力回退。

## Freeze 与 Metadata 审核

发现并修正一项明确 Metadata contract 不一致：`metric_constraints.yaml` 已规定 `period_start_asset`、`period_end_asset`、`asset_change`、`asset_change_rate` 必须提供时间，但运行时 `metrics.yaml` 缺少相同约束。同步后，`PLAN_M016`、`PLAN_M017`、`PLAN_C018` 从错误 ready 恢复为正确 clarification，因此 Raw Score 从 169 提升到 172。

未修改任何原始 Benchmark query、expected、case_id、difficulty 或生产代码。

## Raw 与 Adjudicated 分套件结果

| Suite | Raw | Adjudicated | 裁决信用 |
|---|---:|---:|---:|
| Semantic | 25/30，83.33% | 30/30，100% | 5 synthetic entity conflicts |
| Query Plan | 16/30，53.33% | 21/30，70.00% | 5 yearless-Q1 policy conflicts |
| Generalization | 7/30，23.33% | 28/30，93.33% | 21 MX policy conflicts |
| SQL | 14/15，93.33% | 14/15，93.33% | 0 |
| Multi-turn | 8/10，80.00% | 8/10，80.00% | 0 |
| End-to-End | 17/20，85.00% | 20/20，100% | 3 unsupported/clarification policy conflicts |
| Hallucination | 20/20 | 20/20 | 0 |
| Guardrail | 20/20 | 20/20 | 0 |
| Marketing | 32/32 | 32/32 | 0 |
| Result | 12/12 | 12/12 | 0 |
| Official seed | 1/7 | 1/7 | 0 |

## Semantic 指标

| 指标 | Raw | Adjudicated |
|---|---:|---:|
| Semantic Accuracy | 83.33% | 100% |
| Metric Linking Accuracy | 100% | 100% |
| Dimension Linking Accuracy | 93.33% | 100% |
| Entity Resolution Accuracy | 83.33% | 100% |
| Time Parsing Accuracy | 100% | 100% |
| Intent Accuracy | 96.67% | 100% |
| Unsupported Handling Accuracy | 100% | 100% |
| Semantic Hallucination Rate | 0% | 0% |

Semantic Adjudication 的 5 条全部是 synthetic entity Gold：`P_GZM`、`B_NJ001`、`PB_JS`、`C00000000000169`、`CAT_FUND` 不存在于真实项目 CSV registry。系统使用真实 ID、真实类别名称或 clarification，未制造 synthetic ID。

## Query Plan 与 Generalization

### Query Plan

- Raw structural exact match：16.67%
- Canonical semantic exact match：53.33%
- Plan Component F1：92.69%
- Adjudicated accuracy：70.00%

剩余计划失败中，真实 Semantic Plan Error 主要是 Boolean scope/operator binding、年龄条件丢失及 subject grain 推断。3 条 product/customer subject case 暂列 `AMBIGUOUS`。本轮没有发现新的 Canonicalizer 实现回归。

### Generalization

- Raw strict accuracy：23.33%
- Adjudicated accuracy：93.33%
- Component F1：87.27%

`GEN_MX100`～`GEN_MX120` 共 21 条 query 未提供时间，但 Gold 写入 2026-Q1 并要求 ready。系统依据 Metric Contract 返回 clarification；这不能描述成系统主动猜对，统一记录为 `GOLD_POLICY_CONFLICT`。

## SQL 指标

- SQL Compile Success：93.33%（14/15）
- Schema Validity：100%
- Join Validity：100%
- Parameterization Validity：100%
- SQL Guardrail Pass：100%
- `real_db=false`
- SQL Execution Accuracy：`not_measured`
- Result Equivalence：`not_measured`

`SQL_C002` 的输入 Plan 仍含未展开的 `diamond_customer` concept。SQL Layer 正确返回 `SQL_UNSUPPORTED_COMBINATION`；根因属于上游 Plan/Concept Expansion，不应让 SQL Generator 解释业务 Concept。

## Multi-turn 指标

| 指标 | 结果 |
|---|---:|
| Overall | 80% |
| ADD | 75% |
| REMOVE | 100% |
| REPLACE | 80% |
| CHANGE_METRIC | 80% |
| CHANGE_TIME | 100% |
| CHANGE_ORDER | 100%（专项路径） |
| CHANGE_LIMIT | 100% |
| Context Retention | 100% |
| Clarification Follow-up | 100% |

- `MT_002`：`dim_public` 与生产 value mapping 定义 `5000003=女`，Gold 使用 `F`，且不存在生产映射 `F → 女`。标记 `ENUM_REPRESENTATION_CONFLICT / pending_human`，不计 adjudication 信用。
- `MT_009`：真实数据确认 `1000003=金卡客户`，不是“普通客户”；Gold 错误成立。但系统把无法识别的新等级静默忽略并保留旧钻石等级且返回 ready，也是真实 P0 缺陷，因此不计 adjudication 信用。

## Hallucination、Guardrail 与 Marketing

### Hallucination

- Cases：20
- Handled correctly：20
- Semantic Hallucination Rate：0%
- Unsupported Handling Accuracy：100%

### Guardrail

- 20/20
- Unsafe Block Rate：100%
- Safe Pass Rate：100%
- False Positive：0
- False Negative：0

### Marketing

Marketing 32/32。Tag、Segment、Opportunity、Strategy、Explainability、Generalization、Missing-data boundary、Suitability guard 均为 100%，无回归。

## Coverage

| Coverage | Covered | Rate | 未覆盖 |
|---|---:|---:|---|
| Metric | 38/38 | 100% | 无 |
| Dimension | 19/21 | 90.48% | profession, quarter |
| Intent | 8/9 | 88.89% | comparison |
| Entity | 5/5 | 100% | 无 |
| Operator | 6/16 | 37.50% | 见下文 |
| Marketing Rule | 26/26 | 100% | 无 |

Operator 状态：

- `IMPLEMENTED + TESTED`：eq、gt、gte、lt、between、exists
- `IMPLEMENTED + NOT_TESTED`：neq、lte、in、not_in、contains、starts_with、ends_with、not_exists、is_null、is_not_null
- `UNSUPPORTED`：无

Coverage Collector 已修复对 Semantic `expected.operators` 的采集，因此 `exists` 现在被正确计入。

## Stability

选择 20 个代表性 Cases，覆盖 Semantic 4、Generalization 4、Multi-turn 3、SQL 3、Hallucination 3、Marketing 3；每条重复运行 3 次。

- Stable：20/20
- Unstable：0
- Output Stability Rate：100%

## Latency

以下均为当前本地 dry-run 环境数据，单位毫秒：

| Stage | avg | p50 | p95 | max |
|---|---:|---:|---:|---:|
| Semantic + Plan | 2201.786 | 2045.973 | 3465.853 | 4882.860 |
| Query Plan evaluation | 2015.162 | 1980.642 | 2113.534 | 3455.710 |
| SQL generation | 104.096 | 153.497 | 273.461 | 359.301 |
| Guardrail | 0.356 | 0.283 | 1.017 | 1.646 |
| Marketing | 0.077 | 0.060 | 0.168 | 0.247 |
| End-to-End | 3685.236 | 2114.729 | 17761.383 | 18219.778 |

当前 instrumentation 将 Semantic 与 Plan 合并计时，没有独立 Semantic-only timer；未伪造拆分数字。

## Regression

- 全量 pytest：187/187 passed
- Stage 4 Query Plan batch：132/132 passed
- Frozen Benchmark：226/226 cases executed
- Hallucination、Guardrail、Marketing、SQL、Multi-turn、End-to-End 均无回退
- Stability：100%

## Final Failure List

Raw 54 failures 的分类：

- `GOLD_POLICY_CONFLICT`：29
- `SYNTHETIC_ENTITY_CONFLICT`：5
- `ENUM_REPRESENTATION_CONFLICT`：1
- `REAL_SYSTEM_DEFECT`：16
- `AMBIGUOUS`：3

排除 34 条 confirmed adjudication credit 后，仍保留 20 条：

| Priority | Case | Root cause | Demo impact | Stage 9 前建议修复 |
|---|---|---|---|---|
| P0 | MT_009 | 未识别 replacement 被静默忽略，旧等级仍 ready | 是 | 是 |
| P1 | OFFICIAL_002 | 年龄分组规则与指标组合未完整解析 | 是 | 是 |
| P1 | OFFICIAL_003 | 复合客群、产品实体与盈亏查询未完整组合 | 是 | 是 |
| P1 | OFFICIAL_004 | 组织层级聚合请求未形成可执行计划 | 是 | 是 |
| P1 | OFFICIAL_005 | 双产品实体、交易/持仓关系与账户语义未完整解析 | 是 | 是 |
| P1 | OFFICIAL_006 | 客群筛选到产品分类输出的跨粒度查询未完成 | 是 | 是 |
| P1 | OFFICIAL_007 | 市场维度及交易口径链接不完整；Gold 日期字段名也有差异 | 是 | 是 |
| P1 | PLAN_C001 | OR scope 与分支阈值绑定错误 | 是 | 是 |
| P1 | PLAN_C003 | 年龄条件在复合表达中丢失 | 是 | 是 |
| P1 | PLAN_C006 | 城市 OR 与指标条件 scope 错误；另有 Gold 时间冲突 | 是 | 是 |
| P1 | PLAN_C011 | 双指标 operator/value 绑定与 intent 错误；另有 Gold 时间冲突 | 是 | 是 |
| P1 | PLAN_C020 | NOT scope 被错误并入 OR | 是 | 是 |
| P1 | SQL_C002 | 上游未展开 Concept；SQL 正确拒绝 | 是 | 是（修上游） |
| P2 | PLAN_M014 | 客户计数按分公司分组时 subject 错切为 branch | 否 | 是 |
| P2 | PLAN_C010 | 净流入按营业部分组时 subject 错切为 branch | 否 | 是 |
| P2 | PLAN_C014 | 客户计数按分公司/城市分组时 subject 错切为 branch | 否 | 是 |
| P2 | PLAN_M020 | customer/product 主体口径待裁决 | 否 | 否 |
| P2 | GEN_X008 | customer/product 主体口径待裁决 | 否 | 否 |
| P2 | GEN_X009 | customer/product 主体口径待裁决 | 否 | 否 |
| Won't Fix / Gold Conflict | MT_002 | F 与真实受控值“女”缺少正式等价映射 | 否 | 人工裁决后处理 |

## Stage 9 Gate

| Gate | Threshold | Final | Result |
|---|---:|---:|---|
| Semantic | ≥80% | 83.33% Raw | PASS |
| Generalization Component F1 | ≥85% | 87.27% | PASS |
| SQL dry-run | ≥85% | 93.33% | PASS |
| Multi-turn | ≥80% | 80.00% | PASS |
| End-to-End | ≥80% | 85.00% | PASS |
| Hallucination Handling | 100% | 100% | PASS |
| Semantic Hallucination Rate | 0% | 0% | PASS |
| Guardrail stable | required | 20/20, FP=0, FN=0 | PASS |
| Full Regression | required | 187/187 + Stage 4 132/132 | PASS |

**STAGE_9_READY = YES**

建议在 Stage 9 的第一优先级处理 `MT_009` 的 silent replacement retention；这不阻断 Stage 9 Gate，但不应在面向真实用户的多轮修改场景中长期保留。
