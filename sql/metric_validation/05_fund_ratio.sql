USE agentic_marketing;

WITH customer_holding AS (
    SELECT
        h.pty_id,
        h.data_dt,
        SUM(COALESCE(h.mkt_val, 0)) AS total_holding_value,
        SUM(
            CASE
                WHEN p.up_prdt_type_name = '开放式基金'
                THEN COALESCE(h.mkt_val, 0)
                ELSE 0
            END
        ) AS fund_holding_value
    FROM dwd_cust_hold_d h
    JOIN dim_product p
        ON h.prdt_id = p.prdt_id
    GROUP BY
        h.pty_id,
        h.data_dt
)

SELECT
    pty_id,
    data_dt,
    fund_holding_value,
    total_holding_value,
    fund_holding_value
        / NULLIF(total_holding_value, 0) AS fund_holding_ratio
FROM customer_holding
ORDER BY fund_holding_ratio DESC
LIMIT 20;