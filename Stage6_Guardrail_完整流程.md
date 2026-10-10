# Stage 6 — Guardrail（执行安全与结果可信层）

## 目标

Stage 5 已完成：

自然语言 → Semantic Grounding → Query Plan → Validator

Stage 6 扩展为：

Validated Query Plan
→ SQL Generation
→ SQL Guard
→ Safe Execution
→ Result Validation

核心目标：

1. 普适化：不针对固定 Q&A 编写 SQL 规则。
2. 低幻觉：防止错误 Query Plan、错误 SQL、危险执行进入数据库。

---

# 一、整体架构

```
User
 ↓
Stage 5 Agent Core
 ↓
Validated Query Plan
 ↓
Logical Query Planner
 ↓
SQL Generator
 ↓
SQL Validator
 ↓
Schema Guard
 ↓
Security Guard
 ↓
Cost Guard
 ↓
Database
 ↓
Result Validator
 ↓
Response
```

---

# 二、目录建议

```
guardrail/

├── sql_generator.py
├── sql_validator.py
├── schema_guard.py
├── security_guard.py
├── cost_guard.py
├── result_validator.py
├── execution_manager.py

├── parser/
│   └── sql_ast.py

├── policies/
│   ├── sql_policy.yaml
│   ├── schema_policy.yaml
│   ├── cost_policy.yaml
│   └── result_policy.yaml

└── tests/
```

---

# 三、SQL Generator

职责：

Validated Query Plan → SQL

禁止：

User Query → LLM → SQL

SQL 只能来自：

- 已验证 Metric
- 已验证 Dimension
- 已验证 Entity
- 已验证 Join
- 已验证 Filter

禁止模型自由创造：

- 表
- 字段
- JOIN
- WHERE 条件

---

# 四、Schema Guard

检查：

- 表是否存在
- 字段是否存在
- 字段是否属于该表
- Join 是否来自合法 Join Map
- 聚合是否合理

不存在字段：

必须拒绝。

---

# 五、SQL Security Guard

默认只允许：

```
SELECT
WITH
```

禁止：

```
DROP
DELETE
UPDATE
INSERT
ALTER
TRUNCATE
CREATE
```

---

# 六、参数化查询

禁止：

```python
sql = "select * from customer where id=" + user_input
```

必须：

```python
execute(
    sql,
    params
)
```

避免 SQL Injection。

---

# 七、SQL AST 检查

流程：

```
SQL
↓
Parser
↓
AST
↓
Rule Check
```

检查：

- statement type
- tables
- columns
- joins
- functions
- predicates

---

# 八、Join Guard

防止错误 JOIN 导致数据膨胀。

检查：

- Join Key 是否来自 Metadata
- Join Cardinality
- 是否产生重复
- 是否需要 DISTINCT

---

# 九、Cost Guard

检查：

- SELECT *
- 大表无时间条件
- 扫描规模
- 返回数量
- 执行时间

策略配置化：

```yaml
max_rows: 100000
max_time: 30s
require_partition_filter: true
```

---

# 十、Read Only Execution

数据库建议创建：

```
agent_readonly_user
```

只授予：

```
SELECT
```

权限。

---

# 十一、Result Validator

检查：

- 空结果异常
- 数值异常
- 重复放大
- 指标逻辑异常

例如：

客户数必须考虑去重。

---

# 十二、错误处理

禁止：

SQL 出错后让 LLM 自由重新生成。

流程：

```
SQL Error
↓
Error Classification
↓
Controlled Repair
↓
重新 Validator
```

错误类型：

```
UNKNOWN_COLUMN
UNKNOWN_TABLE
INVALID_JOIN
SYNTAX_ERROR
TIMEOUT
COST_LIMIT
RESULT_ANOMALY
```

---

# 十三、测试

必须包含：

## SQL 安全测试

危险 SQL：

必须拒绝。

## Schema 幻觉测试

不存在字段：

必须拒绝。

## Join 测试

非法 Join：

必须拒绝。

## Cost 测试

大表无条件查询：

必须拦截。

## Result 测试

异常结果：

必须标记。

---

# 十四、开发顺序

Stage 6.1

建立：
- Logical Query Planner
- SQL Generator

↓

Stage 6.2

建立：
- SQL AST Parser
- Schema Guard

↓

Stage 6.3

建立：
- Security Guard
- Read Only Policy

↓

Stage 6.4

建立：
- Cost Guard

↓

Stage 6.5

建立：
- Execution Manager

↓

Stage 6.6

建立：
- Result Validator

↓

Stage 6.7

测试与 Benchmark

---

# 十五、Codex 执行要求

1. 不破坏 Stage 1～5。
2. SQL Generator 只能接受 Valid Query Plan。
3. LLM 不直接输出执行 SQL。
4. 所有 SQL 必须经过 Guardrail。
5. 未知字段必须拒绝。
6. 未知表必须拒绝。
7. 未知 Join 必须拒绝。
8. 默认只读执行。
9. 不针对官方 Q&A 写特殊逻辑。
10. 所有规则配置化。

---

# 十六、验收标准

```
[ ] Query Plan 可以生成 SQL

[ ] SQL 只能来自 Valid Query Plan

[ ] Schema Guard 完成

[ ] SQL AST 检查完成

[ ] 危险 SQL 被拒绝

[ ] 参数化查询完成

[ ] Join 风险检测完成

[ ] Cost Guard 完成

[ ] Read-only 执行完成

[ ] Result Validator 完成

[ ] SQL 错误不会无限自由生成

[ ] Trace 完整

[ ] 安全测试通过
```

最终目标：

Stage 5 防止 Agent 理解错误。

Stage 6 防止错误进入数据库造成执行风险。
