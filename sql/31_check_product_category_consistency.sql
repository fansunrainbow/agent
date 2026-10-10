USE agentic_marketing;

SELECT
    up_prdt_type_id,
    COUNT(DISTINCT up_prdt_type_name) AS name_count,
    GROUP_CONCAT(
        DISTINCT up_prdt_type_name
        ORDER BY up_prdt_type_name
        SEPARATOR ' / '
    ) AS names,
    COUNT(*) AS product_count
FROM dim_product
GROUP BY up_prdt_type_id
HAVING COUNT(DISTINCT up_prdt_type_name) > 1
ORDER BY product_count DESC;

SELECT
    prdt_type_id,
    COUNT(DISTINCT prdt_type_name) AS name_count,
    GROUP_CONCAT(
        DISTINCT prdt_type_name
        ORDER BY prdt_type_name
        SEPARATOR ' / '
    ) AS names,
    COUNT(*) AS product_count
FROM dim_product
GROUP BY prdt_type_id
HAVING COUNT(DISTINCT prdt_type_name) > 1
ORDER BY product_count DESC;

-- 实际持仓数据中的产品一级分类分布
SELECT
    p.up_prdt_type_name,
    COUNT(*) AS holding_rows,
    COUNT(DISTINCT h.pty_id) AS customer_count,
    COUNT(DISTINCT h.prdt_id) AS product_count,
    SUM(COALESCE(h.mkt_val, 0)) AS total_market_value
FROM dwd_cust_hold_d h
JOIN dim_product p
    ON h.prdt_id = p.prdt_id
GROUP BY p.up_prdt_type_name
ORDER BY holding_rows DESC;

-- 实际交易数据中的产品一级分类分布
SELECT
    p.up_prdt_type_name,
    COUNT(*) AS transaction_rows,
    COUNT(DISTINCT t.pty_id) AS customer_count,
    COUNT(DISTINCT t.prdt_id) AS product_count,
    SUM(
        COALESCE(t.buy_amt, 0)
        + COALESCE(t.sell_amt, 0)
    ) AS total_trade_amount
FROM dwd_cust_tran_d t
JOIN dim_product p
    ON t.prdt_id = p.prdt_id
GROUP BY p.up_prdt_type_name
ORDER BY transaction_rows DESC;