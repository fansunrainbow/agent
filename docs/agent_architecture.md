# Stage 5 Agent Core 架构

## 边界

Agent Core 将自然语言转换为经 Stage 4 校验的 Query Plan。它不生成 SQL、不执行查询，也不替代 Stage 6 的 SQL 安全与执行防护。

## 主流程

`AgentOrchestrator` 使用显式状态机串联以下步骤：

1. `SemanticRetriever` 从指标、维度、业务词典和歧义规则中检索候选。
2. `EntityResolver` 依据 `entity_rules.yaml` 和真实 CSV 动态解析产品、机构、客户等实体。
3. `ToolRouter` 根据已检索的语义类型选择确定性工具。
4. `Planner` 生成符合 Stage 4 Pydantic/JSON Schema 的 Query Plan；默认离线确定性运行，可注入结构化 LLM Provider。
5. `validate_plan_data` 强制执行 Stage 4 结构、注册表、能力、时间、实体、置信度校验。
6. `RepairEngine` 仅做注册表支持的规范化，最多两次；未知业务语义不得自动修复。
7. `ClarificationEngine` 把歧义或不可修复错误转换为精确问题。
8. `AgentState.trace` 和可选 JSONL 审计日志保留来源、决策与延迟。

## 低幻觉约束

- 计划中的指标、维度、概念、操作符必须来自 Stage 1～4 注册表。
- 高基数实体必须来自配置的数据源；同名多候选必须澄清。
- 必需时间缺失、口径多义、未知语义均进入澄清，不得猜测。
- LLM 只能看到检索后的候选与正式 Schema，输出仍必须通过同一个 Stage 4 校验器。
- 规则和语言提示放在 Metadata 中，Planner 不包含具体产品名称或机构名称分支。

## 扩展点

- 通过实现 `StructuredLLMProvider` 接入线上模型。
- 通过扩展 Stage 1～4 Metadata 增加指标、维度、概念或实体类型。
- 通过 `JsonlAuditLogger` 接入生产审计管道。
- Stage 6 可消费 `status=ready` 且 `validation_result.valid=true` 的计划。
