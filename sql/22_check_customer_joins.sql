USE agentic_marketing;

-- 1. 资产表里的客户是否都能在客户主表找到
SELECT COUNT(*) AS aset_unmatched
FROM dws_cust_aset_d a
LEFT JOIN ads_cust_info_d c
    ON a.pty_id = c.pty_id
WHERE c.pty_id IS NULL;

-- 2. 持仓表里的客户是否都能找到
SELECT COUNT(*) AS hold_unmatched
FROM dwd_cust_hold_d h
LEFT JOIN ads_cust_info_d c
    ON h.pty_id = c.pty_id
WHERE c.pty_id IS NULL;

-- 3. 交易表里的客户是否都能找到
SELECT COUNT(*) AS tran_unmatched
FROM dwd_cust_tran_d t
LEFT JOIN ads_cust_info_d c
    ON t.pty_id = c.pty_id
WHERE c.pty_id IS NULL;

-- 4. 资金流表里的客户是否都能找到
SELECT COUNT(*) AS fin_unmatched
FROM dws_cust_fin_d f
LEFT JOIN ads_cust_info_d c
    ON f.pty_id = c.pty_id
WHERE c.pty_id IS NULL;