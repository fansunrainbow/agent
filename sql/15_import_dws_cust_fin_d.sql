USE agentic_marketing;

LOAD DATA LOCAL INFILE
'dws_cust_fin_d_202606021050.csv'
INTO TABLE dws_cust_fin_d
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ','
OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\r\n'
IGNORE 1 LINES
(
    data_dt,
    pty_id,
    sys_source,
    cash_in,
    cash_out,
    tran_in,
    tran_out,
    assign_in,
    assign_out
);
