USE agentic_marketing;

LOAD DATA LOCAL INFILE
'dws_cust_aset_d_202606021051.csv'
INTO TABLE dws_cust_aset_d
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ','
OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\r\n'
IGNORE 1 LINES
(
    data_dt,
    pty_id,
    nm_tot_aset,
    nm_bal,
    fc_pur_aset,
    fc_bal
);
