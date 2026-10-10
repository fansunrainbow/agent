from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

import yaml


sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_GOLD_SHA256 = "602496D8308DD391F4184F2A63A256E6942AF21F3FE3A1D6111987B3EAEB4FCD"
FULL_REPORT_PATH = ROOT / "benchmark/reports/real_db_final/submission_integrity_check.json"
QUICK_REPORT_PATH = ROOT / "benchmark/reports/real_db_final/submission_integrity_check_quick.json"
FORBIDDEN_PACKAGE_NAMES = {".env", "node_modules", ".firecrawl"}
RUNTIME_OUTPUT_NAMES = {
    "dist", "__pycache__", ".pytest_cache", "submission_integrity_check.json",
    "submission_integrity_check_quick.json",
}

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def record(name: str, passed: bool, detail: Any) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "detail": detail}


def run_command(name: str, command: list[str], cwd: Path) -> dict[str, Any]:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        command, cwd=cwd, text=True, encoding="utf-8", errors="replace",
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False, env=environment,
    )
    output = completed.stdout.replace(str(ROOT), "<PROJECT_ROOT>").replace(ROOT.as_posix(), "<PROJECT_ROOT>")
    lines = output.splitlines()
    display_command = [Path(command[0]).name, *command[1:]]
    return record(name, completed.returncode == 0, {
        "command": display_command,
        "exit_code": completed.returncode,
        "output_tail": lines[-12:],
    })


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def verify_submission_package() -> dict[str, Any]:
    package = ROOT / "submission/agentic-marketing-final"
    if not package.is_dir() and (ROOT / "SUBMISSION_CONTENTS.json").is_file():
        package = ROOT
    manifest_path = package / "SUBMISSION_CONTENTS.json"
    if not manifest_path.is_file():
        return record("submission_package_integrity", False, {"error": "SUBMISSION_CONTENTS.json not found"})
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = manifest.get("file_sha256") or {}
    mismatches = []
    missing = []
    for relative, digest in expected.items():
        path = package / relative
        if not path.is_file():
            missing.append(relative)
        elif sha256(path) != digest:
            mismatches.append(relative)
    expected_names = set(expected)
    actual_names = set()
    forbidden = []
    for path in package.rglob("*"):
        relative_parts = path.relative_to(package).parts
        if any(part in RUNTIME_OUTPUT_NAMES for part in relative_parts):
            continue
        if any(part in FORBIDDEN_PACKAGE_NAMES for part in relative_parts):
            forbidden.append(path.relative_to(package).as_posix())
        if not path.is_file():
            continue
        if path.name != "SUBMISSION_CONTENTS.json":
            actual_names.add(path.relative_to(package).as_posix())
    extra = sorted(actual_names - expected_names)
    content_material = "\n".join(f"{name}:{expected[name]}" for name in sorted(expected)).encode("utf-8")
    content_matches = hashlib.sha256(content_material).hexdigest().upper() == manifest.get("content_sha256")
    passed = bool(expected) and not missing and not mismatches and not extra and not forbidden and content_matches
    return record("submission_package_integrity", passed, {
        "package": "<PROJECT_ROOT>" if package == ROOT else "submission/agentic-marketing-final",
        "payload_files": len(expected), "missing": missing, "mismatches": mismatches,
        "extra": extra, "forbidden": forbidden, "content_sha256_matches": content_matches,
    })


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Release integrity check. Never runs the Real DB Benchmark."
    )
    parser.add_argument("--quick", action="store_true", help="Skip full pytest and frontend test/build")
    args = parser.parse_args()
    checks: list[dict[str, Any]] = []

    gold = ROOT / "benchmark/datasets/real_db_gold.jsonl"
    digest = hashlib.sha256(gold.read_bytes()).hexdigest().upper()
    cases = [json.loads(line) for line in gold.read_text(encoding="utf-8").splitlines() if line.strip()]
    checks.append(record("frozen_gold", digest == EXPECTED_GOLD_SHA256 and len(cases) == 40 and all(x.get("review_status") == "reviewed" for x in cases), {
        "sha256": digest, "case_count": len(cases),
        "reviewed_count": sum(x.get("review_status") == "reviewed" for x in cases),
    }))

    metadata_files = sorted((ROOT / "metadata").glob("*.yaml"))
    metadata_errors = []
    metadata_values: dict[str, Any] = {}
    for path in metadata_files:
        try:
            metadata_values[path.name] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception as exc:  # release checker must report all files
            metadata_errors.append({"file": path.name, "error": type(exc).__name__})
    checks.append(record("metadata_yaml", bool(metadata_files) and not metadata_errors, {
        "file_count": len(metadata_files), "errors": metadata_errors,
    }))
    checks.append(record("metadata_contracts", bool(metadata_values.get("metrics.yaml", {}).get("metrics")) and bool(metadata_values.get("business_dictionary.yaml", {}).get("dictionary")), {
        "metrics": len(metadata_values.get("metrics.yaml", {}).get("metrics", {})),
        "dictionary_entries": len(metadata_values.get("business_dictionary.yaml", {}).get("dictionary", {})),
    }))

    import_errors = []
    for module in ("agent.orchestrator", "query_plan.models", "guardrail.sql_generator", "guardrail.execution_manager", "marketing.tools", "webapp.api"):
        try:
            importlib.import_module(module)
        except Exception as exc:
            import_errors.append({"module": module, "error": f"{type(exc).__name__}: {exc}"})
    checks.append(record("backend_imports", not import_errors, {"errors": import_errors}))

    try:
        from agent.orchestrator import AgentOrchestrator
        from guardrail.execution_manager import ExecutionManager
        from guardrail.sql_generator import SQLGenerator

        state = AgentOrchestrator().run("南京客户有多少？")
        artifact = SQLGenerator().generate(state.query_id, state.query_plan, state.validation_result)
        dry = ExecutionManager().dry_run(artifact)
        checks.append(record("query_plan_and_guardrail", state.status.value == "ready" and dry.status == "validated", {
            "agent_status": state.status.value, "guardrail_status": dry.status,
            "parameterized": bool(artifact.params) and ":p" in artifact.sql,
        }))
    except Exception as exc:
        checks.append(record("query_plan_and_guardrail", False, {"error": f"{type(exc).__name__}: {exc}"}))

    required_reports = [
        "second_frozen_benchmark_report.md", "second_frozen_benchmark_report.json",
        "second_frozen_failure_cases.jsonl", "second_frozen_result_comparison.jsonl",
        "second_frozen_latency_report.json", "benchmark_delta_report.json",
        "frontend_real_db_e2e.json",
    ]
    report_dir = ROOT / "benchmark/reports/real_db_final"
    missing = [name for name in required_reports if not (report_dir / name).is_file()]
    checks.append(record("formal_reports", not missing, {"missing": missing}))

    second = json.loads((report_dir / "second_frozen_benchmark_report.json").read_text(encoding="utf-8"))
    checks.append(record("acceptance_status", second.get("agent_final_ready") == "YES" and second.get("final_execution_accuracy", {}).get("accuracy") == 0.9, {
        "accuracy": second.get("final_execution_accuracy", {}).get("accuracy"),
        "agent_final_ready": second.get("agent_final_ready"),
    }))

    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    checks.append(record("env_exclusion", ".env" in {line.strip() for line in gitignore}, {"env_file_exists_locally": (ROOT / ".env").exists(), "env_is_ignored": True}))
    checks.append(verify_submission_package())

    if not args.quick:
        temp_name = "release_verify_tmp_" + datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_dir = report_dir / temp_name
        try:
            checks.append(run_command("python_tests", [
                sys.executable, "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider",
                "--basetemp", f"benchmark/reports/real_db_final/{temp_name}",
            ], ROOT))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
        npm = shutil.which("npm")
        if npm:
            checks.append(run_command("frontend_tests", [npm, "test", "--", "--run"], ROOT / "frontend"))
            checks.append(run_command("frontend_build", [npm, "run", "build"], ROOT / "frontend"))
        else:
            checks.append(record("frontend_tests", False, {"error": "npm not found"}))
            checks.append(record("frontend_build", False, {"error": "npm not found"}))

    passed = all(item["passed"] for item in checks)
    payload = {
        "status": "PASS" if passed else "FAIL",
        "generated_at": datetime.now().astimezone().isoformat(),
        "real_db_benchmark_executed": False,
        "mode": "quick" if args.quick else "full",
        "checks": checks,
    }
    report_path = QUICK_REPORT_PATH if args.quick else FULL_REPORT_PATH
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
