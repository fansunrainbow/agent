USE agentic_marketing;

SELECT
    up_prdt_type_id,
    up_prdt_type_name,
    COUNT(*) AS product_count
FROM dim_product
GROUP BY
    up_prdt_type_id,
    up_prdt_type_name
ORDER BY product_count DESC;
SELECT
    prdt_type_id,
    prdt_type_name,
    up_prdt_type_id,
    up_prdt_type_name,
    COUNT(*) AS product_count
FROM dim_product
GROUP BY
    prdt_type_id,
    prdt_type_name,
    up_prdt_type_id,
    up_prdt_type_name
ORDER BY
    up_prdt_type_name,
    product_count DESC;