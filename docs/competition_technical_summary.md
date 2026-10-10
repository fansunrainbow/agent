# Competition Technical Summary

## 一、项目背景

证券营销问数同时涉及自然语言歧义、复杂指标口径、多事实表粒度、客户隐私和数据库安全。项目目标不是生成“看起来合理”的 SQL，而是构建可验证、可解释、可安全执行的智能体链路。

## 二、Agent 总体架构

系统采用 Natural Language → Semantic Grounding → Query Plan → Validation → Deterministic SQL → Guardrail → Real DB → Result Validation → Marketing 的分层架构。每层有独立输入输出和失败语义。

## 三、AI-Friendly Metadata

Metadata 将表、字段、粒度、时间、关联路径、指标和枚举组织为机器可检索、可验证的契约。Agent 使用稳定 ID，而非从问题中猜测物理字段。

## 四、指标体系

指标合同定义来源、表达式、聚合、grain、时间语义、空值策略和约束。系统区分流量、快照、自然日日均、实际快照均值、期初/期末和派生比例。

## 五、业务词典与语义解析

业务词典管理概念扩展和同义表达；统一值链路将“女/F/female”等输入归一为 canonical value，再映射为真实数据库 code。实体必须从受控数据解析，歧义时要求澄清。

## 六、Query Plan

Query Plan 显式记录 intent、subject、metrics、dimensions、filters、entities、time、grouping、HAVING、ranking、limit 和 output shape。它是业务语义与 SQL 的审计边界。

## 七、Agent 规划与工具调用

Agent 依次调用 Registry、Metric、Dimension、Entity、Schema 和 Join 工具。多轮对话通过结构化 Patch 修改已有 Plan，保留未被替换的时间和指标，并对静默忽略 fail closed。

## 八、安全围栏

参数化 SQL 经过 Security、Schema、Join、Cost、EXPLAIN、timeout 和 Result Validator。真实账号只有 SELECT 权限。系统没有 raw SQL 浏览器接口，高成本计划不会因演示或分数被强制执行。

## 九、营销能力

Stage 7 从安全结果构建客户特征，执行标签、圈客、机会和策略规则。输出严格区分 FACT、RULE_DECISION 和 SUGGESTION，并保留证据与解释。

## 十、Benchmark 评测体系

Dry-run Frozen Benchmark 覆盖语义、Plan、SQL、Guardrail、营销、多轮、幻觉和稳定性；Real DB Frozen Benchmark 使用 40 条人工审核 Gold，进行完整只读数据库结果等价比较。

## 十一、Real DB 实验结果

First Frozen 为 18/40（45.00%）。经过通用能力修复，Second Frozen 达到 36/40（90.00%），SQL 执行成功 36/40。Scalar、Ranking、Time Series 分别为 100%；无 PASS→FAIL regression。Gold SHA-256 始终不变。

## 十二、低幻觉机制

系统通过 Metadata 白名单、实体检索、Grounded Conditions、Query Plan Validator、确定性编译、Schema/Join Guard 和结果验证控制表、列、指标、实体、时间、关系与结果幻觉。无证据时 clarification 或 fail closed。

## 十三、普适化设计

核心逻辑由注册表和合同驱动：枚举归一、聚合形态、HAVING、时间桶、期末日期、EXISTS、Ranking tie-breaker、结果归一与数据集加载均为通用能力，不包含 Case ID 特判。

## 十四、系统局限性

Second Frozen 仍有四条 COST_BLOCK：RDB_M06、RDB_M07、RDB_C01、RDB_C11。它们仍是失败，不能宣称结果正确。Set 与 Grouped 类型准确率分别为 72.73% 和 83.33%，复杂关联查询仍有进一步优化空间。

## 十五、未来工作

- 在不放宽安全阈值的前提下，引入物化语义层、统计信息与更多预聚合策略。
- 扩展跨周期比较和更多事实粒度的统一规划。
- 建立 CI 中的发布完整性、敏感信息和报告一致性门禁。
- 增加更多真实业务分布、并发与长期漂移评测。
