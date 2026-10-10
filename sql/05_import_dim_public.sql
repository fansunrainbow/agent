USE agentic_marketing;

LOAD DATA LOCAL INFILE
'dim_public_202606021050.csv'
INTO TABLE dim_public
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ','
OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\r\n'
IGNORE 1 LINES
(
    code,
    code_type_id,
    `describe`
);
