from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
METADATA_DIR = ROOT / "metadata"


class MetadataStore:
    """Read-only cached access to Stage 1-4 metadata and local entity datasets."""

    def __init__(self, root: Path | None = None):
        self.root = (root or ROOT).resolve()
        self.metadata_dir = self.root / "metadata"
        self._yaml_cache: dict[str, dict[str, Any]] = {}
        self._csv_cache: dict[str, list[dict[str, str]]] = {}

    def yaml(self, filename: str) -> dict[str, Any]:
        if filename not in self._yaml_cache:
            path = self.metadata_dir / filename
            with path.open("r", encoding="utf-8") as handle:
                self._yaml_cache[filename] = yaml.safe_load(handle) or {}
        return self._yaml_cache[filename]

    def csv_path_for_table(self, table_name: str) -> Path | None:
        candidates = sorted(self.root.glob(f"{table_name}_*.csv"))
        return candidates[-1] if candidates else None

    def csv_rows(self, table_name: str) -> list[dict[str, str]]:
        if table_name not in self._csv_cache:
            path = self.csv_path_for_table(table_name)
            if path is None:
                self._csv_cache[table_name] = []
            else:
                with path.open("r", encoding="utf-8-sig", newline="") as handle:
                    self._csv_cache[table_name] = list(csv.DictReader(handle))
        return self._csv_cache[table_name]

    def source(self, filename: str) -> str:
        return f"metadata/{filename}"
