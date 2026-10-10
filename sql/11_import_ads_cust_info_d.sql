USE agentic_marketing;

LOAD DATA LOCAL INFILE
'ads_cust_info_d_202606031625.csv'
INTO TABLE ads_cust_info_d
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ','
OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\r\n'
IGNORE 1 LINES
(
    data_dt,
    pty_id,
    sor_pty_id,
    cust_lvl_cd,
    cust_status,
    cust_type,
    prov_name,
    city_name,
    birth_dt,
    cust_age,
    name,
    gender_cd,
    edu_cd,
    prof_cd,
    org_id
);
