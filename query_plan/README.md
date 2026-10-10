# Generic Query Plan

## 1. 模块定位

`query_plan/` 是 Agentic Marketing 项目中自然语言理解层与后续 SQL 生成层之间的中间表示模块。

整体流程为：

```text
Natural Language
↓
Metric System + Business Dictionary
↓
Generic Query Plan
↓
Plan Validation
↓
后续 SQL Generator / Agent
```

本阶段不直接生成 SQL。

Query Plan 的目标是把用户问题转换为：

- 结构化
- 可验证
- 可扩展
- 可解释
- 可执行前检查

的业务查询计划。

---

## 2. 核心设计目标

### 2.1 普适化

Query Plan 不针对官方 Q&A 单独设计。

它应支持：

- 新表达
- 新指标组合
- 新实体
- 新筛选条件
- 新排序方式
- 新分组方式
- 多条件组合
- 多轮修改

官方 Q&A 只作为 regression test。

### 2.2 降低 AI 幻觉

Query Plan 中出现的：

- Intent
- Metric
- Dimension
- Business Concept
- Operator
- Entity
- Time Semantics

都必须能够被已有 Registry 或 Metadata 验证。

模型不能随意创造：

```text
不存在的指标
不存在的维度
不存在的业务概念
不存在的实体 ID
未知操作符
默认业务条件
```

---

## 3. 当前目录结构

```text
query_plan/
├─ __init__.py
├─ models.py
├─ schema/
│  ├─ query_plan.schema.json
│  ├─ filter.schema.json
│  ├─ time_range.schema.json
│  └─ entity_ref.schema.json
│
├─ examples/
│  ├─ customer_selection.json
│  ├─ metric_query.json
│  ├─ group_analysis.json
│  ├─ trend_analysis.json
│  ├─ ranking_query.json
│  ├─ entity_query.json
│  └─ clarification.json
│
└─ README.md
```

---

## 4. 配套 Metadata

Query Plan 依赖以下注册表：

```text
metadata/
├─ intent_registry.yaml
├─ operator_registry.yaml
├─ time_semantics.yaml
├─ query_capabilities.yaml
├─ query_plan_confidence.yaml
├─ metrics.yaml
├─ dimensions.yaml
└─ business_dictionary.yaml
```

`models.py` 提供与 JSON Schema 对应的 Pydantic v2 类型边界；JSON Schema 仍是跨语言交换契约，Pydantic 模型用于 Python 侧生成与接入校验。

## 运行与验收

安装依赖：

```bash
python -m pip install -r requirements.txt
```

执行完整 Stage 4 验收：

```bash
python scripts/check_yaml.py
python scripts/validate_query_plan.py
python scripts/test_query_plan_cases.py
python -m unittest tests.test_query_plan_validator tests.test_query_plan_normalizer -v
python scripts/inspect_query_plan_coverage.py
```

Validator 采用 Fail Closed 策略，并额外检查：Intent 能力矩阵、Subject 兼容性、Metric 必需时间、日期区间顺序、Metric 与 Dimension 的安全 Join 路径、Operator 值形状、Entity Filter 与解析结果一致性、假设来源以及配置化置信度阈值。

分别负责：

```text
intent_registry.yaml
→ 查询意图

operator_registry.yaml
→ 标准操作符

time_semantics.yaml
→ 时间语义

query_capabilities.yaml
→ 当前系统支持的 Query Plan 能力

metrics.yaml
→ Stage 2 标准指标

dimensions.yaml
→ 标准维度

business_dictionary.yaml
→ Stage 3 标准业务概念
```

---

## 5. Query Plan 顶层结构

标准 Query Plan 第一版包含：

```json
{
  "version": "1.0",
  "status": "ready",
  "intent": "",
  "subject": "",
  "metrics": [],
  "dimensions": [],
  "filters": [],
  "entities": [],
  "time_range": null,
  "group_by": [],
  "having": [],
  "order_by": [],
  "limit": null,
  "output": {},
  "ambiguities": [],
  "assumptions": [],
  "confidence": {},
  "context": {}
}
```

---

## 6. status

Query Plan 当前只允许：

```text
ready
needs_clarification
invalid
```

### ready

表示：

```text
Plan 已具备执行条件
```

但仍需通过 Structural Validation 和 Semantic Validation。

### needs_clarification

表示：

```text
存在未解决歧义
```

例如：

- 近期
- 活跃客户
- 优质客户
- 大额资金
- 多候选实体

这种情况下不得继续生成 SQL。

### invalid

表示：

```text
Plan 已确认无法合法表示或执行
```

---

## 7. Intent

当前支持：

```text
customer_selection
metric_query
group_analysis
trend_analysis
ranking
entity_lookup
customer_profile
segment_analysis
comparison
```

Intent 只描述：

```text
用户想做哪类分析任务
```

不能把具体城市、产品、客户等级写成 Intent。

例如：

```text
南京客户查询
```

不是 Intent。

应该解析为：

```text
intent = customer_selection
filter = city eq 南京
```

---

## 8. Metric

Query Plan 中所有 Metric 必须来自：

```text
metadata/metrics.yaml
```

例如：

```text
total_asset
average_total_asset
trade_amount
net_inflow
holding_market_value
fund_holding_ratio
```

不允许模型生成：

```text
customer_profit_score
customer_quality_index
customer_satisfaction_score
```

除非这些指标已经在 Metric System 中注册。

---

## 9. Dimension

所有 Dimension 必须来自：

```text
metadata/dimensions.yaml
```

例如：

```text
customer
gender
age
age_group
customer_level
customer_status
customer_type
education
profession
province
city
branch
parent_branch
product
product_primary_category
product_secondary_category
market
date
month
quarter
account_source
```

---

## 10. Filter

Filter 统一使用：

```json
{
  "id": "f1",
  "type": "dimension",
  "target": "city",
  "operator": "eq",
  "value": "南京",
  "source": "explicit",
  "confidence": 1.0
}
```

Filter 类型支持：

```text
dimension
metric
concept
entity
```

---

## 11. Filter Source

所有筛选条件必须记录来源：

```text
explicit
dictionary
entity_resolution
derived_rule
context
business_default
```

目的：

> 防止模型偷偷增加用户没有提出的条件。

例如用户只说：

```text
查询南京客户
```

不能默认补：

```text
customer_status = 正常
```

除非这是明确注册的 business default。

---

## 12. Operator

Query Plan 中禁止直接使用任意 SQL 操作符。

统一使用 canonical operator：

```text
eq
neq
gt
gte
lt
lte
in
not_in
between
contains
starts_with
ends_with
exists
not_exists
is_null
is_not_null
```

例如：

```text
大于
>
greater than
```

最终统一为：

```text
gt
```

---

## 13. AND / OR / NOT

Filter 支持逻辑树：

```json
{
  "logic": "and",
  "conditions": [
    {},
    {
      "logic": "or",
      "conditions": [
        {},
        {}
      ]
    }
  ]
}
```

支持：

```text
AND
OR
NOT
```

不能只支持扁平 AND。

---

## 14. Entity

高基数实体必须通过 Entity Resolver 动态解析。

例如：

```text
招商银行
贵州茅台
中国平安
某营业部
某客户号
```

统一表示为：

```json
{
  "entity_type": "product",
  "surface": "贵州茅台",
  "resolution_status": "resolved",
  "resolved": {
    "id": "...",
    "name": "贵州茅台"
  },
  "confidence": 0.98,
  "source": "exact_match"
}
```

如果多个候选：

```text
resolution_status = ambiguous
```

此时 Query Plan 必须进入：

```text
needs_clarification
```

不能让模型自行选择。

---

## 15. Time Range

时间语义统一支持：

```text
absolute_date
date_range
month
quarter
year
ytd
last_n_days
last_n_months
latest
start_of_period
end_of_period
```

例如：

```json
{
  "type": "quarter",
  "year": 2026,
  "quarter": 1
}
```

Stage 4 不直接把：

```text
2026 Q1
```

写死成：

```text
2026-01-01 ~ 2026-03-31
```

真正的日期展开留给后续 Time Resolver。

---

## 16. Clarification

对于：

```text
近期
活跃客户
优质客户
大额
重点客户
热门产品
```

如果没有明确业务口径：

```text
status = needs_clarification
```

Query Plan 应记录：

- term
- type
- reason
- question
- candidates

示例：

```json
{
  "term": "近期",
  "type": "time",
  "reason": "未指定明确时间范围",
  "question": "近期是最近7天、30天还是3个月？",
  "candidates": [
    "last_7_days",
    "last_30_days",
    "last_3_months"
  ]
}
```

---

## 17. Confidence

Query Plan 保留各部分置信度：

```text
overall
intent
metrics
dimensions
entities
time
filters
```

当前策略由 `metadata/query_plan_confidence.yaml` 配置：

```text
ready + overall < 0.85
→ LOW_CONFIDENCE
→ Fail Closed，不允许执行

ready + 任一已提供的关键组件置信度 < 0.60
→ LOW_CONFIDENCE
→ 进入澄清流程

needs_clarification
→ 允许低置信度
```

---

## 18. Context

为多轮对话预留：

```json
{
  "parent_plan_id": null,
  "operation": "new"
}
```

支持：

```text
new
modify
refine
compare
```

例如：

```text
第一轮：
Q1南京客户平均资产是多少？

第二轮：
只看钻石客户。

第三轮：
那苏州呢？
```

后续可通过 Plan Patch 修改原 Plan，
而不是每轮完全重新构造。

---

## 19. Structural Validation

脚本：

```text
scripts/validate_query_plan.py
```

第一层使用 JSON Schema 检查：

- JSON 结构
- 必填字段
- 数据类型
- enum
- limit >= 1
- quarter 1~4
- confidence 0~1
- filter 结构
- entity 结构
- time range 结构

---

## 20. Semantic Validation

第二层进一步检查：

- Intent 是否注册
- Metric 是否存在
- Dimension 是否存在
- Business Concept 是否存在
- Operator 是否注册
- Entity 是否已解析
- Time Semantic 是否注册
- Capability 是否支持
- Ambiguity 是否已解决
- Confidence 是否满足执行条件

典型错误码：

```text
UNKNOWN_INTENT
UNKNOWN_METRIC
UNKNOWN_DIMENSION
UNKNOWN_CONCEPT
UNKNOWN_OPERATOR
UNRESOLVED_ENTITY
INVALID_TIME_RANGE
UNSUPPORTED_CAPABILITY
LOW_CONFIDENCE
UNRESOLVED_AMBIGUITY
STRUCTURAL_ERROR
```

---

## 21. Normalization

脚本：

```text
scripts/normalize_query_plan.py
```

用于统一不同表达。

例如：

```text
南京市
南京
Nanjing
→ 南京
```

```text
>
大于
gt
→ gt
```

```text
降序
descending
desc
→ desc
```

---

## 22. 标准示例

当前已有 6 个标准 Plan：

```text
customer_selection.json
metric_query.json
group_analysis.json
trend_analysis.json
ranking_query.json
clarification.json
```

用于说明不同类型 Query Plan 的标准结构。

---

## 23. 测试体系

测试目录：

```text
tests/query_plan/
```

批量测试脚本：

```text
scripts/test_query_plan_cases.py
```

覆盖率检查：

```text
scripts/inspect_query_plan_coverage.py
```

当前测试数量：

```text
132
```

当前结果：

```text
所有 Query Plan 测试通过
```

---

## 24. 当前 Coverage

当前覆盖情况：

```text
Intent Coverage: 100.00%
Metric Coverage: 100.00%
Dimension Coverage: 100.00%
```

核心幻觉 / 非法 Plan 错误类型：

```text
全部覆盖
```

测试覆盖：

- Simple
- Medium
- Complex
- Ambiguous
- Entity
- Multi-turn
- Invalid / Hallucination
- Coverage
- Metric Coverage

---

## 25. Semantic Hallucination 防护

Stage 4 重点防止以下问题：

```text
不存在的 Metric
不存在的 Dimension
不存在的 Concept
不存在的 Entity
非法 Operator
非法 Time Range
未解决歧义
低置信度直接执行
```

原则：

> 宁可进入 needs_clarification，也不要创造不存在的语义。

---

## 26. 禁止裸 SQL

Business Query Plan 中禁止：

```json
{
  "sql": "SELECT ..."
}
```

第一层 Plan 也尽量不直接出现：

```text
table_name
field_name
SQL expression
```

Stage 4 当前只负责：

```text
Business Query Plan
```

未来可扩展为：

```text
Business Query Plan
↓
Logical Query Plan
↓
Physical SQL Plan
```

---

## 27. 常用命令

校验标准示例：

```powershell
python scripts/validate_query_plan.py
```

运行全部测试：

```powershell
python scripts/test_query_plan_cases.py
```

检查 Coverage：

```powershell
python scripts/inspect_query_plan_coverage.py
```

归一化单个 Plan：

```powershell
python scripts/normalize_query_plan.py query_plan/examples/customer_selection.json
```

---

## 28. 当前阶段结论

当前 Generic Query Plan 已具备：

- 通用 Intent
- 通用 Metric 引用
- 通用 Dimension 引用
- Filter Tree
- AND / OR / NOT
- Entity Reference
- Time Semantics
- Ranking
- Top-K
- Group Analysis
- Trend Analysis
- Comparison
- Clarification
- Multi-turn Context 预留
- Structural Validation
- Semantic Validation
- Hallucination Rejection
- Normalization
- 100+ Query Plan 测试
- 全 Registry Coverage

该模块将作为 Stage 5 Agent 生成结构化查询计划时的统一目标格式。
