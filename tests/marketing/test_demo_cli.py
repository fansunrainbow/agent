from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "marketing" / "fixtures" / "stage6_safe_result.json"


def test_marketing_demo_outputs_full_chain_and_safety_refusals():
    process = subprocess.run(
        [
            sys.executable, str(ROOT / "scripts" / "run_marketing_demo.py"),
            "--input", str(FIXTURE), "--allow-demo-fixture",
            "--attribute", "risk_preference", "--specific-product", "某具体基金",
        ],
        cwd=ROOT, text=True, encoding="utf-8", capture_output=True, check=True,
    )
    data = json.loads(process.stdout)
    assert data["customers"][0]["customer_360"]
    assert data["segment"]["segment_id"] == "high_asset_low_fund"
    assert data["cohort_analysis"]["customer_count"] == 1
    assert data["attribute_check"][0]["code"] == "UNSUPPORTED_CUSTOMER_ATTRIBUTE"
    assert data["specific_product_request"]["code"] == "SUITABILITY_DATA_REQUIRED"


def test_demo_fixture_requires_explicit_opt_in():
    process = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run_marketing_demo.py"), "--input", str(FIXTURE)],
        cwd=ROOT, text=True, encoding="utf-8", capture_output=True,
    )
    assert process.returncode != 0
    assert "Refusing synthetic fixture" in process.stderr
