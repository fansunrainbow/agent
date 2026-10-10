from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify controlled external fact files before MySQL import.")
    parser.add_argument("--data-dir", type=Path, default=ROOT, help="Directory containing the four fact CSV files.")
    args = parser.parse_args()
    manifest = json.loads((ROOT / "EXTERNAL_DATA_REQUIREMENTS.json").read_text(encoding="utf-8"))
    results = []
    for expected in manifest["files"]:
        path = (args.data_dir / expected["name"]).resolve()
        exists = path.is_file()
        actual_size = path.stat().st_size if exists else None
        actual_hash = sha256(path) if exists and actual_size == expected["size_bytes"] else None
        results.append({
            "name": expected["name"],
            "exists": exists,
            "size_matches": actual_size == expected["size_bytes"],
            "sha256_matches": actual_hash == expected["sha256"],
        })
    passed = all(item["exists"] and item["size_matches"] and item["sha256_matches"] for item in results)
    print(json.dumps({"status": "PASS" if passed else "FAIL", "data_dir": str(args.data_dir.resolve()), "files": results}, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

