USE agentic_marketing;

SELECT
    prdt_id,
    prdt_name,
    prdt_type_name,
    up_prdt_type_name
FROM dim_product
WHERE up_prdt_type_name = '股票'
LIMIT 20;