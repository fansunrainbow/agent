# Agentic Marketing 数据模型说明

## 1. 数据库概况

数据库名称：

`agentic_marketing`

数据库系统：

`MySQL 8.0`

当前数据库共包含 8 张业务数据表：

| 表名 | 中文含义 | 类型 | 当前数据量 |
|---|---|---|---:|
| ads_cust_info_d | 客户信息表 | 维度/快照表 | 500 |
| dim_branch | 营业部表 | 维度/快照表 | 312 |
| dim_product | 产品属性维表 | 维度表 | 334694 |
| dim_public | 标准化编码字典表 | 字典表 | 155 |
| dws_cust_aset_d | 客户资产日汇总表 | 事实表 | 43684 |
| dws_cust_fin_d | 客户资金流动日事实表 | 事实表 | 4892 |
| dwd_cust_tran_d | 客户交易类买卖日事实表 | 事实表 | 39060 |
| dwd_cust_hold_d | 客户持有产品日事实表 | 事实表 | 408150 |

---

## 2. 表级数据模型

### 2.1 ads_cust_info_d

中文名称：

客户信息表

类型：

客户维度 / 客户快照表

数据量：

`500`

时间范围：

`20260531 ~ 20260531`

说明：

当前数据集中，该表可视为 2026-05-31 的客户信息快照。

核心字段：

- `data_dt`：数据日期
- `pty_id`：客户号
- `sor_pty_id`：来源客户号
- `cust_lvl_cd`：客户等级代码
- `cust_status`：客户状态代码
- `cust_type`：客户类型
- `prov_name`：省份
- `city_name`：城市
- `birth_dt`：出生日期
- `cust_age`：客户年龄
- `name`：客户姓名
- `gender_cd`：性别代码
- `edu_cd`：学历代码
- `prof_cd`：职业类型编码
- `org_id`：所属营业部 ID

数据粒度：

一名客户一条当前快照记录。

核心关联：

- `pty_id` → `dws_cust_aset_d.pty_id`
- `pty_id` → `dws_cust_fin_d.pty_id`
- `pty_id` → `dwd_cust_tran_d.pty_id`
- `pty_id` → `dwd_cust_hold_d.pty_id`
- `org_id` → `dim_branch.org_id`

验证结果：

- 与资产表客户关联缺失数：0
- 与资金流表客户关联缺失数：0
- 与交易表客户关联缺失数：0
- 与持仓表客户关联缺失数：0
- 与营业部表关联缺失数：0

---

### 2.2 dim_branch

中文名称：

营业部表

类型：

机构维度 / 快照表

数据量：

`312`

时间范围：

`20260531 ~ 20260531`

数据粒度：

一条记录对应一个营业部当前快照。

核心字段：

- `data_dt`
- `org_id`
- `org_name`
- `up_org_id`
- `up_org_name`

核心关联：

`ads_cust_info_d.org_id` → `dim_branch.org_id`

---

### 2.3 dim_product

中文名称：

产品属性维表

类型：

产品维度表

数据量：

`334694`

核心字段：

- `prdt_id`：产品 ID
- `prdt_name`：产品名称
- `sor_prdt_id`：来源产品代码
- `market_id`：市场 ID
- `prdt_type_id`：产品二级分类 ID
- `prdt_type_name`：产品二级分类名称
- `up_prdt_type_id`：产品一级分类 ID
- `up_prdt_type_name`：产品一级分类名称

核心关联：

- `dwd_cust_hold_d.prdt_id` → `dim_product.prdt_id`
- `dwd_cust_tran_d.prdt_id` → `dim_product.prdt_id`

关联完整性：

- 持仓产品关联缺失数：0
- 交易产品关联缺失数：0

---

### 2.4 dim_public

中文名称：

标准化编码字典表

类型：

公共字典表

数据量：

`155`

核心字段：

- `code`
- `code_type_id`
- `describe`

主要用途：

将数据库中的编码字段映射成业务语义，例如：

- 客户等级
- 客户状态
- 性别
- 其他标准字典编码

---

### 2.5 dws_cust_aset_d

中文名称：

客户资产日汇总表

类型：

事实表

数据量：

`43684`

时间范围：

`20260101 ~ 20260331`

已验证粒度：

`客户 + 日期`

即：

`pty_id + data_dt`

在该粒度下未发现重复记录。

核心字段：

- `data_dt`
- `pty_id`
- `nm_tot_aset`
- `nm_bal`
- `fc_pur_aset`
- `fc_bal`

主要用途：

- 客户资产规模分析
- 普通账户资产分析
- 信用账户资产分析
- 客户资产时间趋势分析

---

### 2.6 dws_cust_fin_d

中文名称：

客户资金流动日事实表

类型：

事实表

数据量：

`4892`

时间范围：

`20260105 ~ 20260331`

已验证粒度：

`客户 + 日期 + 系统来源`

即：

`pty_id + data_dt + sys_source`

在该粒度下未发现重复记录。

核心字段：

- `data_dt`
- `pty_id`
- `sys_source`
- `cash_in`
- `cash_out`
- `tran_in`
- `tran_out`
- `assign_in`
- `assign_out`

系统来源：

- `nm`：普通账户
- `fc`：信用账户

---

### 2.7 dwd_cust_tran_d

中文名称：

客户交易类买卖日事实表

类型：

事实表

数据量：

`39060`

时间范围：

`20260105 ~ 20260331`

已验证粒度：

`客户 + 日期 + 产品 + 系统来源 + 币种`

即：

`pty_id + data_dt + prdt_id + sys_source + ccy`

在该粒度下未发现重复记录。

核心字段：

- `data_dt`
- `pty_id`
- `prdt_id`
- `sys_source`
- `ccy`
- `buy_cnt`
- `buy_mnt`
- `buy_rake`
- `buy_amt`
- `buy_fare`
- `sell_cnt`
- `sell_mnt`
- `sell_rake`
- `sell_amt`
- `sell_fare`

系统来源：

- `nm`：普通账户
- `fc`：信用账户

当前数据中币种：

- `0`：人民币

当前交易数据中未出现美元或港币记录。

---

### 2.8 dwd_cust_hold_d

中文名称：

客户持有产品日事实表

类型：

事实表

数据量：

`408150`

时间范围：

`20260101 ~ 20260331`

已验证粒度：

`客户 + 日期 + 产品 + 系统来源 + 币种`

即：

`pty_id + data_dt + prdt_id + sys_source + ccy`

在该粒度下未发现重复记录。

核心字段：

- `data_dt`
- `pty_id`
- `prdt_id`
- `sys_source`
- `ccy`
- `hold_cnt`
- `mkt_val`

系统来源：

- `nm`：普通账户
- `fc`：信用账户

当前数据中币种：

- `0`：人民币

当前持仓数据中未出现美元或港币记录。

---

## 3. 核心 Join 关系

### 3.1 客户关系

```text
ads_cust_info_d
    |
    | pty_id
    |
    +---- dws_cust_aset_d
    |
    +---- dws_cust_fin_d
    |
    +---- dwd_cust_tran_d
    |
    +---- dwd_cust_hold_d