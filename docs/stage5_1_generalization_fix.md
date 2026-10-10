# Stage 5.1 — Generalization Fix

## 修改范围

本次只修正 Stage 5 的语义 Grounding、候选剪枝、Planner 输入约束和多轮 Plan Patch；Stage 4 Query Plan Schema、Validator 主体以及 SQL 边界保持不变。

## 核心变化

- 新增 `GroundedCondition`，逐条件保存原文、类型、目标、操作符、值、来源和置信度。
- `ConditionGrounder` 先拆分条件，再按 Metric、Dimension、Concept、Time 等类型查询对应注册表。
- 精确/长别名优先，重叠短指标被剪枝；冲突别名进入澄清，不再任意选择。
- 产品类别限定可作为 Metric 的 scoped evidence，但不会误建 Product Entity 或无条件扩散到全局计划。
- Planner 仅消费 resolved Grounded Conditions；Orchestrator 会拒绝 Provider 新增的未 Ground 语义。
- Patch Engine 支持 ADD/REMOVE/REPLACE Filter 和 Metric，以及修改时间、排序、Limit。
- 多轮合并后统一重新编号 Filter ID。
- Unknown Metric / Dimension 返回未支持原因及注册表替代选项。
- “比较活跃”等修饰词不会触发 comparison Intent。

## 验证

- Stage 4 数据驱动回归：132/132。
- Stage 5 pytest：38/38。
- 新增复杂四条件、双 Metric、Metric + Product Category、Unknown Dimension 精确澄清、三轮 Patch 和未 Ground Provider 输出测试。
