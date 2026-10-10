from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import shutil


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "submission/agentic-marketing-final"
STAGING = ROOT / "submission/.agentic-marketing-final.build"
BACKUP = ROOT / "submission/.agentic-marketing-final.backup"
SOURCE_DIRS = (
    "agent", "benchmark", "data", "database", "docs", "frontend", "guardrail",
    "marketing", "metadata", "query_plan", "scripts", "sql", "tests", "webapp",
)
ROOT_FILES = (
    "README.md", "requirements.txt", "constraints.txt", "pytest.ini",
    "EXTERNAL_DATA_REQUIREMENTS.json", ".env.example", ".gitignore",
    "Stage6_Guardrail_完整流程.md", "Stage7_营销能力_完整流程.md", "Stage8_Benchmark_完整流程.md",
    "表描述_MySQL8.sql", "ads_cust_info_d_202606031625.csv", "dim_branch_202606021048.csv",
    "dim_product_202606021049.csv", "dim_public_202606021050.csv",
)
FORBIDDEN_NAMES = {".env", "node_modules", "__pycache__", ".pytest_cache", ".firecrawl", "dist"}
TEXT_SUFFIXES = {".css", ".example", ".html", ".js", ".json", ".jsonl", ".jsx", ".md", ".py", ".sql", ".txt", ".yaml", ".yml"}
SECRET_PATTERNS = {
    "openai_style_key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "aws_access_key": re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
    "assigned_secret": re.compile(r"(?i)\b(?:api[_-]?key|access[_-]?token|secret|password)\b\s*[:=]\s*['\"][^'\"]{8,}['\"]"),
}
MUTABLE_OUTPUTS = {"submission_integrity_check.json", "submission_integrity_check_quick.json"}


def ignored(_: str, names: list[str]) -> set[str]:
    return {
        name for name in names
        if name in FORBIDDEN_NAMES
        or name in MUTABLE_OUTPUTS
        or name.endswith((".pyc", ".pyo"))
        or name.startswith("pytest_tmp")
        or name.startswith("release_verify_tmp")
        or name == "second_frozen_raw"
    }


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a privacy-scanned, content-hashed submission package.")
    parser.add_argument("--replace", action="store_true", help="Atomically replace an existing package after the new package passes checks.")
    args = parser.parse_args()
    resolved_root = ROOT.resolve()
    resolved_target = TARGET.resolve()
    submission_root = (ROOT / "submission").resolve()
    if submission_root not in resolved_target.parents:
        raise SystemExit("Unsafe submission target")
    if TARGET.exists() and not args.replace:
        raise SystemExit(f"Refusing to overwrite existing package: {TARGET}")
    if STAGING.exists() or BACKUP.exists():
        raise SystemExit("Stale package staging/backup directory exists; inspect it before rebuilding.")
    STAGING.mkdir(parents=True)

    for name in SOURCE_DIRS:
        source = ROOT / name
        if source.exists():
            shutil.copytree(source, STAGING / name, ignore=ignored)
    for name in ROOT_FILES:
        source = ROOT / name
        if source.is_file():
            shutil.copy2(source, STAGING / name)

    package_audit_path = STAGING / "benchmark/reports/real_db_final/submission_package_audit.json"
    package_audit_path.parent.mkdir(parents=True, exist_ok=True)
    package_audit_path.write_text(json.dumps({
        "status": "PASS", "generated_at": datetime.now().astimezone().isoformat(),
        "package_path": "<PROJECT_ROOT>", "forbidden_entries": [], "privacy_findings": [],
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    forbidden = []
    privacy_findings = []
    files = []
    total_bytes = 0
    source_root_text = str(ROOT)
    source_root_posix = ROOT.as_posix()
    source_root_json = json.dumps(source_root_text)[1:-1]
    for path in STAGING.rglob("*"):
        if not path.is_file() or path.name in MUTABLE_OUTPUTS:
            continue
        relative = path.relative_to(STAGING).as_posix()
        if path.suffix.lower() in TEXT_SUFFIXES:
            text = path.read_text(encoding="utf-8", errors="replace")
            sanitized = text.replace(source_root_json, "<PROJECT_ROOT>").replace(source_root_text, "<PROJECT_ROOT>").replace(source_root_posix, "<PROJECT_ROOT>")
            if sanitized != text:
                path.write_text(sanitized, encoding="utf-8")
            if re.search(r"(?i)[A-Z]:[\\/]+Users[\\/]+[^\\/]+[\\/]", sanitized):
                privacy_findings.append({"file": relative, "kind": "absolute_user_path"})
            for kind, pattern in SECRET_PATTERNS.items():
                if pattern.search(sanitized):
                    privacy_findings.append({"file": relative, "kind": kind})
        files.append(relative)
        total_bytes += path.stat().st_size
        if any(part in FORBIDDEN_NAMES for part in path.relative_to(STAGING).parts):
            forbidden.append(relative)

    file_hashes = {relative: file_sha256(STAGING / relative) for relative in sorted(files)}
    content_material = "\n".join(f"{name}:{digest}" for name, digest in file_hashes.items()).encode("utf-8")
    content_sha256 = hashlib.sha256(content_material).hexdigest().upper()

    manifest = {
        "release_name": "agentic-marketing-final",
        "generated_at": datetime.now().astimezone().isoformat(),
        "source_root": resolved_root.name,
        "file_count": len(files) + 1,
        "payload_file_count": len(files),
        "total_bytes": total_bytes,
        "payload_total_bytes": total_bytes,
        "content_sha256": content_sha256,
        "file_sha256": file_hashes,
        "forbidden_entries": forbidden,
        "privacy_findings": privacy_findings,
        "excluded": sorted(FORBIDDEN_NAMES | {"pytest_tmp*", "release_verify_tmp*", "second_frozen_raw"}),
        "includes_required_entity_csv": all((STAGING / name).is_file() for name in ROOT_FILES if name.endswith(".csv")),
        "external_fact_data_policy": "controlled_external_competition_data",
        "external_data_manifest": "EXTERNAL_DATA_REQUIREMENTS.json",
    }
    (STAGING / "SUBMISSION_CONTENTS.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    if forbidden or privacy_findings:
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 1

    if TARGET.exists():
        TARGET.rename(BACKUP)
        try:
            STAGING.rename(TARGET)
        except Exception:
            BACKUP.rename(TARGET)
            raise
        shutil.rmtree(BACKUP)
    else:
        STAGING.rename(TARGET)
    audit_path = ROOT / "benchmark/reports/real_db_final/submission_package_audit.json"
    audit_path.write_text(json.dumps({**manifest, "package_path": str(TARGET)}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
