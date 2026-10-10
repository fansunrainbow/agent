# Real DB Gate Hotfix 2：stock_product Concept Expansion

日期：2026-10-06

## 结论

`stock_product` 已通过通用 Concept Expansion Registry 展开为合法的产品一级分类维度过滤。目标 `SMOKE_07` 与完整 `SMOKE_01–10` 均通过。

- `REAL_DB_GATE = PASS`
- 可以进入 Real DB Benchmark
- `AGENT_FINAL_READY = NO`（仍需完成 Real DB Benchmark）

## 1. stock_product 的真实业务语义

`stock_product` 是产品一级分类概念，不是具体产品实体，也不是指标。它表示 `dim_product` 中一级分类名称为“股票”的产品集合。

具体产品名称（例如“贵州茅台”）仍通过 Product Entity Resolver 动态解析，两条链路保持分离。

## 2. 使用的真实 dim_product 字段

真实库与 Metadata 共同确认：

- 分类层级：一级产品分类
- 分类键字段：`up_prdt_type_id`
- 执行过滤字段：`up_prdt_type_name`
- 股票分类 ID：`PT040000`
- 股票分类名称：`股票`

继续采用现有 Stage 3 Dictionary / Value Mapping 的设计：一级产品分类按 `up_prdt_type_name` 过滤。原因是实际数据中同一分类名称可能对应多个 ID，例如“债券”对应 `PT030000` 与 `PT070000`；使用真实名称能保持既有业务口径一致，避免伪造或错误压缩分类 ID。

## 3. Canonical Value

`stock_product` 的 canonical value 为：`股票`。

同一通用机制同时验证：

- `fund_product → 开放式基金`
- `bond_product → 债券`

这些值均在真实 `dim_product.up_prdt_type_name` 和本地真实数据快照中存在。

## 4. Concept Expansion Registry

新增 `metadata/concept_expansions.yaml`。每条规则包含：

- `concept_id`
- `concept_type`
- `target_type`
- `target_dimension`
- `operator`
- `canonical_value`
- 真实来源表、字段与层级
- `version`
- `enabled`

实现不包含 `if concept == "stock_product"`，新增基金、债券或其他产品分类只需注册 Metadata。

## 5. Expansion 链路

执行顺序为：

`Semantic Grounding → Concept Resolution → ConceptExpander → Grounded Dimension Condition → Query Plan Assembly → Stage 4 Validation → Logical Plan → SQL Compiler`

`SMOKE_07` 的最终 Query Plan 过滤条件为：

```text
type      = dimension
target    = product_primary_category
operator  = eq
value     = 股票
```

原始 concept 只保留在 `expand_concepts` trace/provenance 中，不进入执行 SQL。

Stage 4 Validator 增加了 canonical dimension value 校验；不存在于 Value Mapping 的值返回 `INVALID_DIMENSION_VALUE`。

## 6. stock_product 是否仍进入 Entity Resolver

否。

Entity Resolver 会根据已落地的 categorical dimension evidence，跳过同源的类别短语，不再尝试把“股票类产品”解析成某个具体产品。具体产品查询仍正常进入 Entity Resolver。

对于“持有股票类产品的客户”和“没有持有股票类产品的客户”，系统分别生成带产品分类约束的 correlated `EXISTS` / `NOT EXISTS`，没有使用 `holding_market_value > 0` 替代。

## 7. Targeted SMOKE_07

查询：`2026年Q1股票产品交易额是多少？`

- Semantic：PASS
- Concept Resolution：PASS
- Concept Expansion：PASS
- Query Plan：PASS
- Stage 4 Validator：PASS
- SQL Compile：PASS
- Guardrail：PASS
- EXPLAIN：PASS
- Real DB Execute：PASS
- Result Validator：PASS
- 返回行数：1
- 真实结果：`2768592922.9240`
- 最终 EXPLAIN estimated rows：418,070（限制 1,000,000）

最初的直接维表 Join 在无索引真实库中估算约 95 亿行。SQL Compiler 现采用通用的“事实表通过已验证维度键进行参数化半连接预过滤”，SQL 层只处理展开后的维度条件，不识别 `stock_product`。

## 8. Full Smoke 01–10

最终执行 `python scripts/check_real_db.py`：

- Connection：PASS
- Read-only Verification：PASS
- Schema Check：PASS
- Schema Drift：0
- SMOKE_01：PASS
- SMOKE_02：PASS
- SMOKE_03：PASS
- SMOKE_04：PASS
- SMOKE_05：PASS
- SMOKE_06：PASS
- SMOKE_07：PASS
- SMOKE_08：PASS
- SMOKE_09：PASS
- SMOKE_10：PASS

最终结果：10/10 PASS。机器可读报告已更新至 `benchmark/reports/real_db_final/smoke_test.json`。

## 9. Regression

- 新增 Concept Expansion 专项测试：13 项
- Full pytest：230/230 PASS
- Stage 3 Business Dictionary Validator：PASS
- Stage 4 Query Plan Structural/Semantic Validator：PASS
- Stage 5 Agent、Stage 6 SQL、Stage 7 Marketing、Stage 8.2、Stage 8.4、Guardrail、Hallucination：均包含在全量 pytest 中并通过

专项覆盖：股票/基金/债券扩展、未知概念拒绝、类别与实体分离、具体产品回归、持仓 EXISTS/NOT EXISTS、非法 canonical value、provenance、Validator、SQL 原始 concept 拒绝、无 Smoke 特判。

## 10. REAL_DB_GATE

`REAL_DB_GATE = PASS`

连接、只读权限、Schema、EXPLAIN 成本、执行与结果校验全部通过。

## 11. 是否可以进入 Real DB Benchmark

可以。

下一步应执行冻结的 Real DB Benchmark。Benchmark 完成并满足阈值前，`AGENT_FINAL_READY` 仍保持 `NO`。
