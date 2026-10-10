# Stage 4 Generic Query Plan 完成与验收报告

## 结论

Stage 4 已完成教程规定的 Query Plan 结构、注册表、归一化、双层校验、低幻觉围栏、示例和自动化测试。当前实现不调用大模型，不生成最终 SQL，也未引入针对官方 Q&A 的特殊分支。

## 本次补齐内容

- 新增 `metadata/query_plan_confidence.yaml`，将执行阈值、澄清阈值和关键组件配置化。
- 新增 `query_plan/models.py`，提供与 JSON Schema 对应的 Pydantic v2 类型边界。
- 新增实体查询标准示例 `query_plan/examples/entity_query.json`。
- 增强 Structural Validator，对未知 Intent、未知 Operator、非法时间、非法 Filter 和非法 Limit 返回稳定错误码。
- 增强 Semantic Validator，实际执行 Intent 能力矩阵与 Subject 校验，而非只检查配置文件是否存在。
- 增加 Metric 必需时间范围校验；缺少期间的资产变化问题改为显式澄清。
- 增加日期区间起止顺序校验。
- 增加 Metric 与 Dimension 兼容性校验，只接受指标源表、派生指标依赖和已验证 Join 路径能够支持的组合，并阻止通过无关事实表绕行。
- 增加 Operator 值形状校验，包括 scalar、list、range 和 none。
- 增加 Entity Filter 与已解析实体 ID、实体类型的一致性校验。
- 增加业务默认和假设来源审计。
- 将 Ready Plan 的整体置信度执行门槛统一为 0.85，并校验关键组件、单个 Filter 和已解析 Entity 的置信度。
- 修复中文 Windows 控制台因 Unicode 状态符号导致脚本崩溃的问题。
- 新增依赖清单和可直接执行的验收命令。

## 验收结果

| 验收项 | 结果 |
|---|---:|
| YAML 与 Stage 3 词典校验 | 通过 |
| 标准 Query Plan 示例 | 8 个全部通过 |
| 数据驱动 Query Plan 测试 | 132 通过，0 失败 |
| 聚焦 Validator 与 Normalizer 单元测试 | 12 通过，0 失败 |
| Intent 覆盖率 | 100% |
| Metric 覆盖率 | 100% |
| Dimension 覆盖率 | 100% |
| Python 编译检查 | 通过 |

## 教程验收清单映射

- Registry：Intent、Operator、Time、Capability、Confidence 均已建立。
- Schema：Query Plan、Filter、Time Range、Entity Reference 均已建立并使用 Draft 2020-12。
- 表达能力：客户筛选、指标查询、分组、趋势、排名、对比、AND、OR、NOT、排序、Top-K、时间范围和多轮 Context 均有结构或测试覆盖。
- Fail Closed：未知指标、维度、概念、操作符、实体、非法时间、能力越界、组合不兼容、低置信度和未审计假设均会被拦截。
- 通用性：测试覆盖简单、中等、复杂、模糊、实体、多轮、覆盖补充和幻觉诱导场景；官方 Q&A 仅作为回归样本。

## Stage 4 之外的后续工作

以下内容不属于本阶段，尚未实现：自然语言到 Query Plan 的模型生成、真实在线 Entity Resolver 服务、Logical/Physical Plan、SQL Generator、数据库执行围栏、端到端执行准确率与时延评测。这些应在 Stage 5 及后续阶段基于当前已验证的 Query Plan 合同继续实现。

