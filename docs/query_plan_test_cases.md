# Query Plan 测试用例设计

## 1. 测试目标

本测试集用于验证 Generic Query Plan 的：

- Intent 识别能力
- Metric Linking
- Dimension Linking
- Filter 构造
- Entity Resolution
- Time Parsing
- Clarification
- Unknown Concept Rejection
- Hallucination Rejection
- Multi-turn Plan Patch
- Structural Validation
- Semantic Validation

官方 Q&A 只作为 regression，不作为唯一测试来源。

---

## 2. 测试总规模

Stage 4 第一版至少建立 100 条 Query Plan 测试。

规划如下：

| 类别 | 数量 |
|---|---:|
| Simple | 20 |
| Medium | 20 |
| Complex | 20 |
| Ambiguous | 10 |
| Entity | 10 |
| Multi-turn | 10 |
| Invalid / Hallucination | 10 |
| 总计 | 100 |

---

## 3. Simple — 简单查询（S001-S020）

主要验证：

- 单 Intent
- 单 Metric
- 单 Dimension
- 单 Filter
- 简单时间条件

示例：

### S001

输入：

南京客户有多少？

预期：

- intent = metric_query
- subject = customer
- metric = customer_count
- dimension filter = city eq 南京
- status = ready

---

### S002

输入：

按客户等级统计人数。

预期：

- intent = group_analysis
- metric = customer_count
- dimension = customer_level
- group_by = customer_level
- status = ready

---

### S003

输入：

查询2026年Q1总资产。

预期：

- intent = metric_query
- metric = total_asset
- time_range = quarter(2026, Q1)
- status = ready

---

## 4. Medium — 中等组合查询（M001-M020）

主要验证：

- 2~3 个条件组合
- Metric + Dimension
- 时间范围
- 排序
- Top-K

示例：

### M001

输入：

查询2026年Q1南京地区日均资产超过30万的客户。

预期：

- intent = customer_selection
- metric = average_total_asset
- city = 南京
- average_total_asset > 300000
- time = 2026 Q1
- status = ready

---

## 5. Complex — 复杂组合查询（C001-C020）

主要验证：

- 多条件
- AND / OR / NOT
- group_by
- having
- order_by
- limit
- 多指标组合

示例：

### C001

输入：

查询南京地区女性客户中，基金持仓占比低于10%或现金资产占比高于50%的客户。

预期逻辑：

AND(
  city = 南京,
  gender = female,
  OR(
    fund_holding_ratio < 0.1,
    cash_asset_ratio > 0.5
  )
)

status = ready

---

## 6. Ambiguous — 模糊问题（A001-A010）

主要验证：

- needs_clarification
- ambiguity_rules
- 不允许模型自行猜测

示例：

### A001

输入：

找近期活跃的优质客户。

预期：

status = needs_clarification

ambiguities：

- 近期
- 活跃
- 优质客户

---

### A002

输入：

找大额资金客户。

预期：

需要澄清“大额”的阈值或比例口径。

---

## 7. Entity — 新实体测试（E001-E010）

主要验证：

- 产品实体
- 营业部实体
- 客户实体
- 新实体不依赖官方 Q&A

示例：

### E001

输入：

查询持有贵州茅台的客户。

预期：

- entity_type = product
- surface = 贵州茅台
- 通过 entity resolver 动态解析
- 不允许 LLM 猜 product_id

---

## 8. Multi-turn — 多轮上下文测试（T001-T010）

主要验证：

- parent_plan_id
- modify
- refine
- compare
- Plan Patch

示例：

### T001

第一轮：

Q1南京客户平均资产是多少？

第二轮：

只看钻石客户。

第三轮：

那苏州呢？

预期：

第二轮：

operation = refine

第三轮：

operation = modify

只替换 city 条件，不重新创造其他条件。

---

## 9. Invalid / Hallucination — 幻觉诱导测试（H001-H010）

主要验证：

- UNKNOWN_METRIC
- UNKNOWN_DIMENSION
- UNKNOWN_CONCEPT
- UNKNOWN_OPERATOR
- UNRESOLVED_ENTITY
- INVALID_TIME_RANGE
- LOW_CONFIDENCE
- UNSUPPORTED_CAPABILITY

示例：

### H001

输入：

查询客户满意度评分。

前提：

metrics.yaml 中不存在 customer_satisfaction_score。

预期：

- 不允许创建新 Metric
- Validator 返回 UNKNOWN_METRIC 或要求澄清
- 不允许继续生成 SQL

---

### H002

输入：

查询2026年第8季度客户资产。

预期：

Structural Validation 失败。

原因：

quarter 必须在 1~4 范围内。

---

## 10. 核心评价指标

后续测试至少统计：

- Intent Accuracy
- Metric Linking Accuracy
- Dimension Linking Accuracy
- Filter Accuracy
- Entity Resolution Accuracy
- Time Parsing Accuracy
- Clarification Accuracy
- Unknown Concept Rejection Rate
- Plan Valid Rate
- Hallucination Rejection Rate

---

## 11. Semantic Hallucination Rate

定义：

模型输出未注册 Metric / Dimension / Concept / Entity 的 Query Plan 数量
/
总 Query Plan 数量

目标：

尽可能接近 0。

---

## 12. 当前阶段说明

本文件先建立测试分类和编号体系。

后续将在：

tests/query_plan/

中逐步建立对应 JSON 测试数据，并通过：

scripts/test_query_plan_cases.py

批量运行 Validator。

Stage 4 最终要求至少达到 100 条测试。