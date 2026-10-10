from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGETS = (ROOT / "benchmark/reports", ROOT / "docs")
TEXT_SUFFIXES = {".json", ".jsonl", ".md", ".txt", ".yaml", ".yml"}


def main() -> int:
    raw = str(ROOT)
    posix = ROOT.as_posix()
    escaped = json.dumps(raw)[1:-1]
    changed: list[str] = []
    for base in TARGETS:
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            sanitized = text.replace(escaped, "<PROJECT_ROOT>").replace(raw, "<PROJECT_ROOT>").replace(posix, "<PROJECT_ROOT>")
            if sanitized != text:
                path.write_text(sanitized, encoding="utf-8")
                changed.append(path.relative_to(ROOT).as_posix())
    print(json.dumps({"sanitized_file_count": len(changed), "files": changed}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
