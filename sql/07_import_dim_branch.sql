USE agentic_marketing;

LOAD DATA LOCAL INFILE
'dim_branch_202606021048.csv'
INTO TABLE dim_branch
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ','
OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\r\n'
IGNORE 1 LINES
(
    data_dt,
    org_id,
    org_name,
    up_org_id,
    up_org_name
);
