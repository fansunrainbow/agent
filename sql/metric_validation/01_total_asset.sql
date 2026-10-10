USE agentic_marketing;

SELECT
    pty_id,
    data_dt,
    nm_tot_aset,
    fc_pur_aset,
    COALESCE(nm_tot_aset, 0)
    + COALESCE(fc_pur_aset, 0) AS total_asset
FROM dws_cust_aset_d
ORDER BY data_dt, pty_id
LIMIT 20;