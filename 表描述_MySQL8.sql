USE `agentic_marketing`;

CREATE TABLE `dim_product` (
    `prdt_id` VARCHAR(12) COMMENT '产品ID',
    `prdt_name` VARCHAR(100) COMMENT '产品名称',
    `sor_prdt_id` VARCHAR(12) COMMENT '产品代码',
    `market_id` VARCHAR(50),
    `prdt_type_id` VARCHAR(12) COMMENT '产品二级分类ID',
    `prdt_type_name` VARCHAR(40) COMMENT '产品二级分类名称',
    `up_prdt_type_id` VARCHAR(12) COMMENT '产品一级分类ID',
    `up_prdt_type_name` VARCHAR(40) COMMENT '产品一级分类名称'
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci
  COMMENT='产品属性维表';

CREATE TABLE `ads_cust_info_d` (
    `data_dt` VARCHAR(8) COMMENT '日期',
    `pty_id` VARCHAR(32) COMMENT '客户号',
    `sor_pty_id` VARCHAR(32) COMMENT '经纪客户号',
    `cust_lvl_cd` VARCHAR(12) COMMENT '客户等级',
    `cust_status` VARCHAR(12) COMMENT '账户状态',
    `cust_type` VARCHAR(1) COMMENT '客户类型',
    `prov_name` VARCHAR(50) COMMENT '省份',
    `city_name` VARCHAR(50) COMMENT '城市',
    `birth_dt` VARCHAR(8) COMMENT '出生日期',
    `cust_age` DECIMAL(20,0) COMMENT '年龄',
    `name` VARCHAR(40) COMMENT '姓名',
    `gender_cd` VARCHAR(12) COMMENT '性别代码',
    `edu_cd` VARCHAR(32) COMMENT '学历代码',
    `prof_cd` VARCHAR(100) COMMENT '职业类型编码',
    `org_id` VARCHAR(100) COMMENT '所属营业部ID'
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci
  COMMENT='客户信息表';

CREATE TABLE `dws_cust_fin_d` (
    `data_dt` VARCHAR(8) NOT NULL COMMENT '日期',
    `pty_id` VARCHAR(32) NOT NULL COMMENT '客户号',
    `sys_source` VARCHAR(20) NOT NULL COMMENT '系统来源：普通(nm)、信用(fc)',
    `cash_in` DECIMAL(20,4) COMMENT '现金转入',
    `cash_out` DECIMAL(20,4) COMMENT '现金转出',
    `tran_in` DECIMAL(20,4) COMMENT '证券转入、托管转入、转托转入',
    `tran_out` DECIMAL(20,4) COMMENT '证券转出、托管转出、转托转出',
    `assign_in` DECIMAL(20,4) COMMENT '指定转入',
    `assign_out` DECIMAL(20,4) COMMENT '撤指定转出'
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci
  COMMENT='客户资金流动日事实';

CREATE TABLE `dwd_cust_hold_d` (
    `data_dt` VARCHAR(8) NOT NULL COMMENT '日期',
    `pty_id` VARCHAR(32) NOT NULL COMMENT '客户号',
    `prdt_id` VARCHAR(12) NOT NULL COMMENT '产品ID',
    `sys_source` VARCHAR(20) NOT NULL COMMENT '系统来源：普通(nm)、信用(fc)',
    `ccy` VARCHAR(12) NOT NULL COMMENT '币种,0 人民币；1 美元；2 港币',
    `hold_cnt` DECIMAL(20,4) COMMENT '持有份额',
    `mkt_val` DECIMAL(20,4) COMMENT '持有市值'
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci
  COMMENT='客户持有产品日事实';

CREATE TABLE `dwd_cust_tran_d` (
    `data_dt` VARCHAR(8) NOT NULL COMMENT '日期',
    `pty_id` VARCHAR(32) NOT NULL COMMENT '客户号',
    `prdt_id` VARCHAR(12) NOT NULL COMMENT '产品ID',
    `sys_source` VARCHAR(20) NOT NULL COMMENT '系统来源：普通(nm)、信用(fc)',
    `ccy` VARCHAR(12) NOT NULL COMMENT '币种,0 人民币；1 美元；2 港币',
    `buy_cnt` INT COMMENT '买入次数',
    `buy_mnt` DECIMAL(20,4) COMMENT '买入数量',
    `buy_rake` DECIMAL(20,4) COMMENT '买入佣金',
    `buy_amt` DECIMAL(20,4) COMMENT '买入金额',
    `buy_fare` DECIMAL(20,4) COMMENT '买入费用',
    `sell_cnt` INT COMMENT '卖出次数',
    `sell_mnt` DECIMAL(20,4) COMMENT '卖出数量',
    `sell_rake` DECIMAL(20,4) COMMENT '卖出佣金',
    `sell_amt` DECIMAL(20,4) COMMENT '卖出金额',
    `sell_fare` DECIMAL(20,4) COMMENT '卖出费用'
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci
  COMMENT='客户交易类买卖日事实';

CREATE TABLE `dws_cust_aset_d` (
    `data_dt` VARCHAR(8) NOT NULL COMMENT '日期',
    `pty_id` VARCHAR(32) NOT NULL COMMENT '客户号',
    `nm_tot_aset` DECIMAL(20,4) COMMENT '普通账户总资产',
    `nm_bal` DECIMAL(20,4) COMMENT '普通账户现金资产',
    `fc_pur_aset` DECIMAL(20,4) COMMENT '信用账户净资产',
    `fc_bal` DECIMAL(20,4) COMMENT '信用账户现金资产'
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci
  COMMENT='客户资产日汇总';

CREATE TABLE `dim_public` (
    `code` VARCHAR(12) NOT NULL COMMENT '标准字典码',
    `code_type_id` VARCHAR(6) NOT NULL COMMENT '标准字典码类型',
    `describe` VARCHAR(50) NOT NULL COMMENT '标准字典描述'
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci
  COMMENT='标准化编码字典表';

CREATE TABLE `dim_branch` (
    `data_dt` VARCHAR(8) NOT NULL,
    `org_id` VARCHAR(50) NOT NULL COMMENT '营业部ID',
    `org_name` VARCHAR(100) NOT NULL COMMENT '营业部名称',
    `up_org_id` VARCHAR(50) NOT NULL COMMENT '上级营业部/分公司ID',
    `up_org_name` VARCHAR(100) NOT NULL COMMENT '上级营业部/分公司名称'
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci
  COMMENT='营业部表';
