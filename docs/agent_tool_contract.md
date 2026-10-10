# Agent 工具契约

所有确定性工具统一返回 `ToolResult`：

- `success`: 调用是否成功。
- `data`: 结构化结果；失败时可为空。
- `source`: Metadata 文件或实体数据文件来源。
- `confidence`: 0～1 的工具级置信度。
- `error_code` / `error_message`: 稳定错误码和说明。

## 工具清单

| 工具 | 职责 | 主要来源 |
|---|---|---|
| `MetricTool` | 指标查找、别名匹配、约束返回 | `metrics.yaml`、`metric_aliases.yaml`、`metric_constraints.yaml` |
| `DimensionTool` | 维度和枚举/城市值匹配 | `dimensions.yaml`、`value_mappings.yaml`、源表 CSV |
| `DictionaryTool` | 业务概念与歧义规则检索 | `business_dictionary.yaml`、`ambiguity_rules.yaml` |
| `SchemaTool` | 表和字段元数据查询 | `tables.yaml` |
| `RegistryTool` | 注册 ID 枚举和存在性检查 | Stage 1～4 注册表 |
| `JoinTool` | 已验证连接路径搜索，拒绝多事实表危险路径 | `joins.yaml` |
| `EntityTool` | 精确优先、模糊受控的动态实体解析 | `entity_rules.yaml`、真实 CSV |

工具不生成 SQL，不把模糊匹配当成确定事实，也不返回没有来源的业务 ID。
