# Stage 5 Agent 人工验收 CLI

在项目根目录 `D:\agentic_marketing` 执行：

```powershell
python scripts/run_agent_demo.py
```

启动后直接输入自然语言问题。每轮会打印格式化 JSON，包括检索结果、实体解析、Query Plan、Stage 4 校验结果、澄清、修复次数和完整 trace。

CLI 会在同一次运行中保留上一轮 Query Plan 和 conversation context，可连续输入例如：

```text
南京客户数量
改为苏州
```

输入 `exit` 或 `quit` 退出。脚本只调用现有 `AgentOrchestrator`，不生成 SQL，也不会绕过 Stage 4 Validator。
