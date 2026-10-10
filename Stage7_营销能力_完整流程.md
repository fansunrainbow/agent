# Stage 7 — Marketing Capability（客户营销能力层）完整流程

> 本阶段建立在 Stage 1～6 已完成能力之上。
>
> 项目总目标仍然只有两个最高优先级：
>
> 1. **普适化**：营销能力不能只针对官方 Q&A，也不能只支持固定客群或固定产品；新增营销策略、客群规则、标签体系时应优先通过配置扩展。
> 2. **低幻觉**：所有客户标签、营销机会、圈客结果、策略建议都必须能够追溯到真实数据、已注册指标、业务规则和查询结果，禁止模型凭空编造客户画像、偏好、需求或风险。

---

# 0. Stage 7 的定位

前六个阶段已经完成：

```text
Stage 1 — Data Model
Stage 2 — Metric System
Stage 3 — Generalized Business Dictionary
Stage 4 — Generic Query Plan
Stage 5 — Agent Core & Orchestration
Stage 6 — Guardrail
```

现在系统已经具备：

```text
自然语言
↓
语义 Grounding
↓
Generic Query Plan
↓
安全 SQL
↓
Guardrail
↓
可信结果
```

Stage 7 要解决的是：

> 如何把“安全问数能力”升级成“客户经营与营销能力”。

也就是说，不再只是回答“南京客户有多少”，还要支持：

```text
哪些客户值得重点经营？
哪些客户存在资产流出风险？
哪些客户基金配置不足？
某个客群的结构特征是什么？
为什么这个客户被圈进这个客群？
```

注意：Stage 7 不是做“无依据推荐”，而是：

```text
真实数据
+
标准指标
+
业务规则
+
可解释标签
↓
客户经营能力
```

---

# 1. Stage 7 总体架构

```text
Validated Data Result
↓
Customer Feature Builder
↓
Tag Engine
↓
Segment Engine
↓
Opportunity Detector
↓
Strategy Engine
↓
Explanation Layer
↓
Marketing Result
```

---

# 2. Stage 7 最终目标能力

第一版建议实现：

```text
1. 智能圈客
2. 客户360画像
3. 客群洞察
4. 营销机会发现
5. 可解释策略建议
```

---

# 3. 推荐目录结构

```text
marketing/
├─ feature_builder.py
├─ tag_engine.py
├─ segment_engine.py
├─ opportunity_detector.py
├─ strategy_engine.py
├─ explanation.py
│
├─ models/
│  ├─ customer_feature.py
│  ├─ customer_tag.py
│  ├─ segment_result.py
│  ├─ opportunity.py
│  └─ strategy_result.py
│
├─ rules/
│  ├─ tag_rules.yaml
│  ├─ segment_rules.yaml
│  ├─ opportunity_rules.yaml
│  └─ strategy_rules.yaml
│
└─ services/
   ├─ customer_profile_service.py
   ├─ cohort_analysis_service.py
   └─ marketing_analysis_service.py

tests/
└─ marketing/

docs/
├─ marketing_capability.md
├─ marketing_rules.md
└─ marketing_test_cases.md
```

---

# 4. Stage 7.1 — Customer Feature Builder

先不要直接做标签，先把客户经营特征统一构建出来。

建议特征来源：

```text
客户基本信息
资产
持仓
交易
资金流
产品配置
```

例如：

```text
customer_id
age
gender
customer_level
city
average_total_asset
period_end_asset
asset_change_rate
cash_asset
cash_asset_ratio
holding_market_value
stock_holding_ratio
fund_holding_ratio
bond_holding_ratio
trade_amount
trade_count
stock_trade_amount
fund_trade_amount
net_inflow
```

原则：

所有 Feature 必须来自：

```text
Stage 2 Metric
+
Stage 3 Dimension
+
Stage 6 Safe Result
```

禁止自己写新公式、猜客户偏好、生成无来源风险分。

---

# 5. Customer Feature Model

建议：

```python
class CustomerFeature(BaseModel):
    customer_id: str
    features: dict
    source_metrics: list[str]
    time_range: dict | None
    confidence: float
    trace: list[dict]
```

必须保留来源指标、时间范围、数据来源。

---

# 6. Stage 7.2 — Tag Engine

标签是营销能力核心。

例如：

```text
高净值
高现金
股票偏好
基金低配置
交易活跃
近期净流入
近期净流出
资产增长
资产下降
```

但标签必须：

```text
规则化
参数化
可解释
```

创建：

```text
marketing/rules/tag_rules.yaml
```

示例：

```yaml
tags:

  high_asset:
    name: 高资产客户
    conditions:
      - metric: average_total_asset
        operator: gte
        parameter: threshold

    defaults:
      threshold: 1000000

    explain:
      template: "日均资产达到 {threshold} 元以上"

  high_cash_ratio:
    name: 高现金占比
    conditions:
      - metric: cash_asset_ratio
        operator: gte
        parameter: threshold

    defaults:
      threshold: 0.5
```

---

# 7. 标签规则必须参数化

不要永久写死：

```text
100万 = 高资产
```

优先级建议：

```text
用户指定
>
业务配置
>
默认阈值
```

---

# 8. 标签不能冒充预测

例如可以定义：

```text
资产流出重点关注
```

基于：

```text
net_inflow < 0
asset_change_rate < 0
```

但不要叫：

```text
高流失概率
```

除非真正有训练标签、模型和验证指标。

---

# 9. Stage 7.3 — Customer 360

Customer 360 输出建议包括：

```text
基本属性
客户等级
资产情况
资产变化
持仓结构
交易活跃度
资金流
产品配置
标准标签
```

例如：

```json
{
  "customer_id": "...",
  "basic_profile": {},
  "asset_profile": {},
  "holding_profile": {},
  "trading_profile": {},
  "fund_flow_profile": {},
  "tags": []
}
```

每个标签必须能解释为什么命中。

---

# 10. Stage 7.4 — Segment Engine

智能圈客核心。

输入：

```text
规则 + Feature
```

输出：

```text
客户集合 + 命中原因 + 指标值
```

创建：

```text
marketing/rules/segment_rules.yaml
```

例如：

```yaml
segments:

  high_asset_low_fund:
    name: 高资产低基金配置客户

    logic: AND

    conditions:
      - metric: average_total_asset
        operator: gte
        value: 1000000

      - metric: fund_holding_ratio
        operator: lt
        value: 0.1
```

必须支持：

```text
AND
OR
NOT
```

新增客群应优先只增加 YAML，不修改核心 Python。

---

# 11. Stage 7.5 — Cohort Analysis

圈客后支持分析：

```text
人数
资产规模
平均资产
年龄结构
地区结构
客户等级结构
产品配置
交易活跃度
资金流情况
```

例如：

```text
“基金低配置高资产客户”中：
- 共有多少人
- 平均资产多少
- 主要年龄段
- 主要城市
- 股票配置比例
```

---

# 12. Stage 7.6 — Opportunity Detector

第一版建议规则化发现，不做无依据机器学习预测。

建议机会类型：

```text
高资产 + 低基金配置
高现金 + 低理财配置
高交易活跃 + 单一产品偏好
高等级客户 + 净流出
资产下降 + 净流出
近期大额净流入
```

创建：

```text
marketing/rules/opportunity_rules.yaml
```

例如：

```yaml
opportunities:

  fund_allocation_opportunity:
    name: 基金配置机会

    conditions:
      - metric: average_total_asset
        operator: gte
        value: 1000000

      - metric: fund_holding_ratio
        operator: lt
        value: 0.1

    evidence:
      - average_total_asset
      - fund_holding_ratio
```

Opportunity 必须保留 Evidence。

---

# 13. Stage 7.7 — Strategy Engine

Strategy Engine 不能凭空给客户推荐某只基金。

第一版建议输出：

```text
经营策略类型
而不是具体金融产品推荐
```

例如：

```text
增加基金类产品配置沟通
关注资金流出情况
重点维护高资产客户
进行产品结构优化沟通
```

创建：

```text
marketing/rules/strategy_rules.yaml
```

例如：

```yaml
strategies:

  improve_fund_allocation:
    name: 基金配置沟通

    trigger_opportunities:
      - fund_allocation_opportunity

    action:
      type: engagement
      description: "建议围绕基金配置情况进行客户沟通"

    prohibited:
      - specific_product_recommendation_without_suitability
```

---

# 14. 事实、规则判断、建议必须分离

建议输出结构：

```text
事实：
客户日均资产 185 万
基金占比 4.3%

规则判断：
命中“高资产低基金配置”

经营建议：
可作为基金配置沟通的重点客群
```

禁止写：

```text
客户一定需要购买基金
```

---

# 15. Stage 7.8 — Explainability Layer

任何：

```text
Tag
Segment
Opportunity
Strategy
```

都必须可解释。

建议：

```json
{
  "decision": "fund_allocation_opportunity",
  "rules": [
    {
      "metric": "average_total_asset",
      "actual": 1850000,
      "operator": ">=",
      "threshold": 1000000,
      "passed": true
    },
    {
      "metric": "fund_holding_ratio",
      "actual": 0.043,
      "operator": "<",
      "threshold": 0.1,
      "passed": true
    }
  ]
}
```

---

# 16. Stage 7.9 — Marketing Tools

建议后续 Agent 能调用：

```text
build_customer_profile()
calculate_tags()
evaluate_segment()
find_opportunities()
analyze_segment()
get_strategy()
```

Agent 不自己判断客户属于什么客群，而是调用 Marketing Tool → Rule Engine。

---

# 17. Stage 7.10 — 配置版本化

营销规则建议带：

```text
rule_id
version
effective_from
effective_to
```

每条规则注明来源：

```text
internal_config
business_policy
user_defined
```

阈值来源也记录：

```text
user_input
business_config
default
```

---

# 18. 营销机会优先级

可以设计：

```text
high
medium
low
```

但不要让 LLM自由评分。

如需 Opportunity Score，优先使用透明、配置化规则公式，权重可审计。

---

# 19. 第一版不要做复杂 ML

目前没有明确：

```text
营销响应标签
流失标签
购买标签
```

所以第一版不要声称：

```text
流失预测
购买概率
转化概率
```

无监督聚类可作为后续增强项，不是第一优先级。

---

# 20. 数据时间一致性

所有标签和营销规则必须保存：

```text
统计时间范围
attribute_snapshot_date
metric_time_range
```

避免把不同时间口径指标随意组合。

---

# 21. 缺失事实处理

需要区分：

```text
no_record
zero
unknown
```

例如“从未交易”应优先使用 NOT EXISTS，而不是简单判断金额等于 0。

---

# 22. Marketing Trace

建议记录：

```text
customer_id
feature_values
matched_tags
matched_segment
matched_opportunities
strategy
rule_version
time_range
```

用于解释、审计、Demo 和 Benchmark。

---

# 23. Stage 7 测试体系

必须包含：

```text
Tag Tests
Segment Tests
Opportunity Tests
Strategy Tests
Explainability Tests
Generalization Tests
Hallucination Tests
```

Generalization Test 要验证：

```text
新增 Tag / Segment / Opportunity Rule
只改 YAML
不改核心 Python
```

Hallucination Test 要验证：

```text
不存在的客户属性、风险偏好、需求、购买意图
不能凭空生成
```

---

# 24. 人工验收案例

建议至少：

```text
1. 找高资产但基金配置低的客户
2. 找近期净流出且资产下降的高等级客户
3. 查询某客户360画像
4. 分析基金低配置客群特征
5. 给出某客群经营机会
6. 解释为什么某客户命中标签
7. 新增一个债券低配置规则后重新圈客
8. 删除一个规则后结果同步变化
9. 不存在的客户偏好不得生成
10. 不允许无适当性依据推荐具体金融产品
```

---

# 25. Stage 7 推荐开发顺序

```text
Stage 7.1 Customer Feature Builder
↓
Stage 7.2 Tag Engine
↓
Stage 7.3 Customer 360
↓
Stage 7.4 Segment Engine
↓
Stage 7.5 Cohort Analysis
↓
Stage 7.6 Opportunity Detector
↓
Stage 7.7 Strategy Engine
↓
Stage 7.8 Explainability
↓
Stage 7.9 Marketing Tools
↓
Stage 7.10 Tests + Benchmark
```

---

# 26. Codex 执行要求

1. 不破坏 Stage 1～6。
2. 不为官方 Q&A 写特殊营销逻辑。
3. 所有标签必须基于注册 Metric / Dimension。
4. 所有圈客规则配置化。
5. 高级营销概念必须可解释。
6. 不允许 LLM凭空推断客户偏好。
7. 不允许无依据流失预测或购买概率。
8. 不允许无适当性数据直接推荐具体金融产品。
9. 所有建议区分事实、规则判断和经营建议。
10. 新规则优先通过 YAML 扩展。
11. 所有规则记录版本和来源。
12. 所有判断记录时间范围。
13. 新代码必须有测试。
14. Generalization Test 必须覆盖“只改规则不改代码”。
15. Hallucination Test 必须验证不生成不存在属性。

---

# 27. Stage 7 验收清单

```text
[ ] Customer Feature Builder 完成
[ ] 所有 Feature 可追溯到 Stage 2 Metric / Dimension

[ ] Tag Engine 完成
[ ] Tag 规则参数化
[ ] Tag 可解释

[ ] Customer 360 完成

[ ] Segment Engine 完成
[ ] 支持 AND / OR / NOT
[ ] 新客群不改核心代码

[ ] Cohort Analysis 完成

[ ] Opportunity Detector 完成
[ ] Opportunity 有 Evidence

[ ] Strategy Engine 完成
[ ] 事实与建议分离
[ ] 无依据时不推荐具体金融产品

[ ] Explainability 完成
[ ] Marketing Tools 完成

[ ] Rule Version 完成
[ ] Rule Source 完成
[ ] Threshold Source 完成
[ ] Time Range 可追踪

[ ] Generalization Test 通过
[ ] Hallucination Test 通过

[ ] 官方 Q&A 不是业务逻辑来源
```

---

# 28. Stage 7 完成后的能力

系统将具备：

```text
自然语言问数
+
智能筛客
+
客户360
+
客群洞察
+
机会识别
+
经营策略建议
+
全链路解释
```

下一阶段：

```text
Stage 8 — Benchmark
```

Stage 7 的本质不是“让模型学会营销”，而是：

> **把真实数据和可验证业务规则组织成可配置、可解释、可泛化的客户经营能力。**
