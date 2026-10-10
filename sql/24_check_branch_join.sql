USE agentic_marketing;

SELECT COUNT(*) AS branch_unmatched
FROM ads_cust_info_d c
LEFT JOIN dim_branch b
    ON c.org_id = b.org_id
WHERE b.org_id IS NULL;