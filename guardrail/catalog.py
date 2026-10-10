from __future__ import annotations

from pathlib import Path
import csv
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]


class MetadataCatalog:
    """Read-only view over Stage 1-4 registries used by Stage 6."""

    def __init__(self, root: Path = ROOT):
        self.root = root
        self.metadata_dir = root / "metadata"
        self.metrics = self._load("metrics.yaml").get("metrics", {})
        self.dimensions = self._load("dimensions.yaml").get("dimensions", {})
        self.tables = self._load("tables.yaml").get("tables", {})
        self.joins_data = self._load("joins.yaml")
        self.joins = self.joins_data.get("joins", {})
        self.dictionary = self._load("business_dictionary.yaml").get("dictionary", {})
        self.value_mappings = self._load("value_mappings.yaml").get("mappings", {})
        self.language = self._load("agent_language.yaml")
        self.entity_rules = self._load("entity_rules.yaml")
        self.entity_relations = self._load("entity_relations.yaml").get("relations", {})

    def _load(self, name: str) -> dict[str, Any]:
        with (self.metadata_dir / name).open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}

    def table_columns(self, table: str) -> set[str]:
        columns = self.tables.get(table, {}).get("columns", {})
        if isinstance(columns, dict):
            return set(columns)
        return {
            str(item.get("name")) for item in columns
            if isinstance(item, dict) and item.get("name")
        }

    def verified_join(self, left: str, right: str) -> dict[str, Any] | None:
        for item in self.joins.values():
            if not item.get("verified"):
                continue
            pair = {item.get("left_table"), item.get("right_table")}
            if pair == {left, right}:
                return item
        return None

    def entity_relation(self, relation_id: str | None) -> dict[str, Any] | None:
        relation = self.entity_relations.get(str(relation_id))
        return relation if relation and relation.get("enabled", False) else None

    def verified_join_by_id(self, join_id: str | None) -> dict[str, Any] | None:
        join = self.joins.get(str(join_id))
        return join if join and join.get("verified") else None

    def fact_tables(self) -> set[str]:
        return {
            table_id for table_id, meta in self.tables.items()
            if meta.get("table_type") == "fact"
        }

    def row_count(self, table: str) -> int:
        meta = self.tables.get(table, {})
        for key in ("row_count", "estimated_rows", "rows"):
            value = meta.get(key)
            if isinstance(value, int):
                return value
        return 0

    def storage_value(self, dimension_id: str, value: Any) -> Any:
        """Map a semantic/display dimension value to its registered DB value."""
        if isinstance(value, list):
            return [self.storage_value(dimension_id, item) for item in value]
        mapping = self.value_mappings.get(dimension_id, {})
        text = str(value)
        values = mapping.get("values", {}) or {}
        aliases = mapping.get("input_aliases", {}) or {}
        for canonical, surfaces in aliases.items():
            if text.casefold() in {str(item).casefold() for item in surfaces}:
                text = str(canonical)
                break
        if text in values:
            return text if mapping.get("dictionary_table") else values[text]
        for code, label in values.items():
            if text == str(label):
                return str(code) if mapping.get("dictionary_table") else label
        semantic = mapping.get("semantic_values", {}) or {}
        if text in semantic:
            return semantic[text]
        dimension = self.dimensions.get(dimension_id, {})
        dynamic = (self.language.get("dynamic_dimension_values", {}) or {}).get(dimension_id, {})
        table, field = dimension.get("source_table"), dimension.get("source_field")
        if dynamic and table and field:
            candidates = sorted(self.root.glob(f"{table}_*.csv"))
            if candidates:
                with candidates[-1].open("r", encoding="utf-8-sig", newline="") as handle:
                    for row in csv.DictReader(handle):
                        raw = str(row.get(field, ""))
                        canonical = raw
                        for suffix in dynamic.get("strip_suffixes", []):
                            if canonical.endswith(suffix) and len(canonical) > len(suffix):
                                canonical = canonical[:-len(suffix)]
                                break
                        if text in {raw, canonical}:
                            return raw
        return value
