USE agentic_marketing;

SELECT 'ads_cust_info_d' AS table_name, COUNT(*) AS cnt
FROM ads_cust_info_d

UNION ALL

SELECT 'dim_branch', COUNT(*)
FROM dim_branch

UNION ALL

SELECT 'dim_product', COUNT(*)
FROM dim_product

UNION ALL

SELECT 'dim_public', COUNT(*)
FROM dim_public

UNION ALL

SELECT 'dwd_cust_hold_d', COUNT(*)
FROM dwd_cust_hold_d

UNION ALL

SELECT 'dwd_cust_tran_d', COUNT(*)
FROM dwd_cust_tran_d

UNION ALL

SELECT 'dws_cust_aset_d', COUNT(*)
FROM dws_cust_aset_d

UNION ALL

SELECT 'dws_cust_fin_d', COUNT(*)
FROM dws_cust_fin_d;