USE agentic_marketing;
select count(*)
from ads_cust_info_d a
left join dim_public b on a.edu_cd = b.code and b.code_type_id='600' 
left join dim_public c on a.gender_cd = c.code and c.code_type_id='500'
where b.describe  in ('博士','硕士','学士') and c.describe in ('男')
and a.cust_age>50
