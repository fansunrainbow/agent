USE agentic_marketing;

SELECT
    pty_id,
    name,
    cust_lvl_cd
FROM ads_cust_info_d
WHERE cust_lvl_cd = '1000001'
LIMIT 20;