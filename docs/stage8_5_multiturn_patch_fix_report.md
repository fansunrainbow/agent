# Stage 8.5 — Multi-turn Patch Fix 报告

## 1. 新增/修改文件

- 新增 `agent/models/plan_patch.py`：显式 Patch operation 与 `PlanPatch` 数据模型。
- 修改 `agent/models/__init__.py`：导出 Patch 模型。
- 重构 `agent/services/context_manager.py`：生成、应用、审计结构化 Patch。
- 修改 `agent/planner.py`：Patch 优先、显式 target、New Task reset、Patch audit。
- 修改 `agent/orchestrator.py`：继承时间参考年、Patch 后校验、状态回写、Trace。
- 修改 `tests/agent/test_stage51_generalization.py`：同步完整 operation 集合。
- 新增 `tests/agent/test_stage85_multiturn_patch.py`：33 个专项测试。
- 新增 `benchmark/reports/stage8_5_multiturn_fix/`：multi_turn、end_to_end、all 与 operation metrics 报告。

未修改 Stage 8.2 Semantic Grounding 核心、Stage 8.3 Canonicalizer、Stage 8.4 SQL Compiler、Benchmark cases/expected、Guardrail 或 Marketing Rules。

## 2. Patch Model

`PlanPatch` 明确保存 `operation`、`target`、`old_value`、`new_value` 和 `source`。规划器不再默认根据历史文本重建完整计划；存在 parent plan 时，先生成结构化 Patch，再对 parent plan 做最小变更。

## 3. 支持的 operation

- Filter：`ADD_FILTER`、`REMOVE_FILTER`、`REPLACE_FILTER`
- Metric：`ADD_METRIC`、`REMOVE_METRIC`、`REPLACE_METRIC`
- Time：`CHANGE_TIME_RANGE`、`REMOVE_TIME_RANGE`
- Order：`CHANGE_ORDER`、`REMOVE_ORDER`
- Limit：`CHANGE_LIMIT`、`REMOVE_LIMIT`
- Dimension：`ADD_DIMENSION`、`REMOVE_DIMENSION`、`REPLACE_DIMENSION`

Filter 操作按 semantic target 定位，并递归处理 AND/OR/NOT 嵌套节点。

## 4. Context Retention 策略

Patch Engine 先深拷贝 parent plan，再只改 operation 指定字段。未修改的 subject、metrics、dimensions、filters、entities、time_range、group_by、having、order_by、limit 全部保留。实体按类型合并，Filter ID 在最终计划阶段统一重排。

## 5. Status Recompute 方式

每次 Patch 后重新检查：遗留 ambiguity 是否已解决、指标是否为空、指标是否要求时间、冲突引用是否存在。之后运行 Stage 4 validator；校验失败会把计划状态回写为 `needs_clarification`。澄清全部解决时，状态和组件置信度同步恢复为 ready/1.0。

## 6. Time Patch 方式

时间表达仍由 Stage 8.2 的统一 `TimeParser` 解析。多轮层仅从 parent plan 提取可靠年份并作为 reference date 传入，因此“改成 Q2 / 换成 3 月”可以继承上一轮年份；Patch Engine 不另写时间解析器，且新时间完整替换旧时间。

## 7. Clarification Follow-up 处理

parent plan 的未解决 ambiguity 默认保留；当补充字段满足对应要求时才移除。例如缺少统计时间的日均资产计划，在补充 `2026年Q1` 后保留原指标与过滤条件，重新校验并进入 ready。Unsupported ambiguity 不会因无关的城市补充而消失。

## 8. 新增测试

新增 33 个 Stage 8.5 测试，覆盖 15 类 operation、嵌套 Filter、status 双向重算、KEEP、歧义引用、unsupported follow-up、冲突检测、New Task reset 与审计字段。其中包含 5 组三轮对话和 2 组五轮对话。结果：`33/33 passed`。

## 9. 全量回归

- 全量 pytest：`185/185 passed`
- Semantic：`25/30`，83.33%
- SQL Compiler：`14/15`，93.33%
- Guardrail：`20/20`
- Hallucination：`20/20`
- Marketing：`32/32`
- Result：`12/12`

## 10. Multi-turn Before / After

| 指标 | Before | After |
|---|---:|---:|
| Multi-turn Accuracy | 50% (5/10) | 80% (8/10) |
| ADD proxy | 75% (3/4) | 75% (3/4) |
| REMOVE proxy | 0% (0/1) | 100% (1/1) |
| REPLACE proxy | 80% (4/5) | 80% (4/5) |
| CHANGE_TIME | 0% (0/1) | 100% (1/1) |
| CHANGE_ORDER | 无直接基准例 | 100%（3/3 专项路径） |
| CHANGE_LIMIT | 0% (0/1) | 100% (1/1) |
| Context Retention proxy | 96.67% | 100% |
| Clarification/Status proxy | 70% | 100% |
| Filter Patch | 80% | 80% |
| Metric Retention | 100% | 100% |
| Time Retention | 90% | 100% |
| Output Stability | 100% | 100% |

Operation proxy 按未修改的 10 个 multi_turn case 分组；ADD/REPLACE 的残留失败是枚举值口径差异，不是 operation 未执行。

## 11. End-to-End Before / After

End-to-End dry-run 保持 `85% (17/20)`。全量 Benchmark 从 `166/226` 提升到 `169/226`，失败数从 `60` 降到 `57`。

## 12. 剩余 Multi-turn Root Cause

- `MT_002`：计划正确新增 gender filter，但当前受控元数据输出“女”，Benchmark expected 为 `F`。
- `MT_009`：city 已正确从南京替换为苏州；“普通客户”未在当前 customer_level 词典中注册，系统安全保留原钻石等级，而 Benchmark expected 为 `1000003`（当前词典中该值对应“金卡客户”）。

两例的 metric、time、status、stability 均正确，单例得分均为 0.8。修复它们需要在后续阶段统一枚举/词典口径，不能在 Patch Engine 中做 case-specific 猜测。

## 13. Regression

未发现回归。Guardrail、Hallucination、Marketing、SQL Compiler、End-to-End 均与 Stage 8.4 持平；全量通过数增加 3。Patch audit 包含 parent_plan_id、operation/target、old/new value、result_plan、validation_result、status before/after。

## 14. 是否可以进入 Stage 8.6

可以。Stage 8.5 成功标准已满足：REMOVE 正确执行，REPLACE 按 semantic target 定位，CHANGE_TIME/ORDER/LIMIT 可用，Patch 后状态重算，未修改字段保留，且未重新引入 hallucination。Stage 8.6 应优先处理枚举编码与业务词典对齐，而不是继续向 Patch Engine 添加特例。
