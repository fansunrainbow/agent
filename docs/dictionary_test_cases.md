# Business Dictionary 手工测试用例

## 测试目的

验证自然语言业务词能够稳定映射到标准业务概念、
数据库字段、代码值、实体规则和歧义处理规则。

---

## Case 1：钻石客户

输入：

钻石客户

预期解析：

concept = diamond_customer

数据库映射：

ads_cust_info_d.cust_lvl_cd = '1000001'

---

## Case 2：白金客户

输入：

白金卡客户

预期解析：

concept = platinum_customer

数据库映射：

ads_cust_info_d.cust_lvl_cd = '1000002'

---

## Case 3：金卡客户

输入：

金卡客户

预期解析：

concept = gold_customer

数据库映射：

ads_cust_info_d.cust_lvl_cd = '1000003'

---

## Case 4：男性客户

输入：

男性客户

预期解析：

concept = male_customer

数据库映射：

ads_cust_info_d.gender_cd = '5000002'

---

## Case 5：女性客户

输入：

女性

预期解析：

concept = female_customer

数据库映射：

ads_cust_info_d.gender_cd = '5000003'

---

## Case 6：本科及以上

输入：

本科及以上

预期解析：

concept = bachelor_or_above

数据库映射：

edu_cd IN (
'6000004',
'6000003',
'6000002'
)

对应：

学士、硕士、博士

---

## Case 7：股票

输入：

股票

预期解析：

concept = stock_product

数据库映射：

dim_product.up_prdt_type_name = '股票'

---

## Case 8：基金

输入：

基金

预期解析：

concept = fund_product

数据库映射：

dim_product.up_prdt_type_name = '开放式基金'

---

## Case 9：债券

输入：

债券产品

预期解析：

concept = bond_product

数据库映射：

dim_product.up_prdt_type_name = '债券'

---

## Case 10：普通账户

输入：

普通账户

预期解析：

concept = normal_account

数据库映射：

sys_source = 'nm'

---

## Case 11：信用账户

输入：

信用账户

预期解析：

concept = credit_account

数据库映射：

sys_source = 'fc'

---

## Case 12：A股

输入：

A股

预期解析：

concept = a_share_product

数据库映射：

dim_product.prdt_type_name = 'A股'

---

## Case 13：招商银行

输入：

招商银行

预期解析：

category = entity

entity_rule = product

行为：

优先在 dim_product.prdt_name 中进行精确匹配。

若存在多个候选：

触发澄清。

---

## Case 14：比亚迪

输入：

比亚迪

预期解析：

category = entity

entity_rule = product

行为：

查询 dim_product 中匹配的具体产品。

---

## Case 15：中国平安

输入：

中国平安

预期解析：

category = entity

entity_rule = product

行为：

通过产品实体搜索解析。

---

## Case 16：某营业部

输入：

某营业部名称

预期解析：

category = entity

entity_rule = branch

搜索字段：

- org_name
- org_id

---

## Case 17：指定客户号

输入：

客户号 C00000000000169

预期解析：

category = entity

entity_rule = customer

匹配规则：

优先精确匹配 pty_id。

---

## Case 18：高资产客户

输入：

高资产客户

预期解析：

segment = high_asset_customer

使用指标：

average_total_asset

默认规则：

average_total_asset >= 1000000

注意：

阈值可配置，并需要业务确认。

---

## Case 19：资产增长客户

输入：

资产增长客户

预期解析：

segment = asset_growth_customer

使用指标：

asset_change

规则：

asset_change > 0

---

## Case 20：净流入客户

输入：

净流入客户

预期解析：

segment = net_inflow_customer

使用指标：

net_inflow

规则：

net_inflow > 0

---

## Case 21：交易活跃客户

输入：

交易活跃客户

预期解析：

segment = active_trading_customer

使用指标：

trade_count

默认规则：

trade_count >= 20

注意：

阈值属于可配置业务参数。

---

## Case 22：近期交易客户

输入：

近期交易客户

预期解析：

segment = recent_trading_customer

行为：

必须解析“近期”的时间范围。

若上下文未给出：

触发澄清。

---

## Case 23：优质客户

输入：

优质客户

预期：

不能直接生成 SQL。

行为：

触发澄清。

候选解释：

- 客户等级
- 资产规模
- 交易活跃度
- 综合经营规则

---

## Case 24：活跃客户

输入：

活跃客户

预期：

不能默认等于交易次数高。

候选解释：

- 交易次数
- 交易金额
- 最近交易时间

若上下文不足：

触发澄清。

---

## Case 25：大额资金

输入：

大额资金客户

预期：

“大额”不能直接写死。

候选规则：

- 绝对金额阈值
- 相对客户资产比例

行为：

需要上下文或用户确认。

---

## Case 26：近期

输入：

查询近期交易客户

预期：

“近期”属于模糊时间概念。

候选：

- 最近7天
- 最近30天
- 最近3个月
- 用户指定时间范围

---

## Case 27：资产

输入：

资产超过100万元的客户

预期优先解析：

total_asset

但如果上下文为：

股票资产、基金资产、产品持仓资产

则需要根据上下文判断是否为：

holding_market_value

---

## Case 28：交易

输入：

有交易的客户

预期：

不能自动映射到 trade_amount 或 trade_count。

这里更可能表示：

transaction_exists

即判断是否存在交易记录。

---

## Case 29：基金

输入：

基金配置比例低于10%的客户

预期：

“基金”根据上下文解析为：

fund_holding_ratio

而不是单纯的 fund_product。

---

## Case 30：股票

输入：

股票交易额超过10万元的客户

预期：

“股票”根据上下文解析为：

stock_trade_amount

而不是单纯产品类别。

---

# 测试覆盖总结

以上测试覆盖：

- 枚举型业务概念
- 层级型业务概念
- 派生型业务概念
- 实体型业务概念
- 模糊型业务概念
- 别名解析
- 实体检索
- 客群规则
- 歧义澄清
- 上下文消歧