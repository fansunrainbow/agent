from __future__ import annotations

import pytest

from guardrail.sql_validator import SQLValidator


@pytest.mark.parametrize("sql", [
    "DELETE FROM ads_cust_info_d",
    "UPDATE ads_cust_info_d SET city_name = :p1",
    "DROP TABLE ads_cust_info_d",
    "SELECT c.pty_id FROM ads_cust_info_d AS c; DROP TABLE dim_product",
    "SELECT SLEEP(:p1) FROM ads_cust_info_d AS c",
    "SELECT * FROM ads_cust_info_d AS c",
])
def test_dangerous_sql_is_blocked(sql):
    report = SQLValidator().validate(sql)
    assert not report.allowed
    assert report.issues


def test_schema_hallucinated_table_is_blocked():
    report = SQLValidator().validate("SELECT g.pty_id FROM ghost_customer AS g")
    assert not report.allowed
    assert "UNKNOWN_TABLE" in {item.code for item in report.issues}


def test_schema_hallucinated_column_is_blocked():
    report = SQLValidator().validate("SELECT c.ghost_col FROM ads_cust_info_d AS c")
    assert not report.allowed
    assert "UNKNOWN_COLUMN" in {item.code for item in report.issues}


def test_unqualified_hallucinated_column_is_blocked():
    report = SQLValidator().validate("SELECT ghost_col FROM ads_cust_info_d AS c")
    assert not report.allowed
    assert "UNKNOWN_COLUMN" in {item.code for item in report.issues}


def test_illegal_join_condition_is_blocked():
    sql = "SELECT c.pty_id FROM ads_cust_info_d AS c JOIN dws_cust_aset_d AS a ON c.pty_id = a.data_dt WHERE a.data_dt = :p1"
    report = SQLValidator().validate(sql)
    assert not report.allowed
    assert "INVALID_JOIN_CONDITION" in {item.code for item in report.issues}


def test_fact_scan_without_time_is_blocked():
    report = SQLValidator().validate("SELECT t.pty_id FROM dwd_cust_tran_d AS t")
    assert not report.allowed
    assert "FACT_TIME_FILTER_REQUIRED" in {item.code for item in report.issues}


def test_unparameterized_business_value_is_blocked():
    report = SQLValidator().validate("SELECT c.pty_id FROM ads_cust_info_d AS c WHERE c.city_name = '南京'")
    assert not report.allowed
    assert "UNPARAMETERIZED_LITERAL" in {item.code for item in report.issues}
