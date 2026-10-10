# 官方 Q&A 指标映射检查

## 检查目的

逐条检查官方 Q&A 中的自然语言问题，
确认每个问题都能够映射到现有的：

- metrics.yaml
- dimensions.yaml
- metric_aliases.yaml
- metric_constraints.yaml

如果某个业务概念无法映射，则需要补充指标体系。

---

## Q1

### 原始问题

学历本科及以上的男性客户，年龄大于50岁的有多少个

### 使用指标

- customer_count

### 使用维度

- education
- gender
- age

### 业务概念

- 本科及以上
- 男性
- 年龄大于50岁

### 时间规则

- 无显式时间条件
- 使用客户信息表当前快照语义

### 涉及数据表

- ads_cust_info_d
- dim_public

### 指标体系覆盖情况

- customer_count：已覆盖
- education：已覆盖
- gender：已覆盖
- age：已覆盖

### 待进入业务词典处理的概念

- 本科及以上
- 男性

### 检查结论

✅ 当前指标和维度体系可以承载该问题。

“本科及以上”“男性”的具体数据库映射属于业务词典范畴，
将在 Stage 3 — Business Dictionary 中进一步标准化。
## Q2

### 原始问题

不同客户年龄段资产分布情况，如下规则：

1. 小于30
2. 大于等于30，小于50
3. 大于等于50，小于60
4. 大于等于60

### 使用指标

- total_asset

### 使用维度

- age
- age_group
- customer
- date

### 业务概念

- 30岁以下
- 30-49岁
- 50-59岁
- 60岁及以上
- 客户资产分布

### 时间规则

- 客户属性使用 `20260531` 快照
- 资产指标使用 `20260331` 日快照
- 属于时点资产统计，不进行跨日期 SUM

### 涉及数据表

- ads_cust_info_d
- dws_cust_aset_d

### 指标体系覆盖情况

- total_asset：已覆盖
- age：已覆盖
- age_group：已覆盖
- customer：已覆盖
- date：已覆盖

### 待进入业务词典处理的概念

- 无新增核心业务概念
- 年龄段规则已经在 `dimensions.yaml` 中标准化

### 检查结论

✅ 当前指标和维度体系可以承载该问题。

官方 SQL 中的年龄分组规则与当前 `age_group` 定义一致：

- 年龄 < 30
- 30 <= 年龄 < 50
- 50 <= 年龄 < 60
- 年龄 >= 60

需要注意：客户属性取自 2026-05-31 快照，而资产数据取自
2026-03-31 快照，因此只能理解为“按当前客户属性分析
2026-03-31 的资产情况”，不能解释为 2026-03-31 当时的历史客户属性。

---

## Q3

### 原始问题

钻石卡男性客户，年龄大于40岁，持有比亚迪市值超过1000元，
他在26年Q1的盈亏情况。

### 使用指标

- holding_market_value
- period_start_asset
- period_end_asset
- total_inflow
- total_outflow

### 当前缺失指标

- asset_profit

### 使用维度

- customer
- customer_level
- gender
- age
- product
- date
- quarter

### 业务概念

- 钻石卡客户
- 男性
- 年龄大于40岁
- 比亚迪
- 持仓市值超过1000元
- 2026年Q1
- 盈亏情况

### 时间规则

- Q1：2026-01-01 至 2026-03-31
- 期初资产：官方 SQL 暂以 `20260101` 代替真正的 `20251231`
- 期末资产：`20260331`
- 持仓判断日期：`20260331`

### 涉及数据表

- ads_cust_info_d
- dim_public
- dwd_cust_hold_d
- dim_product
- dws_cust_aset_d
- dws_cust_fin_d

### 指标体系覆盖情况

- holding_market_value：已覆盖
- period_start_asset：已覆盖
- period_end_asset：已覆盖
- total_inflow：已覆盖
- total_outflow：已覆盖
- customer_level：已覆盖
- gender：已覆盖
- age：已覆盖
- product：已覆盖
- quarter：已覆盖
- asset_profit：❌ 当前缺失

### 待进入业务词典处理的概念

- 钻石卡客户
- 男性
- 比亚迪
- 盈亏

### 需要补充的指标

需要新增标准盈亏指标，例如：

`asset_profit`

其业务意图应表达为：

期末资产 - 期初资产 + 期间流出 - 期间流入

但官方 SQL 中 `aset_pft` 的表达式存在括号语义需要进一步确认，
因此在正式写入 `metrics.yaml` 前，应先核对官方口径。

### 检查结论

⚠️ 当前指标体系不能完全覆盖该问题。

主要缺口为“盈亏情况”对应的标准指标 `asset_profit`。

同时官方 SQL 注释明确说明，准确的 Q1 期初日期理论上应为
2025-12-31，但当前数据暂以 2026-01-01 代替，因此这是一个需要
保留的数据边界说明。

---

## Q4

### 原始问题

分公司各营业部的客户省份分析统计。

### 使用指标

- customer_count

### 使用维度

- parent_branch
- branch
- province
- city
- customer

### 业务概念

- 分公司
- 营业部
- 客户省份
- 客户城市
- 客户数量

### 时间规则

- 无显式历史时间范围
- 客户与营业部均使用当前快照语义

### 涉及数据表

- ads_cust_info_d
- dim_branch

### 指标体系覆盖情况

- customer_count：已覆盖
- parent_branch：已覆盖
- branch：已覆盖
- province：已覆盖
- city：已覆盖
- customer：已覆盖

### 待进入业务词典处理的概念

- 分公司
- 营业部

### 检查结论

✅ 当前指标和维度体系可以承载该问题。

该问题本质上是按照：

分公司 → 营业部 → 省份 → 城市

进行客户数量分组统计。

---

## Q5

### 原始问题

26年Q1交易过招商银行，且26年Q1末普通账户持有中国平安的客户。

### 使用指标

该问题主要属于“客户集合筛选”，官方 SQL 没有最终输出聚合指标。

可关联的已有指标包括：

- trade_amount
- holding_market_value

但官方 SQL 实际上只利用“存在交易记录”和“存在持仓记录”
判断客户是否满足条件，并未设置交易金额或持仓市值阈值。

### 使用维度

- customer
- product
- product_secondary_category
- account_source
- date
- quarter

### 业务概念

- 2026年Q1
- 交易过招商银行
- Q1末
- 普通账户
- 持有中国平安
- A股

### 时间规则

- Q1交易期间：2026-01-01 至 2026-03-31
- Q1期末：2026-03-31

### 涉及数据表

- dwd_cust_tran_d
- dwd_cust_hold_d
- dim_product

### 指标体系覆盖情况

- customer：已覆盖
- product：已覆盖
- product_secondary_category：已覆盖
- account_source：已覆盖
- date：已覆盖
- quarter：已覆盖
- trade_amount：已有，可用于交易金额分析
- holding_market_value：已有，可用于持仓市值分析

### 待进入业务词典处理的概念

- 招商银行
- 中国平安
- A股
- 普通账户
- “交易过”
- “持有”

### 检查结论

✅ 当前指标和维度体系基本可以承载该问题。

该问题不要求新增新的数值指标，主要依赖产品、账户来源、
日期等维度以及“存在交易”“存在持仓”两类业务条件。

这类存在性筛选规则后续更适合在 Query Plan 和 Business Dictionary
中进行标准化。

---

## Q6

### 原始问题

26年Q1日均资产大于30万的客户，股票交易量大于10万的，
其持有的产品属于哪些产品大类。

### 使用指标

- average_total_asset
- stock_trade_amount
- holding_market_value

### 使用维度

- customer
- product
- product_primary_category
- product_secondary_category
- date
- quarter

### 业务概念

- 2026年Q1
- 日均资产
- 日均资产大于30万
- 股票
- 股票交易量大于10万
- 产品大类
- 产品二级分类

### 时间规则

- Q1：2026-01-01 至 2026-03-31
- Q1末持仓：2026-03-31

### 涉及数据表

- dws_cust_aset_d
- dwd_cust_tran_d
- dwd_cust_hold_d
- dim_product

### 指标体系覆盖情况

- average_total_asset：已覆盖
- stock_trade_amount：已覆盖
- holding_market_value：已覆盖
- customer：已覆盖
- product：已覆盖
- product_primary_category：已覆盖
- product_secondary_category：已覆盖
- quarter：已覆盖

### 待进入业务词典处理的概念

- 股票
- 产品大类
- “交易量”

### 发现的口径差异

⚠️ 官方 SQL 中“日均资产”的计算方式与当前 Metric System
定义存在差异。

当前 Metric System 定义：

`average_total_asset`

= 对统计期间内实际存在的每日资产快照求 AVG。

而官方 SQL 的计算思路为：

期间资产记录求和 / Q1自然日天数。

因此需要在正式完成 Stage 2 前统一“日均资产”的最终标准口径。

### 发现的别名缺口

官方问题使用：

`股票交易量`

但官方 SQL 实际计算：

`SUM(buy_amt) + SUM(sell_amt)`

也就是金额口径，而不是数量口径。

因此根据官方 Q&A 语义：

`交易量`

在当前数据场景中应能够映射到：

`trade_amount`

建议后续在 `metric_aliases.yaml` 中补充：

- 交易量
- 股票交易量
- 基金交易量

对应交易金额类指标。

### 检查结论

⚠️ 指标和维度已经覆盖该问题，但存在一个需要解决的
“日均资产口径冲突”和一个“交易量别名缺口”。

---

## Q7

### 原始问题

查询26年1月10日到26年2月15日期间，
科创板交易量大于25万的客户营业部分布情况。

### 使用指标

- trade_amount

### 使用维度

- customer
- product_secondary_category
- branch
- parent_branch
- date

### 业务概念

- 2026-01-10 至 2026-02-15
- 科创板
- 交易量大于25万
- 营业部分布
- 分公司

### 时间规则

- 开始日期：2026-01-10
- 结束日期：2026-02-15
- 属于明确自定义时间范围

### 涉及数据表

- ads_cust_info_d
- dwd_cust_tran_d
- dim_product
- dim_branch

### 指标体系覆盖情况

- trade_amount：已覆盖
- customer：已覆盖
- product_secondary_category：已覆盖
- branch：已覆盖
- parent_branch：已覆盖
- date：已覆盖

### 待进入业务词典处理的概念

- 科创板
- 营业部
- 分公司
- 交易量

### 发现的别名缺口

官方问题写的是：

`交易量大于25万`

但官方 SQL 实际使用：

`SUM(buy_amt) + SUM(sell_amt)`

因此这里的“交易量”仍然表示交易金额，而不是交易数量。

建议将：

`交易量`

加入 `trade_amount` 的标准别名。

### 检查结论

✅ 指标和维度体系能够承载该问题。

⚠️ 但需要补充“交易量 → trade_amount”的别名映射。

---

# 官方 Q&A 第一轮反向检查总结

## 已检查问题数量

7 / 7

## 当前可直接覆盖

- Q1：✅
- Q2：✅
- Q4：✅
- Q5：✅
- Q7：✅

## 存在待完善项

### Q3

缺少标准盈亏指标：

- asset_profit

同时需要确认官方 SQL 中 `aset_pft` 的最终计算口径。

### Q6

存在“日均资产”计算口径差异：

- 当前 Metric System：实际资产快照 AVG
- 官方 SQL：资产合计 / 自然日天数

正式完成 Stage 2 前需要确定统一口径。

### Q6 / Q7

官方问题中的：

- 交易量
- 股票交易量

实际 SQL 均使用：

`buy_amt + sell_amt`

因此当前业务语义下应映射为金额类指标，而不是次数或数量指标。

需要补充 `metric_aliases.yaml`。

## 第一轮结论

⚠️ 官方 Q&A 已全部完成反向检查，但 Stage 2.3 目前还不能直接标记为完全完成。

需要先解决：

1. 新增或确认 `asset_profit` 盈亏指标；
2. 确认 `average_total_asset` 的最终日均资产口径；
3. 补充“交易量”相关指标别名。

完成以上三项后，再进行一次最终覆盖检查。