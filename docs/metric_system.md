# Agentic 客户经营智能问数指标体系

## 1. 指标体系设计目标

本指标体系用于 Agentic 客户经营智能问数场景。

目标不是简单罗列业务指标，而是建立一套可被后续 Query Plan、Agent、
Guardrail 和 Benchmark 直接读取和使用的标准指标定义。

对于用户提出的自然语言问题，例如：

> 查询 2026 年 Q1 日均资产超过 30 万、股票交易额超过 10 万的客户

系统不应临时猜测“日均资产”“股票交易额”的计算方式，
而应从标准指标体系中读取：

- 指标定义
- 来源表
- 来源字段
- 聚合规则
- 时间口径
- 产品分类条件
- NULL 处理规则
- 指标别名

然后再生成查询计划和 SQL。

---

## 2. 指标体系整体结构

当前指标体系由以下 Metadata 文件共同组成：

```text
metadata/
├─ metric_domains.yaml
├─ dimensions.yaml
├─ metrics.yaml
├─ metric_aliases.yaml
└─ metric_constraints.yaml