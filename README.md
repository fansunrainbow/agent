# Agentic Marketing：可信智能问数与营销智能体

面向证券营销分析场景的可信数据智能体。系统将自然语言问题转换为经过业务语义约束、结构化验证和安全围栏审查的只读查询，并可将安全结果继续用于客户画像、圈客、营销机会和策略生成。

> 本项目不是直接 NL2SQL。模型不能跳过业务口径、Query Plan 或 Guardrail 直接访问数据库。

## 核心链路

```text
Natural Language
  → Semantic Grounding
  → Structured Query Plan
  → Plan Validation
  → Deterministic SQL Compiler
  → Guardrail + EXPLAIN
  → Read-only Real DB
  → Result Validator
  → Customer 360 / Marketing Capability
```

核心设计目标：

- 普适化：指标、维度、枚举、关系和规则由 Metadata 驱动，不为 Benchmark Case 写特判。
- 低幻觉：未知指标、实体、时间或关系优先 clarification、unsupported 或 fail closed。
- 可解释：Query Plan、SQL、参数、Guardrail、结果和 Trace 均可检查。
- 安全：真实数据库账号仅有 SELECT 权限；所有 SQL 参数化并经过 Schema、Join、Security、Cost 与 Result Guard。

## 系统组成

| 模块 | 作用 |
|---|---|
| `metadata/` | 指标、维度、业务词典、实体关系与枚举映射 |
| `agent/` | 语义归一、实体解析、规划、工具路由与多轮 Patch |
| `query_plan/` | 结构化 Query Plan Schema 与模型 |
| `guardrail/` | 确定性 SQL 编译、AST、Schema/Join/Cost/Security/Result Guard |
| `database/` | MySQL 只读连接、参数执行、EXPLAIN 与超时控制 |
| `marketing/` | 标签、圈客、机会、策略与事实/规则/建议分层 |
| `benchmark/` | Dry-run 评测、Frozen Real DB Gold 与正式报告 |
| `webapp/` | FastAPI 服务与真实执行编排 |
| `frontend/` | React + Vite 演示界面 |

完整架构见 [docs/system_architecture.md](docs/system_architecture.md)。

## 环境要求

- Python 3.11+
- Node.js 20+ 与 npm
- MySQL 8.x（真实执行模式）
- Windows PowerShell 示例命令；其他终端可使用等价命令

## 安装

```powershell
python -m pip install -r requirements.txt -c constraints.txt
Set-Location frontend
npm ci
Set-Location ..
```

## 数据库与 `.env`

真实执行必须使用只读账号。复制模板并在本机填写，禁止提交 `.env`：

```powershell
Copy-Item .env.example .env
```

```dotenv
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=agentic_marketing
DB_USER=agent_readonly_user
DB_PASSWORD=<local-secret>
DB_CONNECT_TIMEOUT=5
DB_QUERY_TIMEOUT=30
```

账号创建与权限核验见 [docs/mysql_readonly_setup.md](docs/mysql_readonly_setup.md)。`.env` 已列入 `.gitignore`。

四个客户事实 CSV 属于受控比赛数据，不随提交包二次分发。需要重建 Real DB 时，请从获批的数据渠道取得文件，放到项目根目录，并运行：

GitHub 代码仓库还排除实体 CSV、真实数据库 Gold、评测结果和生成的 `submission/` 目录。运行真实数据库流程前，请从获批的数据渠道取得所需数据；项目代码、配置模板、测试及普通评测用例可直接从仓库获取。

```powershell
python scripts/verify_external_data.py
```

文件名、大小和 SHA-256 记录在 `EXTERNAL_DATA_REQUIREMENTS.json`；完整建库与导入流程见 [docs/database_rebuild.md](docs/database_rebuild.md)。

## 启动 Backend 与演示站点

生产演示方式（Backend 同时托管 `frontend/dist`）：

```powershell
Set-Location frontend
npm run build
Set-Location ..
python scripts/run_web.py --host 127.0.0.1 --port 8000
```

打开 `http://127.0.0.1:8000`。数据库变量完整时页面显示 `REAL_DB`；否则明确显示 `DEMO / DRY RUN`，不会用 fixture 冒充真实结果。

当前 Web API 是本机比赛演示入口，不包含用户认证。启动脚本默认只绑定回环地址；绑定非回环地址必须显式增加 `--allow-remote`，且在接入认证、授权与 TLS 前不得部署到内网或公网。

前端开发模式：

```powershell
Set-Location frontend
npm run dev
```

## CLI

```powershell
python scripts/run_agent_real.py "南京客户有多少？" --dry-run
python scripts/run_agent_real.py "南京客户有多少？" --execute
```

`--execute` 仍完整经过 Agent、Validator、SQL Compiler、Guardrail、EXPLAIN 和 Result Validator，不提供 raw SQL 执行入口。

## Benchmark

Dry-run Benchmark 与 Real DB Benchmark 是两套不同评测：

```powershell
# Stage 8 Dry-run suites
python scripts/run_benchmark.py

# 正式 Frozen Real DB Benchmark（需要只读数据库；会执行全部 40 条）
python scripts/run_real_db_benchmark.py
```

当前冻结结果：First Frozen `18/40 (45.00%)`，通用修复后的 Second Frozen `36/40 (90.00%)`。Gold SHA-256 为 `602496D8308DD391F4184F2A63A256E6942AF21F3FE3A1D6111987B3EAEB4FCD`，未为提高分数修改 Gold。详见 [docs/final_benchmark_summary.md](docs/final_benchmark_summary.md)。

## 一键发布完整性检查

不会重新运行 Real DB Benchmark：

```powershell
python scripts/final_verify.py
```

该命令检查 Backend 导入、Metadata、词典、Query Plan、Guardrail dry-run、Python 测试、Frontend 测试与构建、Frozen Gold 哈希及正式报告。

## 3–5 分钟 Demo

按 [docs/demo_script.md](docs/demo_script.md) 操作，确保页面为 `REAL_DB`。推荐展示：简单问数、时间指标、复杂圈客、产品类别、Top-K、多轮修改、Customer 360、营销建议及完整 Trace。

## 正式验收

- Gold Integrity：PASS
- SQL Execution Success：36/40（90.00%）
- Final Execution Accuracy：36/40（90.00%）
- Python：241/241 PASS
- Frontend：14/14 PASS；Build PASS
- Frontend REAL_DB E2E：PASS
- `AGENT_FINAL_READY = YES`

最终状态见 [docs/final_system_acceptance_report.md](docs/final_system_acceptance_report.md)。

重新生成提交包时使用：

```powershell
python scripts/build_submission_package.py --replace
python scripts/final_verify.py
```

提交包清单包含逐文件 SHA-256 和稳定内容摘要；根目录 pytest 已明确排除 `submission/`，因此生成提交包后仍可重复执行完整回归。
