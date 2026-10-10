from __future__ import annotations

import argparse
from decimal import Decimal
import json
from pathlib import Path
import sys
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database import DatabaseConfig, create_readonly_connection


Q1 = "BETWEEN '20260101' AND '20260331'"


def case(case_id: str, query: str, difficulty: str, intent: str, result_type: str, sql: str, notes: str) -> dict[str, Any]:
    comparison = "grouped" if result_type == "time_series" else result_type
    return {
        "case_id": case_id,
        "query": query,
        "difficulty": difficulty,
        "intent": intent,
        "expected_result_type": result_type,
        "comparison_kind": comparison,
        "gold_source": "independent_query",
        "review_status": "pending",
        "notes": notes,
        "gold_sql": " ".join(sql.split()),
    }


CASES = [
    case("RDB_S01", "南京客户有多少？", "simple", "metric_query", "scalar",
         "SELECT COUNT(DISTINCT pty_id) AS customer_count FROM ads_cust_info_d WHERE city_name='南京市'",
         "当前客户快照；南京使用真实值南京市。"),
    case("RDB_S02", "苏州客户有多少？", "simple", "metric_query", "scalar",
         "SELECT COUNT(DISTINCT pty_id) AS customer_count FROM ads_cust_info_d WHERE city_name='苏州市'",
         "当前客户快照；苏州使用真实值苏州市。"),
    case("RDB_S03", "女性客户有多少？", "simple", "metric_query", "scalar",
         "SELECT COUNT(DISTINCT pty_id) AS customer_count FROM ads_cust_info_d WHERE gender_cd='5000003'",
         "5000003 由真实公共字典映射为女性。"),
    case("RDB_S04", "钻石客户有多少？", "simple", "metric_query", "scalar",
         "SELECT COUNT(DISTINCT pty_id) AS customer_count FROM ads_cust_info_d WHERE cust_lvl_cd='1000001'",
         "1000001 为真实钻石客户等级代码。"),
    case("RDB_S05", "重庆******营业部客户有多少？", "simple", "metric_query", "scalar",
         "SELECT COUNT(DISTINCT pty_id) AS customer_count FROM ads_cust_info_d WHERE org_id='XX00000008'",
         "Gold 使用人工核对后的唯一机构 ID，查询保留数据脱敏名称。"),
    case("RDB_S06", "2026年Q1客户日均资产是多少？", "simple", "metric_query", "scalar",
         "SELECT AVG(customer_avg) AS average_total_asset FROM (SELECT pty_id,SUM(COALESCE(nm_tot_aset,0)+COALESCE(fc_pur_aset,0))/90.0 customer_avg FROM dws_cust_aset_d WHERE data_dt BETWEEN '20260101' AND '20260331' GROUP BY pty_id) x",
         "日均资产按 Q1 90 个自然日计算，再对客户取平均。"),
    case("RDB_S07", "2026年Q1客户交易额是多少？", "simple", "metric_query", "scalar",
         "SELECT SUM(COALESCE(buy_amt,0)+COALESCE(sell_amt,0)) AS trade_amount FROM dwd_cust_tran_d WHERE data_dt BETWEEN '20260101' AND '20260331'",
         "买入金额加卖出金额。"),
    case("RDB_S08", "2026年Q1客户交易次数是多少？", "simple", "metric_query", "scalar",
         "SELECT SUM(COALESCE(buy_cnt,0)+COALESCE(sell_cnt,0)) AS trade_count FROM dwd_cust_tran_d WHERE data_dt BETWEEN '20260101' AND '20260331'",
         "买入次数加卖出次数。"),
    case("RDB_S09", "2026年Q1客户净流入是多少？", "simple", "metric_query", "scalar",
         "SELECT SUM(COALESCE(cash_in,0)+COALESCE(tran_in,0)+COALESCE(assign_in,0)-COALESCE(cash_out,0)-COALESCE(tran_out,0)-COALESCE(assign_out,0)) AS net_inflow FROM dws_cust_fin_d WHERE data_dt BETWEEN '20260101' AND '20260331'",
         "所有真实流入项减所有真实流出项。"),
    case("RDB_S10", "2026年Q1客户总流入是多少？", "simple", "metric_query", "scalar",
         "SELECT SUM(COALESCE(cash_in,0)+COALESCE(tran_in,0)+COALESCE(assign_in,0)) AS total_inflow FROM dws_cust_fin_d WHERE data_dt BETWEEN '20260101' AND '20260331'",
         "现金、证券、指定流入合计。"),
    case("RDB_S11", "2026年Q1客户总流出是多少？", "simple", "metric_query", "scalar",
         "SELECT SUM(COALESCE(cash_out,0)+COALESCE(tran_out,0)+COALESCE(assign_out,0)) AS total_outflow FROM dws_cust_fin_d WHERE data_dt BETWEEN '20260101' AND '20260331'",
         "现金、证券、指定流出合计。"),
    case("RDB_S12", "2026年Q1末客户现金资产是多少？", "simple", "metric_query", "scalar",
         "SELECT SUM(COALESCE(nm_bal,0)+COALESCE(fc_bal,0)) AS cash_asset FROM dws_cust_aset_d WHERE data_dt='20260331'",
         "Q1 期末使用 2026-03-31 快照。"),

    case("RDB_M01", "2026年Q1南京客户平均日均资产是多少？", "medium", "metric_query", "scalar",
         "SELECT AVG(customer_avg) AS average_total_asset FROM (SELECT a.pty_id,SUM(COALESCE(a.nm_tot_aset,0)+COALESCE(a.fc_pur_aset,0))/90.0 customer_avg FROM dws_cust_aset_d a JOIN ads_cust_info_d c ON c.pty_id=a.pty_id WHERE a.data_dt BETWEEN '20260101' AND '20260331' AND c.city_name='南京市' GROUP BY a.pty_id) x",
         "客户属性采用当前快照，资产为 Q1 日历日均。"),
    case("RDB_M02", "南京女性客户有多少？", "medium", "metric_query", "scalar",
         "SELECT COUNT(DISTINCT pty_id) AS customer_count FROM ads_cust_info_d WHERE city_name='南京市' AND gender_cd='5000003'",
         "双维度等值过滤。"),
    case("RDB_M03", "2026年Q1日均资产超过500万的客户有哪些？", "medium", "customer_selection", "set",
         "SELECT pty_id,SUM(COALESCE(nm_tot_aset,0)+COALESCE(fc_pur_aset,0))/90.0 AS average_total_asset FROM dws_cust_aset_d WHERE data_dt BETWEEN '20260101' AND '20260331' GROUP BY pty_id HAVING average_total_asset>5000000 ORDER BY pty_id",
         "Set 比较忽略行顺序；保留筛选指标。"),
    case("RDB_M04", "2026年Q1交易额超过1000万的客户有哪些？", "medium", "customer_selection", "set",
         "SELECT pty_id,SUM(COALESCE(buy_amt,0)+COALESCE(sell_amt,0)) AS trade_amount FROM dwd_cust_tran_d WHERE data_dt BETWEEN '20260101' AND '20260331' GROUP BY pty_id HAVING trade_amount>10000000 ORDER BY pty_id",
         "按客户聚合后应用 gt。"),
    case("RDB_M05", "2026年Q1净流入超过100万的客户有哪些？", "medium", "customer_selection", "set",
         "SELECT pty_id,SUM(COALESCE(cash_in,0)+COALESCE(tran_in,0)+COALESCE(assign_in,0)-COALESCE(cash_out,0)-COALESCE(tran_out,0)-COALESCE(assign_out,0)) AS net_inflow FROM dws_cust_fin_d WHERE data_dt BETWEEN '20260101' AND '20260331' GROUP BY pty_id HAVING net_inflow>1000000 ORDER BY pty_id",
         "按客户聚合后应用 gt。"),
    case("RDB_M06", "2026年Q1南京持有股票类产品的客户有哪些？", "medium", "customer_selection", "set",
         "SELECT DISTINCT c.pty_id FROM ads_cust_info_d c JOIN dwd_cust_hold_d h ON h.pty_id=c.pty_id WHERE c.city_name='南京市' AND h.data_dt BETWEEN '20260101' AND '20260331' AND h.prdt_id IN (SELECT DISTINCT prdt_id FROM dim_product WHERE up_prdt_type_name='股票') ORDER BY c.pty_id",
         "类别 EXISTS；产品分类由真实一级分类名称验证。"),
    case("RDB_M07", "2026年Q1南京没有持有股票类产品的客户有哪些？", "medium", "customer_selection", "set",
         "SELECT c.pty_id FROM ads_cust_info_d c WHERE c.city_name='南京市' AND NOT EXISTS (SELECT 1 FROM dwd_cust_hold_d h WHERE h.pty_id=c.pty_id AND h.data_dt BETWEEN '20260101' AND '20260331' AND h.prdt_id IN (SELECT DISTINCT prdt_id FROM dim_product WHERE up_prdt_type_name='股票')) ORDER BY c.pty_id",
         "类别 NOT EXISTS，不以持仓市值阈值替代。"),
    case("RDB_M08", "2026年Q1贵州茅台持仓市值是多少？", "medium", "metric_query", "scalar",
         "SELECT SUM(COALESCE(mkt_val,0)) AS holding_market_value FROM dwd_cust_hold_d WHERE data_dt BETWEEN '20260101' AND '20260331' AND prdt_id='9900269727'",
         "具体产品使用独立核对的真实产品 ID。"),
    case("RDB_M09", "按城市统计客户数量", "medium", "group_analysis", "grouped",
         "SELECT city_name AS city,COUNT(DISTINCT pty_id) AS customer_count FROM ads_cust_info_d GROUP BY city_name ORDER BY city_name",
         "Grouped 比较忽略组顺序。"),
    case("RDB_M10", "2026年Q1按客户等级统计平均日均资产", "medium", "group_analysis", "grouped",
         "WITH a AS (SELECT pty_id,SUM(COALESCE(nm_tot_aset,0)+COALESCE(fc_pur_aset,0))/90.0 average_total_asset FROM dws_cust_aset_d WHERE data_dt BETWEEN '20260101' AND '20260331' GROUP BY pty_id) SELECT c.cust_lvl_cd AS customer_level,AVG(a.average_total_asset) AS average_total_asset FROM ads_cust_info_d c JOIN a ON a.pty_id=c.pty_id GROUP BY c.cust_lvl_cd ORDER BY c.cust_lvl_cd",
         "先到客户粒度，再按等级求平均，防止事实行放大。"),
    case("RDB_M11", "2026年Q1日均资产最高的前20名客户", "medium", "ranking", "ranking",
         "SELECT pty_id,SUM(COALESCE(nm_tot_aset,0)+COALESCE(fc_pur_aset,0))/90.0 AS average_total_asset FROM dws_cust_aset_d WHERE data_dt BETWEEN '20260101' AND '20260331' GROUP BY pty_id ORDER BY average_total_asset DESC,pty_id ASC LIMIT 20",
         "Ranking 要求 Top-20 顺序；pty_id 作为确定性并列键。"),
    case("RDB_M12", "2026年Q1交易额最高的前20名客户", "medium", "ranking", "ranking",
         "SELECT pty_id,SUM(COALESCE(buy_amt,0)+COALESCE(sell_amt,0)) AS trade_amount FROM dwd_cust_tran_d WHERE data_dt BETWEEN '20260101' AND '20260331' GROUP BY pty_id ORDER BY trade_amount DESC,pty_id ASC LIMIT 20",
         "Ranking 要求 Top-20 顺序；pty_id 作为确定性并列键。"),
    case("RDB_M13", "2026年Q1按月查看净流入趋势", "medium", "trend_analysis", "time_series",
         "SELECT SUBSTRING(data_dt,1,6) AS month,SUM(COALESCE(cash_in,0)+COALESCE(tran_in,0)+COALESCE(assign_in,0)-COALESCE(cash_out,0)-COALESCE(tran_out,0)-COALESCE(assign_out,0)) AS net_inflow FROM dws_cust_fin_d WHERE data_dt BETWEEN '20260101' AND '20260331' GROUP BY SUBSTRING(data_dt,1,6) ORDER BY month",
         "Time Series 按 YYYYMM bucket 比较。"),
    case("RDB_M14", "2026年Q1客户日均资产和交易额是多少？", "medium", "metric_query", "grouped",
         "WITH a AS (SELECT AVG(v) average_total_asset FROM (SELECT pty_id,SUM(COALESCE(nm_tot_aset,0)+COALESCE(fc_pur_aset,0))/90.0 v FROM dws_cust_aset_d WHERE data_dt BETWEEN '20260101' AND '20260331' GROUP BY pty_id) q),t AS (SELECT SUM(COALESCE(buy_amt,0)+COALESCE(sell_amt,0)) trade_amount FROM dwd_cust_tran_d WHERE data_dt BETWEEN '20260101' AND '20260331') SELECT a.average_total_asset,t.trade_amount FROM a CROSS JOIN t",
         "单行多指标对象，Gold SQL 独立预聚合两个事实源。"),
    case("RDB_M15", "2026年Q1股票产品交易额是多少？", "medium", "metric_query", "scalar",
         "SELECT SUM(COALESCE(t.buy_amt,0)+COALESCE(t.sell_amt,0)) AS trade_amount FROM dwd_cust_tran_d t WHERE t.data_dt BETWEEN '20260101' AND '20260331' AND t.prdt_id IN (SELECT DISTINCT prdt_id FROM dim_product WHERE up_prdt_type_name='股票')",
         "产品类别与交易指标；使用独立半连接。"),
    case("RDB_M16", "2026年Q1北京分公司客户期末资产是多少？", "medium", "metric_query", "scalar",
         "SELECT SUM(COALESCE(a.nm_tot_aset,0)+COALESCE(a.fc_pur_aset,0)) AS period_end_asset FROM dws_cust_aset_d a JOIN ads_cust_info_d c ON c.pty_id=a.pty_id JOIN dim_branch b ON b.org_id=c.org_id WHERE a.data_dt='20260331' AND b.up_org_id='XX00000112'",
         "分公司层级使用真实 up_org_id；期末为 2026-03-31。"),

    case("RDB_C01", "2026年Q1南京女性客户中基金持仓占比低于10%且净流入为正的客户", "complex", "customer_selection", "set",
         "WITH hp AS (SELECT h.pty_id,SUM(CASE WHEN h.prdt_id IN (SELECT DISTINCT prdt_id FROM dim_product WHERE up_prdt_type_name='开放式基金') THEN COALESCE(h.mkt_val,0) ELSE 0 END)/NULLIF(SUM(COALESCE(h.mkt_val,0)),0) fund_holding_ratio FROM dwd_cust_hold_d h WHERE h.data_dt BETWEEN '20260101' AND '20260331' GROUP BY h.pty_id),nf AS (SELECT pty_id,SUM(COALESCE(cash_in,0)+COALESCE(tran_in,0)+COALESCE(assign_in,0)-COALESCE(cash_out,0)-COALESCE(tran_out,0)-COALESCE(assign_out,0)) net_inflow FROM dws_cust_fin_d WHERE data_dt BETWEEN '20260101' AND '20260331' GROUP BY pty_id) SELECT c.pty_id,hp.fund_holding_ratio,nf.net_inflow FROM ads_cust_info_d c JOIN hp ON hp.pty_id=c.pty_id JOIN nf ON nf.pty_id=c.pty_id WHERE c.city_name='南京市' AND c.gender_cd='5000003' AND hp.fund_holding_ratio<0.1 AND nf.net_inflow>0 ORDER BY c.pty_id",
         "复杂多事实条件；两个事实源先独立聚合。"),
    case("RDB_C02", "2026年Q1日均资产超过500万且股票交易额超过100万的客户", "complex", "customer_selection", "set",
         "WITH a AS (SELECT pty_id,SUM(COALESCE(nm_tot_aset,0)+COALESCE(fc_pur_aset,0))/90.0 average_total_asset FROM dws_cust_aset_d WHERE data_dt BETWEEN '20260101' AND '20260331' GROUP BY pty_id),t AS (SELECT pty_id,SUM(COALESCE(buy_amt,0)+COALESCE(sell_amt,0)) stock_trade_amount FROM dwd_cust_tran_d WHERE data_dt BETWEEN '20260101' AND '20260331' AND prdt_id IN (SELECT DISTINCT prdt_id FROM dim_product WHERE up_prdt_type_name='股票') GROUP BY pty_id) SELECT a.pty_id,a.average_total_asset,t.stock_trade_amount FROM a JOIN t ON t.pty_id=a.pty_id WHERE a.average_total_asset>5000000 AND t.stock_trade_amount>1000000 ORDER BY a.pty_id",
         "资产与交易事实分别聚合，避免 fact-to-fact 放大。"),
    case("RDB_C03", "2026年Q1钻石客户中净流出且资产下降的客户", "complex", "customer_selection", "set",
         "WITH nf AS (SELECT pty_id,SUM(COALESCE(cash_in,0)+COALESCE(tran_in,0)+COALESCE(assign_in,0)-COALESCE(cash_out,0)-COALESCE(tran_out,0)-COALESCE(assign_out,0)) net_inflow FROM dws_cust_fin_d WHERE data_dt BETWEEN '20260101' AND '20260331' GROUP BY pty_id),ac AS (SELECT pty_id,MAX(CASE WHEN data_dt='20260331' THEN COALESCE(nm_tot_aset,0)+COALESCE(fc_pur_aset,0) END)-MAX(CASE WHEN data_dt='20260101' THEN COALESCE(nm_tot_aset,0)+COALESCE(fc_pur_aset,0) END) asset_change FROM dws_cust_aset_d WHERE data_dt IN ('20260101','20260331') GROUP BY pty_id) SELECT c.pty_id,nf.net_inflow,ac.asset_change FROM ads_cust_info_d c JOIN nf ON nf.pty_id=c.pty_id JOIN ac ON ac.pty_id=c.pty_id WHERE c.cust_lvl_cd='1000001' AND nf.net_inflow<0 AND ac.asset_change<0 ORDER BY c.pty_id",
         "等级快照 + 两个期间指标，独立预聚合。"),
    case("RDB_C04", "2026年Q1南京客户日均资产和交易额是多少？", "complex", "metric_query", "grouped",
         "WITH city AS (SELECT pty_id FROM ads_cust_info_d WHERE city_name='南京市'),a AS (SELECT x.pty_id,SUM(COALESCE(x.nm_tot_aset,0)+COALESCE(x.fc_pur_aset,0))/90.0 v FROM dws_cust_aset_d x JOIN city c ON c.pty_id=x.pty_id WHERE x.data_dt BETWEEN '20260101' AND '20260331' GROUP BY x.pty_id),aa AS (SELECT AVG(v) average_total_asset FROM a),t AS (SELECT SUM(COALESCE(x.buy_amt,0)+COALESCE(x.sell_amt,0)) trade_amount FROM dwd_cust_tran_d x JOIN city c ON c.pty_id=x.pty_id WHERE x.data_dt BETWEEN '20260101' AND '20260331') SELECT aa.average_total_asset,t.trade_amount FROM aa CROSS JOIN t",
         "城市过滤下的多事实双指标。"),
    case("RDB_C05", "2026年Q1北京分公司客户股票交易额是多少？", "complex", "metric_query", "scalar",
         "SELECT SUM(COALESCE(t.buy_amt,0)+COALESCE(t.sell_amt,0)) AS stock_trade_amount FROM dwd_cust_tran_d t JOIN ads_cust_info_d c ON c.pty_id=t.pty_id JOIN dim_branch b ON b.org_id=c.org_id WHERE t.data_dt BETWEEN '20260101' AND '20260331' AND b.up_org_id='XX00000112' AND t.prdt_id IN (SELECT DISTINCT prdt_id FROM dim_product WHERE up_prdt_type_name='股票')",
         "Branch hierarchy + product category + metric。"),
    case("RDB_C06", "2026年Q1南京女性钻石客户中，排除休眠和销户且净流入为正的客户", "complex", "customer_selection", "set",
         "WITH nf AS (SELECT pty_id,SUM(COALESCE(cash_in,0)+COALESCE(tran_in,0)+COALESCE(assign_in,0)-COALESCE(cash_out,0)-COALESCE(tran_out,0)-COALESCE(assign_out,0)) net_inflow FROM dws_cust_fin_d WHERE data_dt BETWEEN '20260101' AND '20260331' GROUP BY pty_id) SELECT c.pty_id,nf.net_inflow FROM ads_cust_info_d c JOIN nf ON nf.pty_id=c.pty_id WHERE c.city_name='南京市' AND c.gender_cd='5000003' AND c.cust_lvl_cd='1000001' AND c.cust_status NOT IN ('2000004','2000005') AND nf.net_inflow>0 ORDER BY c.pty_id",
         "多条件 AND，包含 NOT IN。"),
    case("RDB_C07", "城市属于南京、苏州之一且年龄40岁及以下的女性客户有多少？", "complex", "metric_query", "scalar",
         "SELECT COUNT(DISTINCT pty_id) AS customer_count FROM ads_cust_info_d WHERE city_name IN ('南京市','苏州市') AND cust_age<=40 AND gender_cd='5000003'",
         "显式 IN + lte + eq。"),
    case("RDB_C08", "2026年Q1南京客户中没有持有贵州茅台的客户", "complex", "customer_selection", "set",
         "SELECT c.pty_id FROM ads_cust_info_d c WHERE c.city_name='南京市' AND NOT EXISTS (SELECT 1 FROM dwd_cust_hold_d h WHERE h.pty_id=c.pty_id AND h.data_dt BETWEEN '20260101' AND '20260331' AND h.prdt_id='9900269727') ORDER BY c.pty_id",
         "具体产品 NOT EXISTS。"),
    case("RDB_C09", "按城市统计客户数，只显示客户数大于2的城市", "complex", "group_analysis", "grouped",
         "SELECT city_name AS city,COUNT(DISTINCT pty_id) AS customer_count FROM ads_cust_info_d GROUP BY city_name HAVING COUNT(DISTINCT pty_id)>2 ORDER BY city_name",
         "Group By + Having。"),
    case("RDB_C10", "2026年Q1南京客户交易额最高的前10名", "complex", "ranking", "ranking",
         "SELECT t.pty_id,SUM(COALESCE(t.buy_amt,0)+COALESCE(t.sell_amt,0)) AS trade_amount FROM dwd_cust_tran_d t JOIN ads_cust_info_d c ON c.pty_id=t.pty_id WHERE t.data_dt BETWEEN '20260101' AND '20260331' AND c.city_name='南京市' GROUP BY t.pty_id ORDER BY trade_amount DESC,t.pty_id ASC LIMIT 10",
         "Filter + Ranking；确定性并列键为 pty_id。"),
    case("RDB_C11", "2026年Q1北京分公司客户日均资产、交易额和净流入是多少？", "complex", "metric_query", "grouped",
         "WITH bc AS (SELECT DISTINCT c.pty_id FROM ads_cust_info_d c JOIN dim_branch b ON b.org_id=c.org_id WHERE b.up_org_id='XX00000112'),a AS (SELECT x.pty_id,SUM(COALESCE(x.nm_tot_aset,0)+COALESCE(x.fc_pur_aset,0))/90.0 v FROM dws_cust_aset_d x JOIN bc ON bc.pty_id=x.pty_id WHERE x.data_dt BETWEEN '20260101' AND '20260331' GROUP BY x.pty_id),aa AS (SELECT AVG(v) average_total_asset FROM a),t AS (SELECT SUM(COALESCE(x.buy_amt,0)+COALESCE(x.sell_amt,0)) trade_amount FROM dwd_cust_tran_d x JOIN bc ON bc.pty_id=x.pty_id WHERE x.data_dt BETWEEN '20260101' AND '20260331'),f AS (SELECT SUM(COALESCE(x.cash_in,0)+COALESCE(x.tran_in,0)+COALESCE(x.assign_in,0)-COALESCE(x.cash_out,0)-COALESCE(x.tran_out,0)-COALESCE(x.assign_out,0)) net_inflow FROM dws_cust_fin_d x JOIN bc ON bc.pty_id=x.pty_id WHERE x.data_dt BETWEEN '20260101' AND '20260331') SELECT aa.average_total_asset,t.trade_amount,f.net_inflow FROM aa CROSS JOIN t CROSS JOIN f",
         "Branch + 三事实指标；每个事实源独立聚合。"),
    case("RDB_C12", "2026年Q1末年龄30到50岁、女性、非休眠且现金资产占比至少20%的客户", "complex", "customer_selection", "set",
         "SELECT c.pty_id,c.cust_age AS age,c.gender_cd AS gender,c.cust_status AS customer_status,(COALESCE(a.nm_bal,0)+COALESCE(a.fc_bal,0))/NULLIF(COALESCE(a.nm_tot_aset,0)+COALESCE(a.fc_pur_aset,0),0) AS cash_asset_ratio FROM ads_cust_info_d c JOIN dws_cust_aset_d a ON a.pty_id=c.pty_id AND a.data_dt='20260331' WHERE c.cust_age BETWEEN 30 AND 50 AND c.gender_cd='5000003' AND c.cust_status<>'2000005' AND (COALESCE(a.nm_bal,0)+COALESCE(a.fc_bal,0))/NULLIF(COALESCE(a.nm_tot_aset,0)+COALESCE(a.fc_pur_aset,0),0)>=0.2 ORDER BY c.pty_id",
         "between + neq + gte；比率使用同一 Q1 期末快照。"),
]


def normalize(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (list, tuple)):
        return [normalize(item) for item in value]
    if isinstance(value, dict):
        return {key: normalize(item) for key, item in value.items()}
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare independently queried Real DB Gold draft rows.")
    parser.add_argument("--difficulty", choices=("simple", "medium", "complex"))
    args = parser.parse_args()
    selected_cases = [item for item in CASES if not args.difficulty or item["difficulty"] == args.difficulty]

    load_dotenv()
    connection = create_readonly_connection(DatabaseConfig.from_env())
    capability = connection.capability_check()
    if not capability.readonly_verified:
        raise SystemExit("read-only capability check failed")
    try:
        for item in selected_cases:
            cursor = connection.raw_connection.cursor()
            cursor.execute(item["gold_sql"])
            columns = [entry[0] for entry in cursor.description or []]
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
            item = dict(item)
            if item["comparison_kind"] == "scalar":
                item["gold_result"] = normalize(next(iter(rows[0].values())) if rows else None)
                item["numeric_tolerance"] = {"absolute": 0.01, "relative": 1e-9}
            else:
                item["gold_result"] = normalize(rows)
            print(json.dumps(item, ensure_ascii=False, separators=(",", ":")))
    finally:
        connection.close()
    print(json.dumps({"case_count": len(selected_cases)}, ensure_ascii=False), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
