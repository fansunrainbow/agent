USE agentic_marketing;

SELECT
    a.pty_id,
    a.name,
    a.edu_cd,
    d.`describe` AS education_name
FROM ads_cust_info_d a
LEFT JOIN dim_public d
    ON a.edu_cd = d.code
    AND d.code_type_id = '600'
WHERE a.edu_cd IN (
    '6000004',
    '6000003',
    '6000002'
)
LIMIT 20;