USE agentic_marketing;

-- 1. 客户类型
SELECT
    cust_type,
    COUNT(*) AS cnt
FROM ads_cust_info_d
GROUP BY cust_type
ORDER BY cnt DESC;

-- 2. 客户等级
SELECT
    cust_lvl_cd,
    COUNT(*) AS cnt
FROM ads_cust_info_d
GROUP BY cust_lvl_cd
ORDER BY cnt DESC;

-- 3. 客户状态
SELECT
    cust_status,
    COUNT(*) AS cnt
FROM ads_cust_info_d
GROUP BY cust_status
ORDER BY cnt DESC;

-- 4. 性别编码
SELECT
    gender_cd,
    COUNT(*) AS cnt
FROM ads_cust_info_d
GROUP BY gender_cd
ORDER BY cnt DESC;

-- 5. 资金流系统来源
SELECT
    sys_source,
    COUNT(*) AS cnt
FROM dws_cust_fin_d
GROUP BY sys_source
ORDER BY cnt DESC;

-- 6. 交易系统来源
SELECT
    sys_source,
    COUNT(*) AS cnt
FROM dwd_cust_tran_d
GROUP BY sys_source
ORDER BY cnt DESC;

-- 7. 持仓系统来源
SELECT
    sys_source,
    COUNT(*) AS cnt
FROM dwd_cust_hold_d
GROUP BY sys_source
ORDER BY cnt DESC;

-- 8. 交易币种
SELECT
    ccy,
    COUNT(*) AS cnt
FROM dwd_cust_tran_d
GROUP BY ccy
ORDER BY cnt DESC;

-- 9. 持仓币种
SELECT
    ccy,
    COUNT(*) AS cnt
FROM dwd_cust_hold_d
GROUP BY ccy
ORDER BY cnt DESC;