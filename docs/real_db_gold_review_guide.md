# Real DB Gold 人工审核指南

## 1. 当前状态

- 数据集：`benchmark/datasets/real_db_gold.jsonl`
- Case 总数：40
- 难度分布：Simple 12 / Medium 16 / Complex 12
- Gold 来源：`independent_query` 40；`official_sql` 0
- 审核状态：`pending` 40；`reviewed` 0
- 数据集 SHA-256：`B9E92BDF2F2DF3B9C06852657C7FA0543D9C87BB84008DF8FC5C8D92854AD121`
- Final Benchmark：**尚未执行**

本数据集是待人工确认的 Gold 草稿。Final Accuracy 只能使用人工确认后标记为 `reviewed` 的 Case；当前不得据此声明任何最终准确率，也不得把 `AGENT_FINAL_READY` 改为 `YES`。

## 2. Gold 独立性

40 条 Gold SQL 均在 `scripts/prepare_real_db_gold_draft.py` 中独立编写，并由已验证的只读数据库连接直接执行。该脚本只使用数据库配置与只读连接，不调用被测 Agent、Semantic Grounding、Query Plan、SQL Compiler 或 Benchmark Runner。

所有 Case 的 `gold_source` 均为 `independent_query`。项目内未发现可复用的官方 Q&A Gold SQL，因此本批次 official Gold 数量为 0。保存的 `gold_sql` 是独立 SQL，不是 Agent Generated SQL。

## 3. 分布与覆盖

### 3.1 Intent 与结果类型

| 分类 | 数量 | Case |
|---|---:|---|
| `metric_query` | 22 | S01–S12, M01–M02, M08, M14–M16, C04–C05, C07, C11 |
| `customer_selection` | 11 | M03–M07, C01–C03, C06, C08, C12 |
| `group_analysis` | 3 | M09–M10, C09 |
| `ranking` | 3 | M11–M12, C10 |
| `trend_analysis` | 1 | M13 |
| Scalar | 19 | S01–S12, M01–M02, M08, M15–M16, C05, C07 |
| Set | 11 | M03–M07, C01–C03, C06, C08, C12 |
| Grouped | 6 | M09–M10, M14, C04, C09, C11 |
| Ranking | 3 | M11–M12, C10 |
| Time Series | 1 | M13 |

### 3.2 Metric 覆盖

| Metric | 代表 Case |
|---|---|
| `customer_count` | S01–S05, M02, M09, C07, C09 |
| `average_total_asset` | S06, M01, M03, M10–M11, M14, C02, C04, C11 |
| `period_end_asset` | M16 |
| `trade_amount` | S07, M04, M12, M14–M15, C02, C04–C05, C10–C11 |
| `trade_count` | S08 |
| `net_inflow` | S09, M05, M13, C01, C03, C06, C11 |
| `total_inflow` | S10 |
| `total_outflow` | S11 |
| `holding_market_value` | M08 |
| `cash_asset` | S12 |
| `cash_asset_ratio` | C12 |

此外覆盖 `stock_trade_amount`、`fund_holding_ratio` 和 `asset_change` 等组合指标。

### 3.3 Dimension、Entity 与 Operator 覆盖

| 能力 | 代表 Case |
|---|---|
| city / city entity | S01–S02, M01–M02, M06–M07, M09, C01, C04, C07–C10 |
| gender | S03, M02, C01, C06–C07, C12 |
| customer level | S04, M10, C03, C06 |
| branch / branch entity | S05, M16, C05, C11 |
| product entity | M08, C08 |
| product primary category / category entity | M06–M07, M15, C01–C02, C05 |
| `eq` | S01–S05 等 |
| `gt` | M03–M05, C01–C03, C06, C09 |
| `gte` | C12 |
| `lt` | C01, C03 |
| `lte` | C07 |
| `between` | Q1 时间过滤及 C12 年龄过滤 |
| `in` | C07；产品分类半连接见 M06、M15、C01–C02、C05 |
| `not_in` | C06 |
| `exists` 语义 | M06 |
| `not_exists` | M07, C08 |

## 4. 人工审核步骤

每条 Case 均按以下顺序审核：

1. 核对自然语言中的时间范围、对象、维度、指标、运算符和结果粒度。
2. 确认 `gold_sql` 未调用被测 Agent，且表、字段、字典代码、实体 ID 与真实 Schema 一致。
3. 检查多事实表是否先在客户粒度独立聚合，避免 fact-to-fact join 放大。
4. 使用只读账号在 MySQL Workbench 或另一独立校验脚本中执行 `gold_sql`。
5. 将结果与 `gold_result` 比较：Scalar 使用数值容差；Set 忽略行顺序；Grouped 按 group key；Ranking 保留顺序；Time Series 按时间 bucket。
6. 检查空集、0 值、NULL、分母为 0、日期缺口和并列排名的处理是否符合业务口径。
7. 记录审核人、审核日期和必要说明；确认无误后，才把该条 `review_status` 从 `pending` 改为 `reviewed`。

如审核发现 Gold 有误，应将其标记为 Gold 问题并修正独立 SQL/结果，记录变更原因；不得依据 Agent 的输出反向调整 Gold。

## 5. 优先人工核验清单

所有 40 条均需人工核验，其中以下项目优先级最高：

1. **全部 Complex Case（C01–C12）**：涉及多事实组合、比例、资产变化、机构层级、排除条件或复杂筛选。
2. **空结果/零值**：S05（营业部客户数为 0）、C06（空 Set）、C07（客户数为 0）。需要确认实体归属、状态代码与条件组合，避免“可执行但无区分度”的 Gold。
3. **排名与并列规则**：M11、M12、C10。当前以指标降序、`pty_id` 升序作为确定性并列规则。
4. **时间口径**：S06、M01、M10–M11、M14、C01–C04、C11 使用 Q1 90 个自然日；M13 使用 `YYYYMM` 月 bucket；期末类使用 2026-03-31。
5. **实体与字典映射**：S05 的机构 ID、M08/C08 的贵州茅台产品 ID、M16/C05/C11 的北京分公司 `up_org_id`，以及性别、等级、状态代码。
6. **类别口径**：M06–M07、M15、C01–C02、C05 使用真实一级产品分类名称；需确认“开放式基金”是否就是业务期望的“基金”。
7. **多指标单行结果**：M14、C04、C11。它们在数据集中按 Grouped/对象结构保存，需确认后续比较器的字段级数值容差策略。
8. **大集合**：M04 返回 94 行。人工审核时建议额外核对边界值及总行数，而非只抽查首尾记录。

## 6. 审核完成门槛

- 至少 30 条被人工标记为 `reviewed` 后，才具备进入 STEP 2 的最低 Gold 条件。
- Complex Gold 必须逐条独立核对。
- 未审核的 `pending` Case 不得纳入 Final Accuracy 分母或分子。
- 用户确认 Gold 之前，不运行 `scripts/run_real_db_benchmark.py`，不生成 Final Benchmark 报告，不更新最终 readiness 判定。

## 7. 当前结论

STEP 1 的 Gold 草稿已建立并通过静态结构校验：40 条 JSONL 均可解析，Case ID 唯一，必填字段完整，`gold_result` 无 NULL，且不存在 `agent_generated` 来源。当前仍有 40 条待人工审核，Final Benchmark 保持未执行。
