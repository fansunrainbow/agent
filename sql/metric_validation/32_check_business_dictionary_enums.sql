USE agentic_marketing;

-- 1. 客户等级
SELECT DISTINCT cust_lvl_cd
FROM ads_cust_info_d
ORDER BY cust_lvl_cd;

-- 2. 性别
SELECT DISTINCT gender_cd
FROM ads_cust_info_d
ORDER BY gender_cd;

-- 3. 学历
SELECT DISTINCT edu_cd
FROM ads_cust_info_d
ORDER BY edu_cd;

-- 4. 客户状态
SELECT DISTINCT cust_status
FROM ads_cust_info_d
ORDER BY cust_status;

-- 5. 客户类型
SELECT DISTINCT cust_type
FROM ads_cust_info_d
ORDER BY cust_type;

-- 6. 账户来源
SELECT DISTINCT sys_source
FROM dwd_cust_hold_d
ORDER BY sys_source;

-- 7. 产品一级分类
SELECT DISTINCT up_prdt_type_name
FROM dim_product
ORDER BY up_prdt_type_name;