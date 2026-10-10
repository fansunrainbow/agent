USE agentic_marketing;

LOAD DATA LOCAL INFILE
'dim_product_202606021049.csv'
INTO TABLE dim_product
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ','
OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\r\n'
IGNORE 1 LINES
(
    prdt_id,
    prdt_name,
    sor_prdt_id,
    market_id,
    prdt_type_id,
    prdt_type_name,
    up_prdt_type_id,
    up_prdt_type_name
);
