USE agentic_marketing;

-- 1. 持仓表里的产品是否都能在产品维表中找到
SELECT COUNT(*) AS hold_product_unmatched
FROM dwd_cust_hold_d h
LEFT JOIN dim_product p
    ON h.prdt_id = p.prdt_id
WHERE p.prdt_id IS NULL;

-- 2. 交易表里的产品是否都能在产品维表中找到
SELECT COUNT(*) AS tran_product_unmatched
FROM dwd_cust_tran_d t
LEFT JOIN dim_product p
    ON t.prdt_id = p.prdt_id
WHERE p.prdt_id IS NULL;