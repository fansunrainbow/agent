# Stage 8 — Benchmark（统一评测体系）完整流程

## 一、目标

Stage 8 不再新增主要业务能力，而是把 Stage 1～7 的能力变成可量化、可复现、可展示的评测结果。

两个最高优先级继续保持：

1. **普适化**：Benchmark 不能只测官方 Q&A，必须覆盖新表达、新组合、新实体、多轮、安全和营销场景。
2. **低幻觉**：必须量化语义幻觉、SQL 幻觉、结果幻觉、营销幻觉以及 Unsupported Handling 能力。

总体流程：

```text
Benchmark Dataset
↓
Unified Runner
↓
Stage-wise Evaluation
↓
Metrics
↓
Failure Analysis
↓
Benchmark Report
```

---

## 二、Benchmark 分类

建议建立以下 10 类：

```text
1. Semantic Benchmark
2. Query Plan Benchmark
3. SQL Benchmark
4. Result Benchmark
5. Hallucination Benchmark
6. Guardrail Benchmark
7. Generalization Benchmark
8. Multi-turn Benchmark
9. Marketing Benchmark
10. End-to-End Benchmark
```

同时统计：

```text
Latency
Stability
Coverage
Repair
Clarification
Trace Completeness
```

---

## 三、推荐目录

```text
benchmark/
├─ datasets/
│  ├─ official_seed.jsonl
│  ├─ semantic.jsonl
│  ├─ query_plan.jsonl
│  ├─ sql.jsonl
│  ├─ hallucination.jsonl
│  ├─ guardrail.jsonl
│  ├─ generalization.jsonl
│  ├─ multi_turn.jsonl
│  ├─ marketing.jsonl
│  └─ end_to_end.jsonl
├─ evaluators/
│  ├─ semantic_evaluator.py
│  ├─ plan_evaluator.py
│  ├─ sql_evaluator.py
│  ├─ result_evaluator.py
│  ├─ hallucination_evaluator.py
│  ├─ guardrail_evaluator.py
│  ├─ marketing_evaluator.py
│  └─ latency_evaluator.py
├─ runner/
│  ├─ benchmark_runner.py
│  └─ case_runner.py
├─ reports/
│  ├─ benchmark_report.json
│  ├─ benchmark_report.md
│  └─ failure_cases.jsonl
└─ fixtures/
```

---

## 四、Benchmark Case Schema

每条 Case 至少包含：

```json
{
  "case_id": "SEM-001",
  "category": "semantic",
  "query": "2026年Q1南京客户日均资产是多少？",
  "expected": {},
  "difficulty": "medium",
  "source": "self_built",
  "tags": []
}
```

难度建议：

```text
simple
medium
complex
adversarial
```

来源必须标记：

```text
official_seed
self_built
generalization
adversarial
human_reviewed
```

---

## 五、Official Q&A 定位

官方 Q&A 只能作为：

```text
Official Seed Benchmark
```

不能作为：

```text
唯一评测集
业务规则来源
SQL 模板来源
```

---

## 六、Semantic Benchmark

评测：

```text
Intent Accuracy
Metric Linking Accuracy
Dimension Linking Accuracy
Concept Linking Accuracy
Entity Resolution Accuracy
Time Parsing Accuracy
Operator Accuracy
Clarification Accuracy
Unsupported Detection Accuracy
```

推荐指标：

```text
Accuracy
Precision
Recall
F1
Exact Match
```

---

## 七、Query Plan Benchmark

比较：

```text
intent
metrics
dimensions
filters
entities
time_range
group_by
having
order_by
limit
status
```

核心指标：

```text
Plan Exact Match
Plan Component F1
```

---

## 八、SQL Benchmark

不要只比较 SQL 字符串。

至少评测：

```text
SQL Compile Success
Schema Validity
Join Validity
Parameterized Value Accuracy
Execution Success
Execution Equivalence
```

多种等价 SQL 应优先比较执行结果，而不是文本完全一致。

---

## 九、Result Benchmark

根据结果类型分别评测：

```text
Scalar Accuracy
Set Precision / Recall / F1
Ranking Accuracy
Aggregation Accuracy
Grouped Result Accuracy
```

---

## 十、Hallucination Benchmark

至少覆盖：

```text
不存在 Metric
不存在 Dimension
不存在 Entity
不存在 Customer Attribute
不存在 Product Attribute
不存在 Business Concept
无法支持的预测请求
无适当性数据的具体产品推荐
```

分类：

```text
Semantic Hallucination
SQL Hallucination
Result Hallucination
Marketing Hallucination
```

核心指标：

```text
Semantic Hallucination Rate
SQL Hallucination Rate
Marketing Hallucination Rate
Unsupported Handling Accuracy
```

Semantic Hallucination Rate 可定义为：

```text
生成未注册 Metric / Dimension / Concept / Entity 的 Case 数
/
全部相关 Case 数
```

---

## 十一、Guardrail Benchmark

至少测试：

```text
DROP
DELETE
UPDATE
INSERT
ALTER
TRUNCATE
SELECT *
未知表
未知字段
非法 Join
事实表直接 Join
无时间条件大表扫描
超大 LIMIT
SQL 注释
多语句
非法函数
未参数化业务值
```

指标：

```text
Unsafe Query Block Rate
Safe Query Pass Rate
False Positive Rate
False Negative Rate
```

---

## 十二、Generalization Benchmark

必须专门测试官方 Q&A 未覆盖的新情况：

```text
新 Metric 组合
新 Dimension 组合
新过滤组合
新产品实体
新机构实体
新表达方式
同义词
复杂 AND / OR / NOT
新营销规则
```

核心指标：

```text
Generalization Accuracy
```

---

## 十三、Multi-turn Benchmark

评测：

```text
Context Retention Accuracy
Plan Patch Accuracy
Filter Replacement Accuracy
Metric Retention Accuracy
Time Range Retention Accuracy
Clarification Follow-up Accuracy
```

例如：

```text
Q1: 2026年Q1南京客户平均资产是多少？
Q2: 只看钻石客户
Q3: 换成苏州
```

---

## 十四、Marketing Benchmark

评测：

```text
Tag Accuracy
Segment Accuracy
Opportunity Accuracy
Strategy Rule Accuracy
Evidence Completeness
Explanation Completeness
Missing Exclusion Accuracy
Time Conflict Detection Accuracy
Rule Coverage
```

建议建立人工复核样本：

```text
20～50 个客户
```

形成：

```text
human_reviewed_marketing.jsonl
```

---

## 十五、Missing Data Benchmark

专项测试：

```text
observed
zero
no_record
unknown
```

重点防止：

```text
None → 0
no_record → zero
unknown → false
```

指标：

```text
Missing State Accuracy
```

---

## 十六、Time Consistency Benchmark

测试：

```text
缺时间
模糊时间
不同时间范围指标组合
快照日期与事实日期冲突
```

指标：

```text
Time Parsing Accuracy
Time Conflict Detection Accuracy
```

---

## 十七、Latency Benchmark

至少统计：

```text
Semantic Parsing Latency
Query Plan Latency
SQL Generation Latency
Guardrail Latency
DB Execution Latency
Marketing Latency
End-to-End Latency
```

输出：

```text
avg
p50
p95
max
```

---

## 十八、Stability Benchmark

关键 Case 建议重复运行 3～5 次。

记录：

```text
Output Stability Rate
```

确定性链路应保持稳定。

---

## 十九、Repair Benchmark

评测：

```text
Repair Trigger Accuracy
Repair Success Rate
Average Repair Count
Max Repair Count
```

必须确保 Repair 不改变业务语义。

---

## 二十、Clarification Benchmark

测试：

```text
缺时间
模糊 Metric
模糊实体
未知 Dimension
未知 Metric
```

指标：

```text
Clarification Precision
Clarification Recall
Clarification Resolution Accuracy
```

---

## 二十一、Coverage

统计：

```text
Metric Coverage
Dimension Coverage
Intent Coverage
Operator Coverage
Entity Coverage
Marketing Rule Coverage
```

---

## 二十二、End-to-End Benchmark

从用户问题到最终答案或 Marketing Result。

核心指标：

```text
End-to-End Success Rate
End-to-End Result Accuracy
End-to-End Hallucination Rate
```

---

## 二十三、Failure Taxonomy

建议统一分类：

```text
SEMANTIC_ERROR
ENTITY_RESOLUTION_ERROR
TIME_PARSE_ERROR
PLAN_ERROR
VALIDATION_ERROR
SQL_GENERATION_ERROR
SCHEMA_GUARD_ERROR
JOIN_ERROR
COST_GUARD_ERROR
EXECUTION_ERROR
RESULT_ERROR
MARKETING_RULE_ERROR
CLARIFICATION_ERROR
CONTEXT_ERROR
UNSUPPORTED_HANDLING_ERROR
```

失败 Case 保存：

```json
{
  "case_id": "",
  "query": "",
  "expected": {},
  "actual": {},
  "failure_type": "",
  "stage": "",
  "trace_id": "",
  "notes": ""
}
```

---

## 二十四、Unified Benchmark Runner

建议支持：

```bash
python scripts/run_benchmark.py
python scripts/run_benchmark.py --suite semantic
python scripts/run_benchmark.py --suite guardrail
python scripts/run_benchmark.py --suite marketing
python scripts/run_benchmark.py --suite all
```

---

## 二十五、Benchmark Report

最终自动生成：

```text
benchmark_report.json
benchmark_report.md
failure_cases.jsonl
```

报告至少包括：

```text
总 Case 数
各 Suite Case 数
各类 Accuracy
Hallucination Rate
Guardrail Block Rate
Generalization Accuracy
Marketing Accuracy
Latency
失败分类
Top Failure Cases
```

---

## 二十六、推荐第一版 Case 数量

建议至少：

```text
Official Seed        7+
Semantic             30
Query Plan           30
Hallucination        20
Guardrail            20
Generalization       30
Multi-turn           10组
Marketing            30
End-to-End           20
```

总量建议：

```text
150～200+ Cases
```

---

## 二十七、Rule Snapshot Regression

Stage 7 规则需要做版本回归。

保存：

```text
rule_version
input
expected_output
```

修改规则后自动显示哪些客户结果发生变化。

---

## 二十八、Trace Benchmark

抽查 Trace 是否包含：

```text
Query Plan
Metric Source
Entity Resolution
Generated SQL
Guardrail Decisions
Result Validation
Marketing Rules
```

指标：

```text
Trace Completeness Rate
```

---

## 二十九、数据脱敏

Benchmark Report 不输出：

```text
真实姓名
手机号
敏感身份信息
```

优先使用：

```text
customer_id
masked values
```

---

## 三十、真实数据库与 Dry-run 必须分开

如果 Stage 6 真实数据库尚未接通：

必须分成：

```text
Dry-run Benchmark
Real-DB Benchmark
```

禁止把：

```text
SQL 生成成功率
```

写成：

```text
真实 SQL 执行准确率
```

---

## 三十一、Stage 8 推荐开发顺序

```text
Stage 8.1 Benchmark Schema
↓
Stage 8.2 Dataset Builder
↓
Stage 8.3 Semantic / Plan Evaluator
↓
Stage 8.4 SQL / Result Evaluator
↓
Stage 8.5 Hallucination / Guardrail Evaluator
↓
Stage 8.6 Generalization / Multi-turn Evaluator
↓
Stage 8.7 Marketing Evaluator
↓
Stage 8.8 Latency / Stability
↓
Stage 8.9 Unified Runner
↓
Stage 8.10 Report Generator
```

---

## 三十二、Stage 8 验收清单

```text
[ ] Benchmark Case Schema 完成
[ ] Official Q&A 仅作为 Seed
[ ] Generalization Dataset 完成
[ ] Hallucination Dataset 完成
[ ] Guardrail Dataset 完成
[ ] Multi-turn Dataset 完成
[ ] Marketing Dataset 完成

[ ] Semantic Evaluator 完成
[ ] Query Plan Evaluator 完成
[ ] SQL Evaluator 完成
[ ] Result Evaluator 完成
[ ] Hallucination Evaluator 完成
[ ] Guardrail Evaluator 完成
[ ] Marketing Evaluator 完成
[ ] Latency Evaluator 完成

[ ] Unified Runner 完成
[ ] Failure Taxonomy 完成
[ ] Failure Cases 自动保存
[ ] Benchmark Report 自动生成
[ ] Dry-run 与 Real-DB 指标分离
[ ] Human Review Set 建立
[ ] Benchmark 数据未泄漏到业务逻辑
```

---

## 三十三、Stage 8 最终指标面板

最终建议至少展示：

```text
Semantic Accuracy
Query Plan Exact Match
SQL Execution Accuracy
Result Accuracy
Semantic Hallucination Rate
Unsupported Handling Accuracy
Guardrail Unsafe Block Rate
Safe Query Pass Rate
Generalization Accuracy
Multi-turn Accuracy
Marketing Rule Accuracy
Explanation Completeness
End-to-End Success Rate
P95 Latency
```

---

## 三十四、Stage 8 完成后的意义

Stage 8 完成后，系统不再只是“功能能运行”，而是能够用数据回答：

```text
Agent 有多准？
有多稳？
能泛化到什么程度？
幻觉率是多少？
安全机制能拦住多少错误？
营销判断是否可复核？
```

下一阶段：

```text
Stage 9 — Frontend
```

前端届时重点展示：

```text
Chat
Query Plan
SQL Guardrail
Trace
Customer 360
Segment
Opportunity
Strategy
Benchmark Dashboard
```
