USE agentic_marketing;

SELECT DISTINCT
    sys_source
FROM dwd_cust_hold_d
WHERE sys_source = 'nm';