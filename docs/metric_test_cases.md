# Metric System 手工测试用例

## 测试目的

验证自然语言问题能够正确映射到标准指标、维度和时间口径，
确保后续 Query Plan 与 Agent 不需要临时猜测指标定义。

---

## Case 1：某日客户总资产

### 问题

客户 A 在 2026-03-31 的总资产是多少？

### 使用指标

- total_asset

### 使用维度

- customer
- date

### 预期计算

total_asset = nm_tot_aset + fc_pur_aset

### 时间语义

指定日期快照

### 预期结果

取客户在 2026-03-31 的资产快照计算总资产。

---

## Case 2：Q1 日均资产

### 问题

客户 A 2026 年 Q1 的日均资产是多少？

### 使用指标

- average_total_asset

### 使用维度

- customer
- quarter

### 预期计算

Q1期间资产累计值 / Q1自然日天数

2026年Q1自然日天数为90天。

### 时间语义

calendar_day_average

---

## Case 3：有效快照日均资产

### 问题

客户 A 2026 年 Q1 已有资产记录的平均资产是多少？

### 使用指标

- observed_average_total_asset

### 使用维度

- customer
- quarter

### 预期计算

对 Q1 实际存在的每日资产快照计算 AVG。

---

## Case 4：客户现金资产

### 问题

客户 A 某日现金资产是多少？

### 使用指标

- cash_asset

### 预期计算

cash_asset = nm_bal + fc_bal

---

## Case 5：客户交易额

### 问题

客户 A 2026 年 Q1 的交易额是多少？

### 使用指标

- trade_amount

### 使用维度

- customer
- quarter

### 预期计算

SUM(buy_amt + sell_amt)

### 时间语义

期间流量指标按 SUM 聚合。

---

## Case 6：交易量自然语言映射

### 问题

客户 A 2026 年 Q1 的交易量是多少？

### 使用指标

- trade_amount

### 说明

根据官方 Q&A 当前业务口径，
“交易量”映射到交易金额，而不是交易次数。

---

## Case 7：交易次数

### 问题

客户 A 2026 年 Q1 一共交易多少次？

### 使用指标

- trade_count

### 预期计算

SUM(buy_cnt + sell_cnt)

---

## Case 8：股票交易金额

### 问题

客户 A 2026 年 Q1 股票交易额是多少？

### 使用指标

- stock_trade_amount

### 产品过滤

up_prdt_type_name = '股票'

### 预期计算

股票类产品：

SUM(buy_amt + sell_amt)

---

## Case 9：基金交易金额

### 问题

客户 A 2026 年 Q1 基金成交额是多少？

### 使用指标

- fund_trade_amount

### 产品过滤

up_prdt_type_name = '开放式基金'

---

## Case 10：股票持仓市值

### 问题

客户 A 在 2026-03-31 的股票持仓市值是多少？

### 使用指标

- stock_holding_value

### 产品过滤

up_prdt_type_name = '股票'

### 时间语义

日快照

---

## Case 11：基金持仓占比

### 问题

客户 A 的基金配置比例是多少？

### 使用指标

- fund_holding_ratio

### 预期计算

fund_holding_value / holding_market_value

### 分母规则

如果 holding_market_value = 0，则返回 NULL。

---

## Case 12：债券持仓占比

### 问题

客户 A 的债券资产占全部持仓的比例是多少？

### 使用指标

- bond_holding_ratio

### 预期计算

bond_holding_value / holding_market_value

### 分母规则

总持仓为0时返回NULL。

---

## Case 13：期间净流入

### 问题

客户 A 2026 年 Q1 净资金流入是多少？

### 使用指标

- net_inflow

### 预期计算

total_inflow - total_outflow

---

## Case 14：资产变化额

### 问题

客户 A 2026 年 Q1 资产增加了多少？

### 使用指标

- asset_change

### 预期计算

period_end_asset - period_start_asset

---

## Case 15：资产变化率

### 问题

客户 A 2026 年 Q1 资产增长率是多少？

### 使用指标

- asset_change_rate

### 预期计算

(period_end_asset - period_start_asset)
/
period_start_asset

### 分母规则

如果 period_start_asset = 0，则返回 NULL。

---

## Case 16：资产盈亏

### 问题

客户 A 2026 年 Q1 的盈亏是多少？

### 使用指标

- asset_profit

### 预期计算

period_end_asset
- period_start_asset
+ total_outflow
- total_inflow

### 时间要求

必须明确统计期间。

---

## Case 17：年龄段客户数

### 问题

50～59 岁客户有多少人？

### 使用指标

- customer_count

### 使用维度

- age_group

### 年龄规则

50 <= cust_age < 60

---

## Case 18：营业部客户数量

### 问题

每个营业部有多少客户？

### 使用指标

- customer_count

### 使用维度

- branch

---

## Case 19：省份客户分布

### 问题

不同省份分别有多少客户？

### 使用指标

- customer_count

### 使用维度

- province

---

## Case 20：日均资产与股票交易组合筛选

### 问题

查询2026年Q1日均资产超过30万元，
且股票交易额超过10万元的客户。

### 使用指标

- average_total_asset
- stock_trade_amount

### 使用维度

- customer
- quarter

### 筛选条件

average_total_asset > 300000

stock_trade_amount > 100000

### 时间规则

2026 Q1 = 2026-01-01 至 2026-03-31

---

# 测试结论

以上测试覆盖：

- 客户指标
- 资产指标
- 持仓指标
- 交易指标
- 资金流指标
- 产品配置指标
- 时间口径
- 产品分类
- 比例指标
- 复合指标
- 自然语言别名

这些测试将作为后续 Query Plan、Agent 和 Benchmark 的基础测试案例。