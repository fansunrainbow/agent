USE agentic_marketing;

LOAD DATA LOCAL INFILE
'dwd_cust_tran_d_202606021051.csv'
INTO TABLE dwd_cust_tran_d
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ','
OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\r\n'
IGNORE 1 LINES
(
    data_dt,
    pty_id,
    prdt_id,
    sys_source,
    ccy,
    buy_cnt,
    buy_mnt,
    buy_rake,
    buy_amt,
    buy_fare,
    sell_cnt,
    sell_mnt,
    sell_rake,
    sell_amt,
    sell_fare
);
