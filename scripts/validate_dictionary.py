from pathlib import Path
from collections import defaultdict
import sys
import yaml


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


ROOT = Path(__file__).resolve().parents[1]
METADATA_DIR = ROOT / "metadata"


FILES = {
    "tables": METADATA_DIR / "tables.yaml",
    "metrics": METADATA_DIR / "metrics.yaml",
    "dictionary": METADATA_DIR / "business_dictionary.yaml",
    "concept_aliases": METADATA_DIR / "concept_aliases.yaml",
    "segments": METADATA_DIR / "segment_rules.yaml",
    "entities": METADATA_DIR / "entity_rules.yaml",
    "ambiguity": METADATA_DIR / "ambiguity_rules.yaml",
    "value_mappings": METADATA_DIR / "value_mappings.yaml",
}


def load_yaml(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")

    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return data or {}


def normalize_columns(table_meta):
    """
    兼容 tables.yaml 中 columns 为 dict 或 list 的情况。
    返回字段名集合。
    """
    columns = table_meta.get("columns", {})

    if isinstance(columns, dict):
        return set(columns.keys())

    if isinstance(columns, list):
        result = set()

        for item in columns:
            if isinstance(item, str):
                result.add(item)

            elif isinstance(item, dict):
                if "name" in item:
                    result.add(item["name"])
                elif len(item) == 1:
                    result.add(next(iter(item.keys())))

        return result

    return set()


def extract_table_names(tables_data):
    tables = tables_data.get("tables", {})
    return set(tables.keys())


def extract_table_columns(tables_data):
    result = {}

    for table_name, table_meta in tables_data.get("tables", {}).items():
        result[table_name] = normalize_columns(table_meta)

    return result


def extract_metric_ids(metrics_data):
    return set(metrics_data.get("metrics", {}).keys())


def check_dictionary_sources(dictionary, table_names, table_columns):
    errors = []

    for concept_id, concept in dictionary.items():
        source = concept.get("source")

        if not source:
            continue

        # 单表 source
        table = source.get("table")
        field = source.get("field")

        if table:
            if table not in table_names:
                errors.append(
                    f"[dictionary:{concept_id}] "
                    f"source table 不存在: {table}"
                )
            elif field:
                columns = table_columns.get(table, set())
                if columns and field not in columns:
                    errors.append(
                        f"[dictionary:{concept_id}] "
                        f"source field 不存在: {table}.{field}"
                    )

        # 多字段 source
        fields = source.get("fields", [])

        for full_field in fields:
            if "." not in full_field:
                errors.append(
                    f"[dictionary:{concept_id}] "
                    f"source.fields 格式错误: {full_field}"
                )
                continue

            table_name, field_name = full_field.split(".", 1)

            if table_name not in table_names:
                errors.append(
                    f"[dictionary:{concept_id}] "
                    f"source table 不存在: {table_name}"
                )
                continue

            columns = table_columns.get(table_name, set())

            if columns and field_name not in columns:
                errors.append(
                    f"[dictionary:{concept_id}] "
                    f"source field 不存在: "
                    f"{table_name}.{field_name}"
                )

    return errors


def check_segment_metrics(segments, metric_ids):
    errors = []

    for segment_id, segment in segments.items():
        conditions = segment.get("conditions", [])

        for condition in conditions:
            metric = condition.get("metric")

            if metric and metric not in metric_ids:
                errors.append(
                    f"[segment:{segment_id}] "
                    f"引用的 metric 不存在: {metric}"
                )

    return errors


def check_entity_sources(entities, table_names, table_columns):
    errors = []

    for entity_id, entity in entities.items():
        table = entity.get("source_table")

        if not table:
            continue

        if table not in table_names:
            errors.append(
                f"[entity:{entity_id}] "
                f"source_table 不存在: {table}"
            )
            continue

        columns = table_columns.get(table, set())

        for field in entity.get("search_fields", []):
            if columns and field not in columns:
                errors.append(
                    f"[entity:{entity_id}] "
                    f"search field 不存在: {table}.{field}"
                )

        for field in entity.get("return_fields", []):
            if columns and field not in columns:
                errors.append(
                    f"[entity:{entity_id}] "
                    f"return field 不存在: {table}.{field}"
                )

    return errors


def collect_aliases(dictionary, concept_aliases, segments):
    """
    收集标准业务概念相关 alias。
    返回:
      alias -> [(source_type, concept_id), ...]
    """
    alias_map = defaultdict(list)

    for concept_id, concept in dictionary.items():
        for alias in concept.get("aliases", []):
            alias_map[str(alias).strip()].append(
                ("dictionary", concept_id)
            )

    for concept_id, aliases in concept_aliases.items():
        for alias in aliases or []:
            alias_map[str(alias).strip()].append(
                ("concept_aliases", concept_id)
            )

    for segment_id, segment in segments.items():
        for alias in segment.get("aliases", []):
            alias_map[str(alias).strip()].append(
                ("segment", segment_id)
            )

    return alias_map


def check_alias_conflicts(
    dictionary,
    concept_aliases,
    segments,
    ambiguity_data,
):
    warnings = []

    alias_map = collect_aliases(
        dictionary,
        concept_aliases,
        segments,
    )

    ambiguous_aliases = set(
        ambiguity_data.get("ambiguous_aliases", {}).keys()
    )

    for alias, targets in sorted(alias_map.items()):
        concept_ids = {concept_id for _, concept_id in targets}

        # 同一个 alias 在两个文件里重复指向同一 concept，
        # 不属于真正冲突。
        if len(concept_ids) <= 1:
            continue

        # 如果已经明确记录在 ambiguity_rules，
        # 则视为已处理冲突。
        if alias in ambiguous_aliases:
            continue

        warnings.append(
            f"[alias conflict] '{alias}' "
            f"同时指向: {sorted(concept_ids)}"
        )

    return warnings


def check_dictionary_alias_targets(
    dictionary,
    concept_aliases,
):
    warnings = []

    dictionary_ids = set(dictionary.keys())

    for concept_id in concept_aliases:
        # 允许 alias 文件暂时比主词典更丰富，
        # 但需要提示后续是否应补入主词典。
        if concept_id not in dictionary_ids:
            warnings.append(
                f"[concept_aliases] '{concept_id}' "
                f"暂未出现在 business_dictionary.yaml"
            )

    return warnings


def check_value_mapping_sources(
    mappings,
    table_names,
    table_columns,
):
    errors = []

    for mapping_id, mapping in mappings.items():
        table = mapping.get("source_table")
        field = mapping.get("source_field")

        if table:
            if table not in table_names:
                errors.append(
                    f"[value_mapping:{mapping_id}] "
                    f"source_table 不存在: {table}"
                )
            elif field:
                columns = table_columns.get(table, set())

                if columns and field not in columns:
                    errors.append(
                        f"[value_mapping:{mapping_id}] "
                        f"source_field 不存在: "
                        f"{table}.{field}"
                    )

        for full_field in mapping.get("source_fields", []):
            if "." not in full_field:
                errors.append(
                    f"[value_mapping:{mapping_id}] "
                    f"source_fields 格式错误: {full_field}"
                )
                continue

            table_name, field_name = full_field.split(".", 1)

            if table_name not in table_names:
                errors.append(
                    f"[value_mapping:{mapping_id}] "
                    f"source table 不存在: {table_name}"
                )
                continue

            columns = table_columns.get(table_name, set())

            if columns and field_name not in columns:
                errors.append(
                    f"[value_mapping:{mapping_id}] "
                    f"source field 不存在: "
                    f"{table_name}.{field_name}"
                )

    return errors


def main():
    print("=" * 72)
    print("Stage 3 Business Dictionary Validator")
    print("=" * 72)

    try:
        data = {
            name: load_yaml(path)
            for name, path in FILES.items()
        }
    except Exception as e:
        print(f"❌ YAML 加载失败: {e}")
        sys.exit(1)

    print("✅ 所需 YAML 文件全部成功加载")

    tables_data = data["tables"]
    metrics_data = data["metrics"]

    dictionary = data["dictionary"].get("dictionary", {})
    concept_aliases = data["concept_aliases"].get("aliases", {})
    segments = data["segments"].get("segments", {})
    entities = data["entities"].get("entities", {})
    ambiguity_data = data["ambiguity"]
    mappings = data["value_mappings"].get("mappings", {})

    table_names = extract_table_names(tables_data)
    table_columns = extract_table_columns(tables_data)
    metric_ids = extract_metric_ids(metrics_data)

    print(f"数据库表数量: {len(table_names)}")
    print(f"指标数量: {len(metric_ids)}")
    print(f"业务词典概念数量: {len(dictionary)}")
    print(f"客群规则数量: {len(segments)}")
    print(f"实体规则数量: {len(entities)}")
    print()

    errors = []
    warnings = []

    errors.extend(
        check_dictionary_sources(
            dictionary,
            table_names,
            table_columns,
        )
    )

    errors.extend(
        check_segment_metrics(
            segments,
            metric_ids,
        )
    )

    errors.extend(
        check_entity_sources(
            entities,
            table_names,
            table_columns,
        )
    )

    errors.extend(
        check_value_mapping_sources(
            mappings,
            table_names,
            table_columns,
        )
    )

    warnings.extend(
        check_alias_conflicts(
            dictionary,
            concept_aliases,
            segments,
            ambiguity_data,
        )
    )

    warnings.extend(
        check_dictionary_alias_targets(
            dictionary,
            concept_aliases,
        )
    )

    print("-" * 72)

    if warnings:
        print(f"⚠ 发现 {len(warnings)} 条警告：")
        for item in warnings:
            print(f"  - {item}")
    else:
        print("✅ 未发现别名/覆盖警告")

    print("-" * 72)

    if errors:
        print(f"❌ 发现 {len(errors)} 个错误：")
        for item in errors:
            print(f"  - {item}")

        print("=" * 72)
        print("❌ Stage 3 业务词典结构校验未通过")
        sys.exit(1)

    print("✅ 表、字段、指标和规则引用检查通过")
    print("=" * 72)
    print("✅ Stage 3 业务词典结构校验通过")


if __name__ == "__main__":
    main()
