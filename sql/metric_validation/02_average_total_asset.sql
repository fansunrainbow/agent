USE agentic_marketing;

SELECT
    pty_id,
    SUM(
        COALESCE(nm_tot_aset, 0)
        + COALESCE(fc_pur_aset, 0)
    ) / 90.0 AS average_total_asset
FROM dws_cust_aset_d
WHERE data_dt BETWEEN '20260101' AND '20260331'
GROUP BY pty_id
ORDER BY average_total_asset DESC
LIMIT 20;