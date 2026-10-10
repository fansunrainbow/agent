USE agentic_marketing;

SELECT
    pty_id,
    data_dt,
    COUNT(*) AS cnt
FROM dws_cust_aset_d
GROUP BY
    pty_id,
    data_dt
HAVING COUNT(*) > 1
LIMIT 20;

SELECT
    pty_id,
    data_dt,
    prdt_id,
    sys_source,
    ccy,
    COUNT(*) AS cnt
FROM dwd_cust_hold_d
GROUP BY
    pty_id,
    data_dt,
    prdt_id,
    sys_source,
    ccy
HAVING COUNT(*) > 1
LIMIT 20;

SELECT
    pty_id,
    data_dt,
    prdt_id,
    sys_source,
    ccy,
    COUNT(*) AS cnt
FROM dwd_cust_tran_d
GROUP BY
    pty_id,
    data_dt,
    prdt_id,
    sys_source,
    ccy
HAVING COUNT(*) > 1
LIMIT 20;
SELECT
    pty_id,
    data_dt,
    sys_source,
    COUNT(*) AS cnt
FROM dws_cust_fin_d
GROUP BY
    pty_id,
    data_dt,
    sys_source
HAVING COUNT(*) > 1
LIMIT 20;