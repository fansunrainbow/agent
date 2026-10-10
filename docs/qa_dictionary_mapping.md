# 官方 Q&A 业务词典映射检查

## 检查目的

逐条检查官方 Q&A 中出现的业务概念，
确认这些概念都能够通过以下文件解析：

- business_dictionary.yaml
- concept_aliases.yaml
- value_mappings.yaml
- entity_rules.yaml
- segment_rules.yaml
- ambiguity_rules.yaml

若某个概念无法解析，则继续补充 Business Dictionary。

---
## 设计原则

本文件用于官方 Q&A 的回归测试与词典覆盖验证。

官方 Q&A 不是 Agent 的能力边界，也不应针对具体问题硬编码规则。

Business Dictionary 的目标是维护可复用的：

- 标准业务概念
- 枚举映射
- 层级关系
- 实体解析规则
- 派生客群规则
- 歧义澄清规则

后续任何未见过的新问题，都应通过这些通用语义组件组合解析。

因此：

> 官方 Q&A 用于验证通用能力是否覆盖官方场景，而不是为每一道官方问题建立专用规则。

## Q1

### 原始问题

学历本科及以上的男性客户，年龄大于50岁的有多少个

### 业务概念

- 本科及以上
- 男性客户
- 年龄大于50岁

### 词典映射

#### 本科及以上

标准概念：

bachelor_or_above

类型：

hierarchy

数据库映射：

ads_cust_info_d.edu_cd IN (
'6000004',
'6000003',
'6000002'
)

对应：

- 学士
- 硕士
- 博士

状态：

✅ 可解析

#### 男性客户

标准概念：

male_customer

类型：

enum

数据库映射：

ads_cust_info_d.gender_cd = '5000002'

状态：

✅ 可解析

#### 年龄大于50岁

该条件属于标准维度过滤：

dimension = age

condition:

cust_age > 50

不需要额外业务词典概念。

### 检查结论

✅ Q1 中所有业务概念均可解析。

---

---

## Q2

### 原始问题

不同客户年龄段资产分布情况：

1. 小于30
2. 大于等于30，小于50
3. 大于等于50，小于60
4. 大于等于60

### 业务概念

- 年龄段
- 资产

### 解析结果

#### 年龄段

属于标准维度：

`age_group`

标准规则：

- 30岁以下：`cust_age < 30`
- 30-49岁：`30 <= cust_age < 50`
- 50-59岁：`50 <= cust_age < 60`
- 60岁及以上：`cust_age >= 60`

状态：

✅ 可通过 dimensions.yaml 解析

#### 资产

“资产”存在潜在歧义。

候选：

- `total_asset`
- `holding_market_value`

当前问题是客户资产分布，因此优先解析：

`total_asset`

状态：

✅ 可通过 ambiguity_rules.yaml 消歧

### 检查结论

✅ Q2 全部可解析。

---

## Q3

### 原始问题

钻石卡男性客户，年龄大于40岁，持有比亚迪市值超过1000元，
他在26年Q1的盈亏情况。

### 业务概念

- 钻石卡客户
- 男性客户
- 年龄大于40岁
- 比亚迪
- 持有
- 市值超过1000元
- Q1
- 盈亏

### 解析结果

#### 钻石卡客户

标准概念：

`diamond_customer`

映射：

`ads_cust_info_d.cust_lvl_cd = '1000001'`

状态：

✅ 可解析

#### 男性客户

标准概念：

`male_customer`

映射：

`ads_cust_info_d.gender_cd = '5000002'`

状态：

✅ 可解析

#### 年龄大于40岁

维度：

`age`

条件：

`cust_age > 40`

状态：

✅ 可解析

#### 比亚迪

类型：

实体型业务词

实体规则：

`product`

行为：

在 `dim_product` 中优先按产品名称精确匹配。

如存在多个候选，触发澄清。

状态：

✅ 可通过 entity_rules.yaml 解析

#### 持有

解释：

指定时点存在相应产品持仓记录。

来源：

`dwd_cust_hold_d`

状态：

✅ 可作为存在性条件解析

#### 市值超过1000元

标准指标：

`holding_market_value`

条件：

`holding_market_value > 1000`

状态：

✅ 可解析

#### 盈亏

标准指标：

`asset_profit`

公式：

`period_end_asset - period_start_asset + total_outflow - total_inflow`

状态：

✅ 已在 Stage 2 定义并验证

### 检查结论

✅ Q3 全部可解析。

---

## Q4

### 原始问题

分公司各营业部的客户省份分析统计。

### 业务概念

- 分公司
- 营业部
- 省份
- 客户

### 解析结果

#### 分公司

标准概念：

`parent_branch_dimension`

来源：

- `dim_branch.up_org_id`
- `dim_branch.up_org_name`

状态：

✅ 可解析

#### 营业部

标准概念：

`branch_dimension`

来源：

- `dim_branch.org_id`
- `dim_branch.org_name`

状态：

✅ 可解析

#### 省份

标准概念：

`province_dimension`

来源：

`ads_cust_info_d.prov_name`

状态：

✅ 可解析

#### 客户

统计语境下映射：

`customer_count`

具体客户语境下使用：

`customer` 实体规则

状态：

✅ 可根据上下文解析

### 检查结论

✅ Q4 全部可解析。

---

## Q5

### 原始问题

26年Q1交易过招商银行，且26年Q1末普通账户持有中国平安的客户。

### 业务概念

- Q1
- 交易过
- 招商银行
- Q1末
- 普通账户
- 持有
- 中国平安

### 解析结果

#### 招商银行

类型：

实体型业务词

实体规则：

`product`

行为：

通过 `dim_product` 产品名称检索。

状态：

✅ 可解析

#### 交易过

解释：

指定期间内存在该产品交易记录。

来源：

`dwd_cust_tran_d`

说明：

不要求固定交易金额或交易次数阈值。

状态：

✅ 可解析为 transaction existence

#### 普通账户

标准概念：

`normal_account`

映射：

`sys_source = 'nm'`

状态：

✅ 可解析

#### 中国平安

类型：

实体型业务词

实体规则：

`product`

状态：

✅ 可解析

#### 持有

解释：

指定时点存在对应持仓记录。

来源：

`dwd_cust_hold_d`

状态：

✅ 可解析

#### Q1末

时间语义：

`end_of_period`

本题对应：

`2026-03-31`

状态：

✅ 可解析

### 检查结论

✅ Q5 全部可解析。

---

## Q6

### 原始问题

26年Q1日均资产大于30万的客户，股票交易量大于10万的，
其持有的产品属于哪些产品大类。

### 业务概念

- Q1
- 日均资产
- 股票
- 股票交易量
- 持有
- 产品大类

### 解析结果

#### 日均资产

属于 Metric System：

`average_total_asset`

状态：

✅ 已标准化

#### 股票

基础业务概念：

`stock_product`

但在“股票交易量”上下文中，
应结合指标上下文解析为：

`stock_trade_amount`

状态：

✅ 可通过上下文消歧

#### 股票交易量

根据官方 Q&A 现有业务口径：

“交易量”实际使用交易金额。

因此：

`stock_trade_amount > 100000`

状态：

✅ 已在 Stage 2 metric_aliases 中处理

#### 持有

解释：

存在产品持仓记录。

来源：

`dwd_cust_hold_d`

状态：

✅ 可解析

#### 产品大类

维度：

`product_primary_category`

来源：

`dim_product.up_prdt_type_name`

状态：

✅ 可解析

### 检查结论

✅ Q6 全部可解析。

---

## Q7

### 原始问题

查询26年1月10日到26年2月15日期间，
科创板交易量大于25万的客户营业部分布情况。

### 业务概念

- 明确时间范围
- 科创板
- 交易量
- 客户
- 营业部

### 解析结果

#### 时间范围

开始：

`2026-01-10`

结束：

`2026-02-15`

属于明确时间条件。

状态：

✅ 可解析

#### 科创板

类型：

产品二级分类

维度：

`product_secondary_category`

来源：

`dim_product.prdt_type_name`

条件：

`prdt_type_name = '科创板'`

状态：

✅ 可解析

#### 交易量

根据当前官方业务口径：

映射到：

`trade_amount`

条件：

`trade_amount > 250000`

状态：

✅ 可解析

#### 营业部

标准概念：

`branch_dimension`

来源：

- `dim_branch.org_id`
- `dim_branch.org_name`

状态：

✅ 可解析

### 检查结论

✅ Q7 全部可解析。

---

# 官方 Q&A 回归验证总结

## 验证数量

7 / 7

## 验证结论

✅ 官方 Q&A 中核心业务概念全部可以解析。

✅ 枚举型概念可以映射到真实数据库编码。

✅ 层级型概念可以映射到标准值集合。

✅ 产品、客户、营业部等高基数实体通过 entity_rules 动态解析。

✅ 模糊概念通过 ambiguity_rules 和上下文消歧处理。

✅ 指标类表达继续由 Stage 2 Metric System 负责。

## 泛化说明

本次官方 Q&A 验证属于回归测试，而不是问题模板。

系统没有针对 Q1～Q7 建立专用 SQL 或专用问句判断。

后续未知问题仍按照统一流程解析：

自然语言
→ 标准业务概念
→ 指标 / 维度 / 实体 / 时间 / 规则
→ Query Plan
→ SQL

因此 Business Dictionary 可以继续服务于未见过的新问题。