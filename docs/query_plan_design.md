# Generic Query Plan 设计说明

## 1. 文档目的

本文档说明 Agentic Marketing 项目 Stage 4 —— Generic Query Plan（通用查询计划）的设计目标、总体架构、核心数据结构、验证机制、归一化机制、测试体系以及低幻觉设计。

Stage 4 的核心任务不是直接生成 SQL，而是将用户自然语言问题转换为一个结构化、可验证、可扩展的 Business Query Plan。

整体链路为：

```text
自然语言问题
↓
Stage 2 Metric System
+
Stage 3 Business Dictionary
↓
Generic Query Plan
↓
Structural Validation
+
Semantic Validation
↓
后续 Agent / SQL Generator
```

Stage 4 重点解决两个问题：

1. 如何让不同类型的自然语言问题统一表示；
2. 如何在 SQL 生成前拦截语义幻觉、歧义和非法查询计划。

---

## 2. 核心设计目标

### 2.1 普适化

Query Plan 不能围绕官方 Q&A 建立固定模板，也不能把问题写成：

```text
Q1 → 固定计划
Q2 → 固定计划
Q3 → 固定计划
```

而应把问题拆解为可复用的语义组件：

```text
Intent
Metric
Dimension
Filter
Entity
Time Range
Group By
Order By
Limit
Output
```

因此即使最终测试中出现此前未见过的：

- 新自然语言表达
- 新产品实体
- 新指标组合
- 新筛选条件
- 新分组方式
- 新排序要求
- 新多轮修改方式

也可以通过同一套 Query Plan Schema 表达。

---

### 2.2 降低 AI 幻觉

Query Plan 中的关键语义不得由模型自由创造。

所有语义必须能够追溯到已有 Registry 或 Metadata：

```text
Intent
→ metadata/intent_registry.yaml

Metric
→ metadata/metrics.yaml

Dimension
→ metadata/dimensions.yaml

Business Concept
→ metadata/business_dictionary.yaml

Operator
→ metadata/operator_registry.yaml

Time Semantics
→ metadata/time_semantics.yaml

Query Capability
→ metadata/query_capabilities.yaml

Entity
→ Stage 3 entity_rules + 实体解析结果
```

若模型输出不存在的指标、维度、概念、实体或操作符，Validator 必须拦截。

核心原则：

> 宁可澄清，不要猜测；宁可拒绝非法 Plan，也不要生成不存在的 SQL 语义。

---

## 3. Stage 4 与前三阶段的关系

### Stage 1：Data Model

解决：

```text
数据库里有什么
```

提供：

- 表
- 字段
- 主键
- 粒度
- Join
- 数据约束

---

### Stage 2：Metric System

解决：

```text
指标怎么算
```

例如：

```text
total_asset
average_total_asset
trade_amount
net_inflow
asset_profit
```

Query Plan 只能引用 Stage 2 已注册 Metric。

---

### Stage 3：Business Dictionary

解决：

```text
业务自然语言是什么意思
```

例如：

```text
钻石客户
本科及以上
股票
普通账户
高资产客户
优质客户
```

Query Plan 不重新定义这些概念，只引用 Stage 3 的标准业务语义。

---

### Stage 4：Generic Query Plan

解决：

```text
用户到底想查什么
以及
如何把需求结构化
```

因此 Stage 4 是自然语言理解层和后续 SQL 生成层之间的中间表示层。

---

## 4. 总体架构

当前 Stage 4 设计如下：

```text
User Question
↓
Semantic Parsing
├─ Intent Linking
├─ Metric Linking
├─ Dimension Linking
├─ Business Concept Linking
├─ Entity Resolution
└─ Time Parsing
↓
Generic Query Plan
↓
Normalization
↓
Structural Validator
↓
Semantic Validator
↓
Ready / Needs Clarification / Invalid
↓
Stage 5 Agent / 后续 SQL Generator
```

---

## 5. Stage 4 文件结构

### 5.1 Metadata

```text
metadata/
├─ intent_registry.yaml
├─ operator_registry.yaml
├─ time_semantics.yaml
└─ query_capabilities.yaml
```

作用：

```text
intent_registry.yaml
→ 注册允许的分析意图

operator_registry.yaml
→ 统一条件操作符

time_semantics.yaml
→ 统一时间表达

query_capabilities.yaml
→ 明确不同 Intent 当前支持的能力
```

---

### 5.2 Query Plan

```text
query_plan/
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
│  └─ clarification.json
│
└─ README.md
```

---

### 5.3 Scripts

```text
scripts/
├─ validate_query_plan.py
├─ normalize_query_plan.py
├─ test_query_plan_cases.py
├─ inspect_query_plan_coverage.py
├─ add_dimension_coverage_cases.py
└─ add_metric_coverage_cases.py
```

其中：

```text
validate_query_plan.py
→ Structural + Semantic Validation

normalize_query_plan.py
→ Query Plan 归一化

test_query_plan_cases.py
→ 批量运行测试

inspect_query_plan_coverage.py
→ 统计 Intent / Metric / Dimension 等覆盖率

add_dimension_coverage_cases.py
→ 自动补齐 Dimension Coverage 测试

add_metric_coverage_cases.py
→ 自动补齐 Metric Coverage 测试
```

---

### 5.4 Tests

```text
tests/
└─ query_plan/
```

当前用于存放：

- Simple
- Medium
- Complex
- Ambiguous
- Entity
- Multi-turn
- Invalid / Hallucination
- Coverage
- Metric Coverage

等 Query Plan 测试。

---

## 6. Intent Registry 设计

当前第一版支持：

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

Intent 只表达：

```text
用户想做哪类分析任务
```

例如：

```text
“南京客户查询”
```

不是 Intent。

正确表示应为：

```text
intent = customer_selection
filter = city eq 南京
```

这样具体城市、产品、客户等级等信息进入 Filter，而不是不断扩张 Intent 数量。

---

## 7. Operator Registry 设计

Query Plan 不允许模型输出任意 SQL 操作符。

当前统一使用 canonical operator：

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

逻辑操作符：

```text
and
or
not
```

例如：

```text
大于
>
gt
```

统一归一化为：

```text
gt
```

这样可以减少模型输出格式漂移，并为 Validator 提供固定可验证集合。

---

## 8. Time Semantics 设计

当前支持：

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

Stage 4 不直接在 Plan 中写：

```text
2026-01-01 ~ 2026-03-31
```

而只表达：

```text
2026 Q1
```

真正的自然时间语义到实际日期范围的转换由后续 Time Resolver 完成。

这样可以避免把某一年 Q1 写死，提高通用性。

---

## 9. Query Capability Matrix

`metadata/query_capabilities.yaml` 用于声明当前不同 Intent 可以使用哪些能力。

例如：

```text
customer_selection
→ dimension_filter
→ metric_filter
→ concept_filter
→ entity_filter
→ time_filter
→ and/or/not
→ ordering
→ limit

group_analysis
→ group_by
→ metric_aggregation
→ ordering
→ limit

trend_analysis
→ time_grouping
→ metric_aggregation
→ time_filter
```

若用户提出当前系统尚不支持的能力，Validator 应拒绝或要求澄清，而不是让模型强行生成 SQL。

---

## 10. Query Plan 顶层结构

当前 Query Plan 版本为：

```text
1.0
```

顶层结构为：

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

## 11. Status 状态设计

Query Plan 只允许三种状态：

```text
ready
needs_clarification
invalid
```

### ready

Plan 已具备执行条件，但仍需通过 Validator。

### needs_clarification

存在未解决问题，例如：

- 时间不明确
- 模糊业务规则
- 多个实体候选
- 关键语义置信度不足

此状态不能继续生成 SQL。

### invalid

Plan 已确认结构或语义非法，不能执行。

---

## 12. Subject 设计

当前支持：

```text
customer
product
branch
transaction
holding
```

第一版主要围绕：

```text
customer
```

但保留 product、branch、transaction、holding 等主体，为后续扩展提供空间。

---

## 13. Metric 引用规则

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
asset_profit
fund_holding_ratio
```

若出现：

```text
customer_satisfaction_score
```

但 Stage 2 未注册，则 Semantic Validator 返回：

```text
UNKNOWN_METRIC
```

不允许模型根据名字自行定义指标公式。

---

## 14. Dimension 引用规则

所有 Dimension 必须来自：

```text
metadata/dimensions.yaml
```

当前已注册并在测试中全部覆盖：

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

## 15. Filter Schema

简单 Filter 统一结构：

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

当前 Filter 类型：

```text
dimension
metric
concept
entity
```

---

## 16. Filter Source

每个 Filter 必须记录来源：

```text
explicit
dictionary
entity_resolution
derived_rule
context
business_default
```

例如：

```text
“南京客户”
```

可以得到：

```text
city = 南京
source = explicit
```

而：

```text
“钻石客户”
```

来自 Stage 3 Business Dictionary，因此：

```text
source = dictionary
```

该设计可以追踪条件来源，防止模型偷偷添加用户没有提出的条件。

---

## 17. Filter Tree

Stage 4 不只支持扁平 AND，还支持任意嵌套：

```text
AND
OR
NOT
```

例如：

```json
{
  "logic": "and",
  "conditions": [
    {
      "target": "city",
      "operator": "eq",
      "value": "南京"
    },
    {
      "logic": "or",
      "conditions": [
        {
          "target": "fund_holding_ratio",
          "operator": "lt",
          "value": 0.1
        },
        {
          "target": "cash_asset_ratio",
          "operator": "gt",
          "value": 0.5
        }
      ]
    }
  ]
}
```

这使 Query Plan 可以表达复杂客户筛选场景。

---

## 18. Entity Reference 设计

具体实体不在 Business Dictionary 中全部硬编码。

例如：

```text
招商银行
贵州茅台
中国平安
南京某营业部
某客户号
```

应先通过 Stage 3 Entity Resolver 动态解析。

已解析实体结构：

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

如果存在多个候选：

```text
resolution_status = ambiguous
```

Query Plan 应进入：

```text
needs_clarification
```

而不是让模型随机选择一个产品 ID。

---

## 19. Group By / Having / Order By / Limit

### Group By

用于表达分组维度。

例如：

```text
按客户等级统计人数
```

表示：

```text
group_by = customer_level
```

### Having

用于保留聚合后过滤语义。

第一版仍停留在业务语义层，后续 SQL Planner 再决定 WHERE / HAVING 的实际位置。

### Order By

例如：

```text
按日均资产降序
```

表示：

```json
{
  "field": "average_total_asset",
  "direction": "desc"
}
```

### Limit

用于 Top-K：

```text
前20名
→ limit = 20
```

---

## 20. Output 结构

当前输出需求可以结构化为：

```json
{
  "mode": "aggregate",
  "format": "table",
  "include_details": false,
  "include_explanation": true
}
```

当前支持：

```text
mode:
detail
aggregate
summary

format:
table
text
chart
```

Stage 4 只表达输出需求，不负责真正画图。

---

## 21. Clarification 机制

对于：

```text
近期
活跃
优质客户
大额资金
重点客户
热门产品
```

如果上下文不足，Query Plan 必须记录歧义：

```json
{
  "term": "近期",
  "type": "time",
  "reason": "未指定明确时间范围",
  "question": "你希望最近7天、30天还是3个月？",
  "candidates": [
    "last_7_days",
    "last_30_days",
    "last_3_months"
  ]
}
```

并设置：

```text
status = needs_clarification
```

这种机制是降低业务语义幻觉的关键。

---

## 22. Assumption 策略

`assumptions` 默认：

```json
[]
```

不鼓励模型自动假设。

如果 Plan 出现 assumption，应被标记为需要审查。

原则：

> 用户没有说、业务规则没有定义、Metadata 没有证据的内容，不应静默补充。

---

## 23. Confidence 策略

当前 Query Plan 保存：

```text
overall
intent
metrics
dimensions
entities
time
filters
```

等置信度。

执行阈值由 `metadata/query_plan_confidence.yaml` 配置，当前策略为：

```text
ready + overall < 0.85
→ LOW_CONFIDENCE
→ Fail Closed，不允许执行

ready + 任一已提供的关键组件置信度 < 0.60
→ LOW_CONFIDENCE
→ 进入澄清流程

ready + overall >= 0.85
→ 可继续后续流程

needs_clarification
→ 允许低置信度
```

原因是：

```text
needs_clarification
```

本身就是一种主动承认不确定性的合法状态。

---

## 24. 多轮上下文设计

Stage 4 为多轮对话预留：

```json
{
  "parent_plan_id": null,
  "operation": "new"
}
```

当前支持：

```text
new
modify
refine
compare
```

示例：

```text
第一轮：
Q1 南京客户平均资产是多少？

第二轮：
只看钻石客户。

第三轮：
那苏州呢？
```

理想情况下：

```text
第二轮
→ refine

第三轮
→ modify city filter
```

而不是每轮重新生成完全独立的 Plan。

---

## 25. Plan Patch 预留

未来可以进一步实现：

```json
{
  "operation": "modify",
  "changes": [
    {
      "action": "replace_filter",
      "target": "city",
      "value": "苏州"
    }
  ]
}
```

Stage 4 当前只做 Context 结构预留，不实现完整 Patch Engine。

---

## 26. JSON Schema 设计

当前使用：

```text
JSON Schema Draft 2020-12
```

四个 Schema：

```text
query_plan.schema.json
filter.schema.json
time_range.schema.json
entity_ref.schema.json
```

作用分别为：

```text
query_plan.schema.json
→ 顶层 Query Plan 结构

filter.schema.json
→ 简单 Filter + AND/OR/NOT Filter Tree

time_range.schema.json
→ 时间结构

entity_ref.schema.json
→ 实体解析结果结构
```

---

## 27. Structural Validation

Structural Validation 负责：

- JSON 是否合法
- 必填字段是否存在
- 字段类型是否正确
- enum 是否允许
- quarter 是否为 1~4
- confidence 是否为 0~1
- limit 是否 >= 1
- Filter 是否符合 Schema
- Entity 是否符合 Schema
- Time Range 是否符合 Schema

典型错误：

```text
quarter = 8
limit = -20
非法 operator
缺少必填字段
```

这类问题无需进入业务语义验证。

---

## 28. Semantic Validation

Structural Validation 通过后，继续 Semantic Validation。

当前检查：

```text
Intent 是否注册
Metric 是否注册
Dimension 是否注册
Concept 是否注册
Operator 是否注册
Entity 是否解析完成
Time Type 是否注册
Capability 是否支持
Ambiguity 是否解决
Confidence 是否符合执行条件
Order By 字段是否有效
```

---

## 29. 主要错误码

当前 Validator 使用：

```text
UNKNOWN_INTENT
UNKNOWN_METRIC
UNKNOWN_DIMENSION
UNKNOWN_CONCEPT
UNKNOWN_OPERATOR
UNRESOLVED_ENTITY
INVALID_TIME_RANGE
UNSUPPORTED_CAPABILITY
UNKNOWN_ORDER_FIELD
LOW_CONFIDENCE
MEDIUM_CONFIDENCE
MISSING_AMBIGUITY
UNRESOLVED_AMBIGUITY
STRUCTURAL_ERROR
```

通过标准化错误码，后续 Agent 可以：

```text
Pass
Repair
Clarify
Reject
```

而不是依赖模糊文本判断。

---

## 30. Normalization 设计

`normalize_query_plan.py` 用于将不同写法统一为 canonical value。

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
descending
降序
desc
→ desc
```

同时可以规范：

- Metric Alias
- Concept Alias
- Operator Alias
- City Value
- Time Value
- Order Direction

Normalization 和 Validation 分离：

```text
Normalization
→ 尽量把可确定的同义表达归一

Validation
→ 判断归一后语义是否真实合法
```

---

## 31. 不允许自动修复所有错误

对于能够通过注册 Alias 明确修复的问题：

```text
可自动归一化
```

例如：

```text
大于
→ gt
```

但如果只能靠模型猜测：

```text
不能自动修复
```

例如：

```text
优质客户
```

不能自动等于：

```text
average_total_asset >= 1000000
```

而必须要求澄清。

---

## 32. 标准 Query Plan 示例

当前已建立：

```text
customer_selection.json
metric_query.json
group_analysis.json
trend_analysis.json
ranking_query.json
clarification.json
```

分别验证：

- 客户筛选
- 指标查询
- 分组统计
- 趋势分析
- 排名分析
- 模糊语义澄清

全部已通过：

```text
Structural Validation
+
Semantic Validation
```

---

## 33. 测试体系

Stage 4 不只使用官方 Q&A。

当前测试类别包括：

```text
Simple
Medium
Complex
Ambiguous
Entity
Multi-turn
Invalid / Hallucination
Coverage
Metric Coverage
```

基础规划要求至少：

```text
100 条 Query Plan 测试
```

目前实际测试数量已达到：

```text
132 条
```

并已完成批量测试。

---

## 34. 测试执行脚本

批量测试：

```powershell
python scripts/test_query_plan_cases.py
```

覆盖率检查：

```powershell
python scripts/inspect_query_plan_coverage.py
```

标准示例校验：

```powershell
python scripts/validate_query_plan.py
```

单 Plan 归一化：

```powershell
python scripts/normalize_query_plan.py query_plan/examples/customer_selection.json
```

---

## 35. 当前测试结果

当前测试结果：

```text
Tests: 132
```

全部 Query Plan 测试通过。

覆盖率：

```text
Intent Coverage: 100.00%
Metric Coverage: 100.00%
Dimension Coverage: 100.00%
```

其中：

```text
注册 Metric：38
已覆盖 Metric：38

注册 Dimension：21
已覆盖 Dimension：21
```

核心幻觉 / 非法 Plan 错误类型：

```text
已覆盖
```

---

## 36. 幻觉防护测试

当前 Invalid / Hallucination 测试覆盖典型问题：

```text
不存在的 Metric
不存在的 Dimension
不存在的 Concept
非法 Time Range
未知 Operator
未解析 Entity
不存在 Entity
低 Confidence Ready Plan
Ready 状态仍有 Ambiguity
Ranking 缺少 Order By
```

这些测试要求：

```text
Validator 必须拒绝
```

而不是让系统继续生成 SQL。

---

## 37. Semantic Hallucination Rate

Stage 4 重点关注：

```text
Semantic Hallucination Rate
```

定义为：

```text
输出未注册 Metric / Dimension / Concept / Entity 的 Query Plan 数量
/
总 Query Plan 数量
```

Stage 4 的目标是：

```text
尽可能接近 0
```

当前主要通过：

- Registry
- JSON Schema
- Semantic Validator
- Entity Resolution
- Ambiguity Handling
- Confidence Policy

共同降低语义幻觉。

---

## 38. 为什么不直接 NL → SQL

直接：

```text
Natural Language
↓
LLM
↓
SQL
```

容易产生：

- 幻觉字段
- 幻觉表
- 错误 Join
- 错误指标公式
- 错误实体 ID
- 隐式业务假设
- 时间口径错误

因此本项目采用：

```text
Natural Language
↓
Semantic Parse
↓
Business Query Plan
↓
Validate
↓
后续 SQL Generator
```

先把语义层稳定下来，再进入 SQL 层。

---

## 39. Query Plan 中禁止裸 SQL

Stage 4 Business Query Plan 不允许：

```json
{
  "sql": "SELECT ..."
}
```

也尽量不直接出现：

```text
table_name
field_name
raw SQL expression
```

第一层 Plan 表达的是业务语义：

```text
average_total_asset
city
customer_level
stock_trade_amount
```

数据库表字段映射留给后续 Resolver / SQL Planner。

---

## 40. 三层 Plan 架构预留

项目未来可以扩展为：

```text
Business Query Plan
↓
Logical Query Plan
↓
Physical SQL Plan
```

当前 Stage 4 只实现：

```text
Business Query Plan
```

这样可以把：

```text
用户语义
```

与：

```text
数据库实现细节
```

解耦。

---

## 41. 当前 Stage 4 能力

当前 Generic Query Plan 已具备：

- Customer Selection
- Metric Query
- Group Analysis
- Trend Analysis
- Ranking
- Entity Lookup
- Customer Profile
- Segment Analysis
- Comparison
- 多 Metric
- 多 Dimension
- Metric Filter
- Dimension Filter
- Concept Filter
- Entity Filter
- AND / OR / NOT
- Group By
- Having 语义预留
- Order By
- Top-K
- Time Range
- Entity Resolution Result
- Clarification
- Confidence
- Multi-turn Context
- Structural Validation
- Semantic Validation
- Normalization
- Hallucination Rejection

---

## 42. 当前阶段边界

Stage 4 当前不负责：

```text
LLM 真正生成 Query Plan
SQL 生成
SQL 执行
结果解释 Agent
营销触达
```

这些能力将在后续阶段实现。

当前 Stage 4 的职责只有：

```text
定义一个正确、统一、可验证的 Query Plan 应该长什么样
```

---

## 43. 与 Stage 5 Agent 的接口

Stage 5 Agent 应按照以下流程工作：

```text
Natural Language
↓
Metadata / Metric / Dictionary Tool
↓
生成 Query Plan
↓
Normalization
↓
Structural Validation
↓
Semantic Validation
↓
Pass / Repair / Clarify
```

而不是：

```text
LLM
↓
直接 SQL
```

Stage 5 的模型输出必须以 Stage 4 Query Plan Schema 为目标结构。

---

## 44. Stage 4 当前成果

### Metadata

```text
intent_registry.yaml
operator_registry.yaml
time_semantics.yaml
query_capabilities.yaml
```

### Schema

```text
query_plan.schema.json
filter.schema.json
time_range.schema.json
entity_ref.schema.json
```

### Examples

```text
customer_selection.json
metric_query.json
group_analysis.json
trend_analysis.json
ranking_query.json
clarification.json
```

### Scripts

```text
validate_query_plan.py
normalize_query_plan.py
test_query_plan_cases.py
inspect_query_plan_coverage.py
```

### Documents

```text
query_plan/README.md
docs/query_plan_test_cases.md
docs/query_plan_design.md
```

### Tests

```text
132 条 Query Plan 测试
```

当前：

```text
Intent Coverage = 100%
Metric Coverage = 100%
Dimension Coverage = 100%
```

---

## 45. 设计结论

Stage 4 已建立一套面向通用智能问数场景的 Business Query Plan 表示体系。

它不是针对官方 Q&A 的模板系统，而是通过：

```text
Registry
+
Schema
+
Normalization
+
Validation
+
Clarification
+
Entity Resolution
+
Test Coverage
```

共同构建一个可扩展、可验证、低幻觉的查询计划层。

其核心价值在于：

> 在让大模型真正参与 SQL 生成之前，先用结构化 Query Plan 把“用户到底想查什么”固定下来，并且确保这个语义计划可以被已有 Metadata、Metric System 和 Business Dictionary 验证。

Stage 4 将作为 Stage 5 Agent 的统一结构化输出目标。
