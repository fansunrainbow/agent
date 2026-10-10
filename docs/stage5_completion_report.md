# Stage 5 完成报告

## 已完成

- AgentState、统一 ToolResult、PlannerResult 和 ClarificationResult。
- 指标、维度、词典、Schema、注册表、Join、实体等确定性工具。
- 基于真实 Stage 1～4 Metadata 的语义检索与工具路由。
- 默认离线确定性 Planner，以及可注入的结构化 LLM Provider 抽象。
- 强制 Stage 4 校验、最多两次确定性修复、精确澄清与不支持分流。
- 动态实体解析、多轮 Query Plan patch、结构化 trace、脱敏 JSONL 审计日志。
- 人工验收 CLI：`python scripts/run_agent_demo.py`，支持循环输入和会话上下文保留。
- 简单、复杂、歧义、实体、上下文、修复、Provider 防绕过、幻觉率测试。

## 验证结果

- Stage 5 / pytest：38 通过，0 失败（含 Stage 5.1 泛化修复回归）。
- Stage 4 数据驱动回归：132 通过，0 失败。
- Metadata YAML：全部解析通过。
- Python 源码：`compileall` 通过。
- 基准用例中的未注册语义输出：0，语义幻觉率：0.0。

## 普适化与低幻觉结论

Planner 未写死产品名、机构名或数据中的业务实体。新增产品只要进入受控源表即可被解析；同名、缺失或低置信度实体不会被自动选中。所有计划无论由确定性 Planner 还是 LLM Provider 产生，都必须经过同一 Stage 4 校验入口。

## 当前限制

- 中文解析器采用可审计的配置化短语/正则与受控模糊匹配，不等同于完整语法解析器。
- 大产品表首次载入和实体扫描存在冷启动成本；生产环境应替换为带索引的实体检索服务。
- 当前 Provider 是接口与离线静态实现；线上模型的鉴权、重试、配额和观测需要部署环境配置。
- 澄清答案的交互式回填目前通过 `conversation_context` / previous plan 完成，尚未提供前端会话协议。

## Stage 6 必须继续处理

- 仅接收 `ready` 且校验通过的 Query Plan。
- 生成参数化 SQL，实施表/字段白名单、Join 约束、行数与成本限制。
- 执行前静态检查、只读权限、超时、审计、敏感字段脱敏和结果级权限控制。
- 对执行错误进行安全分类，不得把数据库错误直接交给模型自由改写 SQL。
