USE agentic_marketing;

SELECT
    'ads_cust_info_d' AS table_name,
    MIN(data_dt) AS min_dt,
    MAX(data_dt) AS max_dt
FROM ads_cust_info_d

UNION ALL

SELECT
    'dim_branch',
    MIN(data_dt),
    MAX(data_dt)
FROM dim_branch

UNION ALL

SELECT
    'dws_cust_aset_d',
    MIN(data_dt),
    MAX(data_dt)
FROM dws_cust_aset_d

UNION ALL

SELECT
    'dws_cust_fin_d',
    MIN(data_dt),
    MAX(data_dt)
FROM dws_cust_fin_d

UNION ALL

SELECT
    'dwd_cust_tran_d',
    MIN(data_dt),
    MAX(data_dt)
FROM dwd_cust_tran_d

UNION ALL

SELECT
    'dwd_cust_hold_d',
    MIN(data_dt),
    MAX(data_dt)
FROM dwd_cust_hold_d;