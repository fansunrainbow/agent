USE agentic_marketing;

SELECT
    pty_id,
    SUM(
        COALESCE(buy_amt, 0)
        + COALESCE(sell_amt, 0)
    ) AS trade_amount
FROM dwd_cust_tran_d
WHERE data_dt BETWEEN '20260105' AND '20260331'
GROUP BY pty_id
ORDER BY trade_amount DESC
LIMIT 20;