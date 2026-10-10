# Real DB Gate Hotfix：parent_branch Relation Mapping

日期：2026-10-06

## 结论

`parent_branch` SQL 执行映射已完成，目标真实数据库用例 `SMOKE_06` 全链路通过并返回 5 位客户。完整 Smoke Test 随后在与本轮修复无关的 `SMOKE_07 stock_product` 概念展开处失败，因此当前结论仍为：

- `REAL_DB_GATE = FAIL`
- `AGENT_FINAL_READY = NO`
- 不可进入 Real DB Benchmark

## 1. parent_branch 的真实语义

`parent_branch` 表示“当前客户所属机构的上级机构/分公司”。它不是推导出的自由文本关系，而是 `dim_branch` 中已存在的层级字段：

- 上级机构 ID：`up_org_id`
- 上级机构名称：`up_org_name`

语义链路为：

`Natural Language → parent_branch dimension hint + entity resolution → entity filter(parent_branch) → Relation Registry → verified join → parent_branch dimension projection → parameterized SQL`

修复前缺失的具体环节是 `entity filter(parent_branch) → SQL relation mapping`。

## 2. 使用的真实表和字段

- 客户表：`ads_cust_info_d`
  - 客户键：`pty_id`
  - 所属机构键：`org_id`
- 机构维表：`dim_branch`
  - 机构键：`org_id`
  - 上级机构键：`up_org_id`
  - 上级机构名称：`up_org_name`

真实库核验结果：

- `dim_branch`：312 行，312 个唯一 `org_id`
- Join 前客户表：500 行，500 个唯一 `pty_id`
- Join 后：500 行，500 个唯一 `pty_id`

## 3. Join Path

复用 `joins.yaml` 中已验证的 `branch_to_customer`：

`ads_cust_info_d.org_id = dim_branch.org_id`

然后从同一条 `dim_branch` 记录读取 `up_org_id`。SQL Generator 不包含针对 `parent_branch` 或具体查询文本的特殊 Join；维表直连路径由 Metadata Catalog 和 verified join 通用解析。

## 4. Relation Registry

新增 `metadata/entity_relations.yaml`，统一注册：

- `held_product`
- `traded_product`
- `product`
- `branch`
- `parent_branch`

每条关系声明来源/目标实体、来源/目标表、关系类型、实体字段、verified join、cardinality、grain strategy 和 enabled 状态。Logical Planner 仅接受已启用且绑定 verified join 的关系；未知、禁用或路径不一致的关系均 fail-closed。

此外，同一表面词同时命中 `branch` 与 `parent_branch` 时，Entity Resolver 使用已落地的 dimension 类型证据进行通用消歧。`北京分公司` 最终只保留 `parent_branch`，没有基于该查询文本写特例。

## 5. Grain Safety

不存在 grain amplification：

- 客户到机构为 many-to-one
- `dim_branch.org_id` 在真实库唯一
- Join 前后客户行数与唯一客户数均为 500
- 生成 SQL 的客户基表使用 `SELECT DISTINCT pty_id`
- `customer_count` 继续使用 `COUNT(DISTINCT pty_id)`

Planner 会拒绝未声明安全策略的关系并返回 `RELATION_GRAIN_AMPLIFICATION`。一对多实体关系继续使用 correlated `EXISTS`，不直接放大客户粒度。

## 6. Targeted Real DB Test

`SMOKE_06 — 北京分公司客户有多少？`：PASS

- Semantic：PASS
- Query Plan：PASS
- Logical Plan：PASS
- SQL Compile：PASS
- Guardrail：PASS
- EXPLAIN：PASS
- Real DB Execute：PASS
- Result Validator：PASS
- 返回：1 行，`customer_count = 5`
- 过滤值：参数化为 `:p1`，未拼接进 SQL

## 7. 完整 10 条 Smoke Test

执行命令：`python scripts/check_real_db.py`

- Real DB Connection：PASS
- Read-only Verification：PASS
- Schema Check：PASS
- SCHEMA_DRIFT：0
- SMOKE_01：PASS
- SMOKE_02：PASS
- SMOKE_03：PASS
- SMOKE_04：PASS
- SMOKE_05：PASS
- SMOKE_06：PASS
- SMOKE_07：FAIL（`stock_product` 概念未在 Stage 4/5 展开为已验证维度筛选）
- SMOKE_08–10：按 Gate fail-fast 规则未运行

`SMOKE_07` 不属于 `parent_branch` Entity/Dimension Relation Mapping。本轮遵守“唯一目标”约束，没有扩大范围修改已验证 Semantic 主逻辑。

机器可读结果已更新至 `benchmark/reports/real_db_final/smoke_test.json`。

## 8. Regression

- 新增 hotfix 专项测试：12/12 PASS
- hotfix + Stage 8.4 SQL Compiler：33/33 PASS
- Full pytest（含 Stage 6、Stage 8.4、Stage 8.5、Guardrail、Hallucination）：217/217 PASS

新增测试覆盖：有效映射、customer → branch、branch → parent_branch、非法上级关系、未知关系拒绝、粒度放大拒绝、参数化、not_found、ambiguous、既有 branch 回归、同表面词消歧以及 distinct 客户粒度。

## 9. Gate 状态

`parent_branch` hotfix 本身：PASS。

完整 Real DB Gate：`FAIL`，阻塞点为后续独立问题 `SMOKE_07 stock_product concept expansion`。

## 10. 是否可以进入 Real DB Benchmark

不可以。必须先单独修复并验证 `SMOKE_07`，随后重新执行完整 10 条 Smoke Test；只有 10/10 PASS 后，才可将 `REAL_DB_GATE` 标记为 PASS 并进入 Real DB Benchmark。
