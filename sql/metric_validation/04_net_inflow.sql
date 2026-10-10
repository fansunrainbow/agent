USE agentic_marketing;

SELECT
    pty_id,
    SUM(
        COALESCE(cash_in, 0)
        + COALESCE(tran_in, 0)
        + COALESCE(assign_in, 0)
        - COALESCE(cash_out, 0)
        - COALESCE(tran_out, 0)
        - COALESCE(assign_out, 0)
    ) AS net_inflow
FROM dws_cust_fin_d
WHERE data_dt BETWEEN '20260105' AND '20260331'
GROUP BY pty_id
ORDER BY net_inflow DESC
LIMIT 20;