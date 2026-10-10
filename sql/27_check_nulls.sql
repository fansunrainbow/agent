USE agentic_marketing;

-- 1. 客户主表
SELECT
    COUNT(*) AS total_rows,
    SUM(pty_id IS NULL) AS pty_id_null,
    SUM(org_id IS NULL) AS org_id_null,
    SUM(cust_age IS NULL) AS cust_age_null,
    SUM(prov_name IS NULL) AS prov_name_null,
    SUM(city_name IS NULL) AS city_name_null
FROM ads_cust_info_d;


-- 2. 资产表
SELECT
    COUNT(*) AS total_rows,
    SUM(data_dt IS NULL) AS data_dt_null,
    SUM(pty_id IS NULL) AS pty_id_null,
    SUM(nm_tot_aset IS NULL) AS nm_tot_aset_null,
    SUM(nm_bal IS NULL) AS nm_bal_null,
    SUM(fc_pur_aset IS NULL) AS fc_pur_aset_null,
    SUM(fc_bal IS NULL) AS fc_bal_null
FROM dws_cust_aset_d;


-- 3. 资金流表
SELECT
    COUNT(*) AS total_rows,
    SUM(data_dt IS NULL) AS data_dt_null,
    SUM(pty_id IS NULL) AS pty_id_null,
    SUM(sys_source IS NULL) AS sys_source_null,
    SUM(cash_in IS NULL) AS cash_in_null,
    SUM(cash_out IS NULL) AS cash_out_null
FROM dws_cust_fin_d;


-- 4. 交易表
SELECT
    COUNT(*) AS total_rows,
    SUM(data_dt IS NULL) AS data_dt_null,
    SUM(pty_id IS NULL) AS pty_id_null,
    SUM(prdt_id IS NULL) AS prdt_id_null,
    SUM(sys_source IS NULL) AS sys_source_null,
    SUM(buy_amt IS NULL) AS buy_amt_null,
    SUM(sell_amt IS NULL) AS sell_amt_null
FROM dwd_cust_tran_d;


-- 5. 持仓表
SELECT
    COUNT(*) AS total_rows,
    SUM(data_dt IS NULL) AS data_dt_null,
    SUM(pty_id IS NULL) AS pty_id_null,
    SUM(prdt_id IS NULL) AS prdt_id_null,
    SUM(sys_source IS NULL) AS sys_source_null,
    SUM(hold_cnt IS NULL) AS hold_cnt_null,
    SUM(mkt_val IS NULL) AS mkt_val_null
FROM dwd_cust_hold_d;
-- 核心业务字段 NULL 汇总
SELECT 'ads_cust_info_d.city_name' AS field_name,
       SUM(city_name IS NULL) AS null_cnt
FROM ads_cust_info_d

UNION ALL
SELECT 'dws_cust_aset_d.fc_pur_aset',
       SUM(fc_pur_aset IS NULL)
FROM dws_cust_aset_d

UNION ALL
SELECT 'dws_cust_aset_d.fc_bal',
       SUM(fc_bal IS NULL)
FROM dws_cust_aset_d

UNION ALL
SELECT 'dws_cust_fin_d.cash_out',
       SUM(cash_out IS NULL)
FROM dws_cust_fin_d

UNION ALL
SELECT 'dwd_cust_tran_d.buy_amt',
       SUM(buy_amt IS NULL)
FROM dwd_cust_tran_d

UNION ALL
SELECT 'dwd_cust_tran_d.sell_amt',
       SUM(sell_amt IS NULL)
FROM dwd_cust_tran_d

UNION ALL
SELECT 'dwd_cust_hold_d.hold_cnt',
       SUM(hold_cnt IS NULL)
FROM dwd_cust_hold_d

UNION ALL
SELECT 'dwd_cust_hold_d.mkt_val',
       SUM(mkt_val IS NULL)
FROM dwd_cust_hold_d;