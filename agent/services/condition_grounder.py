from __future__ import annotations

import re
from typing import Any

from agent.models import GroundedCondition
from agent.services.metadata_store import MetadataStore
from agent.services.time_parser import TimeParser
from agent.tools import DictionaryTool, DimensionTool, MetricTool


class ConditionGrounder:
    """Split a request and ground each condition against one typed registry."""

    SPLIT_PATTERN = re.compile(r"[，,。；;、]|同时|并且|以及|且")
    CONTROL_WORDS = (
        "查询", "筛选", "帮我找", "找出", "找", "只看", "客户中", "客户里",
        "客户的", "客户", "个人", "名", "地区", "请", "一下", "分析", "查看", "统计",
    )

    def __init__(self, store: MetadataStore | None = None):
        self.store = store or MetadataStore()
        self.metric_tool = MetricTool(self.store)
        self.dimension_tool = DimensionTool(self.store)
        self.dictionary_tool = DictionaryTool(self.store)
        self.metrics = self.store.yaml("metrics.yaml").get("metrics", {})
        self.metric_aliases = self.store.yaml("metric_aliases.yaml").get("aliases", {})
        self.dimensions = self.store.yaml("dimensions.yaml").get("dimensions", {})
        self.dictionary = self.store.yaml("business_dictionary.yaml").get("dictionary", {})
        self.concept_aliases = self.store.yaml("concept_aliases.yaml").get("aliases", {})
        self.operators = self.store.yaml("operator_registry.yaml").get("operators", {})
        self.language = self.store.yaml("agent_language.yaml")
        self.time_parser = TimeParser(self.store)
        self.segments = self.store.yaml("segment_rules.yaml").get("segments", {})
        self.semantic_boundaries = self.store.yaml("semantic_boundaries.yaml").get("boundaries", {})
        ambiguity = self.store.yaml("ambiguity_rules.yaml")
        self.ambiguous_aliases = ambiguity.get("ambiguous_aliases", {})

    @staticmethod
    def _number(text: str) -> float | int | None:
        match = re.search(r"(-?\d+(?:\.\d+)?)\s*(亿|万|千|百|%)?", text)
        if not match:
            return None
        value = float(match.group(1)) * {
            "亿": 100_000_000, "万": 10_000, "千": 1_000, "百": 100, "%": 0.01,
        }.get(match.group(2), 1)
        return int(value) if value.is_integer() else value

    @staticmethod
    def _catalog_matches(text: str, catalog: dict[str, list[str]]) -> list[dict[str, Any]]:
        lowered = text.lower()
        raw: list[dict[str, Any]] = []
        for target, aliases in catalog.items():
            for alias in dict.fromkeys(str(item) for item in aliases if item):
                start = lowered.find(alias.lower())
                while start >= 0:
                    raw.append({"start": start, "end": start + len(alias), "target": target, "alias": alias})
                    start = lowered.find(alias.lower(), start + 1)
        raw.sort(key=lambda item: (-(item["end"] - item["start"]), item["start"], item["target"]))
        for item in raw:
            item["conflicts"] = sorted({
                other["target"] for other in raw
                if other["start"] == item["start"] and other["end"] == item["end"] and other["alias"] == item["alias"]
            })
        selected: list[dict[str, Any]] = []
        for item in raw:
            if any(item["start"] < old["end"] and old["start"] < item["end"] for old in selected):
                continue
            selected.append(item)
        return sorted(selected, key=lambda item: item["start"])

    def _metric_catalog(self) -> dict[str, list[str]]:
        return {
            metric_id: [
                metric_id,
                definition.get("name", ""),
                *(definition.get("aliases", []) or []),
                *(self.metric_aliases.get(metric_id, []) or []),
            ]
            for metric_id, definition in self.metrics.items()
        }

    def _dimension_catalog(self) -> dict[str, list[str]]:
        return {
            dimension_id: [definition.get("name", ""), *(definition.get("aliases", []) or [])]
            for dimension_id, definition in self.dimensions.items()
        }

    def _concept_catalog(self) -> dict[str, list[str]]:
        return {
            concept_id: [
                definition.get("name", ""),
                *(definition.get("aliases", []) or []),
                *(self.concept_aliases.get(concept_id, []) or []),
            ]
            for concept_id, definition in self.dictionary.items()
        }

    def _operator_value(self, suffix: str) -> tuple[str | None, Any]:
        compact = suffix.strip(" 的客户。")
        special = [
            (r"^(?:为正|正值)", "gt", 0),
            (r"^(?:为负|负值)", "lt", 0),
        ]
        for pattern, operator, value in special:
            if re.search(pattern, compact):
                return operator, value
        aliases = []
        for operator_id, definition in self.operators.items():
            if operator_id in {"exists", "not_exists", "is_null", "is_not_null"}:
                continue
            for alias in [definition.get("sql"), *(definition.get("aliases", []) or [])]:
                if alias:
                    aliases.append((len(str(alias)), str(alias), operator_id))
        for _, alias, operator_id in sorted(aliases, reverse=True):
            match = re.search(re.escape(alias), compact, flags=re.IGNORECASE)
            if match:
                value = self._number(compact[match.end():])
                if value is not None:
                    return operator_id, value
        return None, None

    @staticmethod
    def _patch_action(query: str, semantic_type: str) -> str:
        if any(marker in query for marker in ("去掉", "移除", "删除", "不要", "不看")):
            return "REMOVE_METRIC" if semantic_type == "metric" else "REMOVE_FILTER"
        if any(marker in query for marker in ("换成", "改为", "替换为")):
            return "REPLACE_METRIC" if semantic_type == "metric" else "REPLACE_FILTER"
        return "ADD_METRIC" if semantic_type == "metric" else "ADD_FILTER"

    def _time_condition(
        self, query: str, condition_id: str, context: dict[str, Any] | None = None,
    ) -> GroundedCondition | None:
        return self.time_parser.parse(query, condition_id, context)

    @staticmethod
    def _explicit_dimension_use(query: str, target: str) -> bool:
        if target == "customer":
            return bool(re.search(r"(?:按|逐|每个|每位)客户|客户(?:ID|号)", query, flags=re.IGNORECASE))
        if target == "product":
            return bool(re.search(r"(?:按|逐|每个)产品|产品(?:ID|代码|名称)", query, flags=re.IGNORECASE))
        if target in {"month", "quarter", "date"}:
            markers = {
                "month": ("按月", "逐月", "各月", "每月"),
                "quarter": ("按季度", "逐季度", "各季度", "每季度"),
                "date": ("按日期", "逐日", "每日"),
            }
            return any(marker in query for marker in markers[target])
        return True

    def _boundary_conditions(self, query: str) -> list[GroundedCondition]:
        results: list[GroundedCondition] = []
        for semantic_type, rule in self.semantic_boundaries.items():
            if rule.get("any_markers"):
                matched = next((item for item in rule["any_markers"] if item in query), None)
            else:
                action = next((item for item in rule.get("action_markers", []) if item in query), None)
                obj = next((item for item in rule.get("object_markers", []) if item in query), None)
                matched = f"{action}{obj}" if action and obj else None
            if not matched:
                continue
            if semantic_type == "unsupported_attribute" and any(
                item.semantic_type in {"prediction_request", "suitability_request"} for item in results
            ):
                continue
            results.append(GroundedCondition(
                condition_id=f"c{len(results) + 1}", original_surface=matched,
                semantic_type=semantic_type, target=rule.get("code"),
                source=self.store.source("semantic_boundaries.yaml"), confidence=1.0,
                status="unsupported", reason=rule.get("reason"), question=rule.get("question"),
            ))
        return results

    def _segment_conditions(self, clause: str, query: str) -> list[dict[str, Any]]:
        grounded: list[dict[str, Any]] = []
        for definition in self.segments.values():
            aliases = [definition.get("name", ""), *(definition.get("aliases", []) or [])]
            surface = next((str(alias) for alias in aliases if alias and str(alias) in clause), None)
            if not surface or definition.get("configurable"):
                continue
            for rule in definition.get("conditions", []):
                if rule.get("metric") in self.metrics:
                    grounded.append({
                        "original_surface": surface, "semantic_type": "metric", "target": rule["metric"],
                        "operator": {">": "gt", ">=": "gte", "<": "lt", "<=": "lte", "=": "eq"}.get(rule.get("operator"), rule.get("operator")),
                        "value": rule.get("value"), "source": self.store.source("segment_rules.yaml"),
                        "confidence": 1.0, "patch_action": self._patch_action(query, "metric"),
                    })
        return grounded

    @staticmethod
    def _age_condition(clause: str) -> tuple[str, str, Any] | None:
        match = re.search(r"(?P<low>\d{1,3})\s*(?:到|至|[-~—－])\s*(?P<high>\d{1,3})\s*岁", clause)
        if match:
            return match.group(0), "between", [int(match.group("low")), int(match.group("high"))]
        match = re.search(r"(?P<age>\d{1,3})\s*岁\s*(?P<op>及以上|以上|及以下|以下)", clause)
        if match:
            operators = {"以上": "gt", "及以上": "gte", "以下": "lt", "及以下": "lte"}
            return match.group(0), operators[match.group("op")], int(match.group("age"))
        return None

    def _product_scope(self, metric_match: dict[str, Any]) -> tuple[str, Any] | None:
        alias = metric_match["alias"]
        for concept_id, definition in self.dictionary.items():
            if definition.get("dimension") != "product_primary_category":
                continue
            aliases = [definition.get("name", ""), *(definition.get("aliases", []) or []), *(self.concept_aliases.get(concept_id, []) or [])]
            matched = next((item for item in aliases if item and alias.startswith(str(item))), None)
            values = definition.get("values", [])
            if matched and values:
                return "product_primary_category", values[0]
        return None

    def _unknown_options(self, semantic_type: str) -> list[dict[str, str]]:
        registry = self.metrics if semantic_type == "metric" else self.dimensions
        return [
            {f"{semantic_type}_id": identifier, "name": definition.get("name", identifier)}
            for identifier, definition in list(registry.items())[:10]
        ]

    @classmethod
    def _clean_unknown_surface(cls, text: str) -> str:
        result = text
        for word in cls.CONTROL_WORDS:
            result = result.replace(word, "")
        result = re.sub(r"20\d{2}年|[Qq][1-4]|前\d+|最高|最低|排名|是多少|多少|的", "", result)
        return result.strip(" 、，。")

    def ground(self, query: str, context: dict[str, Any] | None = None) -> list[GroundedCondition]:
        conditions: list[GroundedCondition] = self._boundary_conditions(query)

        def add(**kwargs: Any) -> None:
            kwargs.setdefault("condition_id", f"c{len(conditions) + 1}")
            conditions.append(GroundedCondition(**kwargs))

        time_condition = self._time_condition(query, f"c{len(conditions) + 1}", context)
        if time_condition:
            conditions.append(time_condition)

        metric_catalog = self._metric_catalog()
        dimension_catalog = self._dimension_catalog()
        concept_catalog = self._concept_catalog()
        clauses = [item.strip() for item in self.SPLIT_PATTERN.split(query) if item.strip()]

        for clause in clauses:
            segment_items = self._segment_conditions(clause, query)
            if not any(marker in query for marker in ("筛选", "找出", "选出", "哪些", "客户中", "客户里")) and not any(
                "客户" in str(item.get("original_surface", "")) for item in segment_items
            ):
                segment_items = []
            for kwargs in segment_items:
                add(**kwargs)

            age = self._age_condition(clause)
            if age:
                add(
                    original_surface=age[0], semantic_type="dimension", target="age",
                    operator=age[1], value=age[2], source=self.store.source("dimensions.yaml"),
                    confidence=1.0, patch_action=self._patch_action(query, "dimension"),
                )

            metric_matches = self._catalog_matches(clause, metric_catalog)
            trend_markers = self.language.get("intent_markers", {}).get("trend_analysis", [])
            trend_context = any(marker in query for marker in trend_markers)
            if trend_context and any(item["target"] == "asset_change" for item in metric_matches):
                base_aliases = metric_catalog.get("total_asset", [])
                base = next((alias for alias in sorted(base_aliases, key=len, reverse=True) if alias and alias in clause), None)
                if base:
                    start = clause.find(base)
                    metric_matches = [item for item in metric_matches if item["target"] != "asset_change"]
                    metric_matches.append({
                        "start": start, "end": start + len(base), "target": "total_asset",
                        "alias": base, "conflicts": ["total_asset"],
                    })
                    metric_matches.sort(key=lambda item: item["start"])
            metric_spans = [(item["start"], item["end"]) for item in metric_matches]
            for match in metric_matches:
                ambiguous_rule = self.ambiguous_aliases.get(match["alias"], {})
                ambiguous_candidates = ambiguous_rule.get("candidates", [])
                if ambiguous_candidates and clause.strip(" 查询筛选找。？?") == match["alias"]:
                    add(
                        original_surface=match["alias"], semantic_type="metric",
                        source=self.store.source("ambiguity_rules.yaml"), confidence=0.0, status="ambiguous",
                        candidates=ambiguous_candidates,
                        reason=ambiguous_rule.get("explanation"),
                        question="该表达存在多个已注册指标口径，请选择自然日均资产或有效快照日均资产。",
                    )
                    continue
                if len(match.get("conflicts", [])) > 1:
                    add(
                        original_surface=match["alias"], semantic_type="metric",
                        source=self.store.source("metrics.yaml"), confidence=0.0, status="ambiguous",
                        candidates=match["conflicts"],
                        reason=f"短语“{match['alias']}”同时匹配多个已注册指标。",
                        question="请选择具体指标口径。",
                    )
                    continue
                operator, value = self._operator_value(clause[match["end"]:])
                add(
                    original_surface=clause[match["start"]:].strip(),
                    semantic_type="metric",
                    target=match["target"],
                    operator=operator,
                    value=value,
                    source=self.store.source("metrics.yaml"),
                    confidence=1.0,
                    patch_action=self._patch_action(query, "metric"),
                )
                raw_id_policy = self.language.get("raw_metric_id_time_policy", {})
                if (
                    raw_id_policy.get("enabled")
                    and str(match["alias"]).lower() == str(match["target"]).lower()
                    and time_condition is None
                    and match["target"] not in raw_id_policy.get("non_temporal_metrics", [])
                    and not any(item.semantic_type == "time" for item in conditions)
                ):
                    add(
                        original_surface=match["alias"], semantic_type="time",
                        source=self.store.source("agent_language.yaml"), confidence=0.0,
                        status="ambiguous",
                        reason=f"标准指标 ID“{match['target']}”具有时间语义，但请求未指定统计期间或时点。",
                        question=f"指标“{match['target']}”需要明确统计时间。请提供日期范围、月份、季度，或明确使用最新时点。",
                    )
                product_scope = self._product_scope(match)
                if product_scope:
                    add(
                        original_surface=match["alias"], semantic_type="dimension",
                        target=product_scope[0], operator="eq", value=product_scope[1],
                        source=self.store.source("business_dictionary.yaml"), confidence=1.0,
                        scope=f"metric:{match['target']}", patch_action=self._patch_action(query, "dimension"),
                    )

            value_result = self.dimension_tool.find_values(clause)
            value_surfaces: list[str] = []
            for value in value_result.data or []:
                surface = str(value.get("matched_surface") or value.get("value") or "")
                if value.get("dimension_id") in {"product_primary_category", "product_secondary_category"} and "客户" not in query:
                    continue
                start = clause.find(surface)
                if start >= 0 and any(start < end and begin < start + len(surface) for begin, end in metric_spans):
                    continue
                value_surfaces.append(surface)
                action = self._patch_action(query, "dimension")
                add(
                    original_surface=surface or clause, semantic_type="dimension",
                    target=value["dimension_id"], operator="eq", value=value["value"],
                    source=value["source"], confidence=1.0, patch_action=action,
                )

            for match in self._catalog_matches(clause, dimension_catalog):
                if any(match["start"] < end and begin < match["end"] for begin, end in metric_spans):
                    continue
                if not self._explicit_dimension_use(query, match["target"]):
                    continue
                if age and match["target"] in {"age", "age_group"}:
                    continue
                if any(item.target == match["target"] and item.original_surface in clause for item in conditions):
                    continue
                add(
                    original_surface=match["alias"], semantic_type="dimension", target=match["target"],
                    source=self.store.source("dimensions.yaml"), confidence=1.0,
                )

            for match in self._catalog_matches(clause, concept_catalog):
                if any(match["start"] < end and begin < match["end"] for begin, end in metric_spans):
                    continue
                if any(surface and surface in match["alias"] for surface in value_surfaces):
                    continue
                definition = self.dictionary.get(match["target"], {})
                if definition.get("category") in {"dimension", "entity"}:
                    continue
                operator = "neq" if re.search(rf"(?:非|不是|排除|不含|不包括){re.escape(match['alias'])}", clause) else "eq"
                add(
                    original_surface=match["alias"], semantic_type="concept", target=match["target"],
                    operator=operator, value=True, source=self.store.source("business_dictionary.yaml"),
                    confidence=1.0, patch_action=self._patch_action(query, "concept"),
                )

            if not metric_matches and not segment_items:
                for alias, rule in self.ambiguous_aliases.items():
                    if alias not in clause:
                        continue
                    preferred = rule.get("resolution", {}).get("prefer_metric")
                    if preferred in self.metrics:
                        operator, value = self._operator_value(clause[clause.find(alias) + len(alias):])
                        alias_start = clause.find(alias)
                        add(
                            original_surface=clause[alias_start:].strip(), semantic_type="metric", target=preferred,
                            operator=operator, value=value, source=self.store.source("ambiguity_rules.yaml"),
                            confidence=0.9, patch_action=self._patch_action(query, "metric"),
                        )
                        metric_matches = [{"target": preferred, "alias": alias, "start": alias_start, "end": alias_start + len(alias)}]
                        break

            if not metric_matches and not segment_items:
                operator, value = self._operator_value(clause)
                ranking = re.search(r"(.+?)(?:最高|最低|排名|前\d+)", clause)
                unknown_surface = self._clean_unknown_surface(ranking.group(1) if ranking else clause.split("超过")[0].split("低于")[0])
                if (operator is not None or ranking) and len(unknown_surface) >= 2:
                    add(
                        original_surface=unknown_surface, semantic_type="metric", source="unmatched_user_phrase",
                        confidence=0.0, status="unsupported", candidates=self._unknown_options("metric"),
                        reason=f"指标“{unknown_surface}”未在 Metric Registry 中注册，不能生成可执行计划。",
                        question=f"不支持指标“{unknown_surface}”。请改用下列已注册指标之一，或先补充该指标的正式口径。",
                    )

        ambiguity_result = self.dictionary_tool.find_ambiguities(query)
        for item in ambiguity_result.data or []:
            semantic_type = "time" if item.get("type") == "time" else "concept"
            if semantic_type == "time" and time_condition is not None:
                continue
            add(
                original_surface=item.get("term", "模糊概念"), semantic_type=semantic_type,
                source=item.get("source", self.store.source("ambiguity_rules.yaml")), confidence=0.0,
                status="ambiguous", candidates=item.get("options", []), reason=item.get("question"),
                question=item.get("question"),
            )

        if "指定客户" in query and not re.search(r"[A-Za-z]?\d{4,}", query):
            add(
                original_surface="指定客户", semantic_type="entity", target="customer",
                source=self.store.source("entity_rules.yaml"), confidence=0.0, status="ambiguous",
                reason="客户实体需要唯一客户标识，当前请求没有提供客户号或客户ID。",
                question="请提供明确的客户号或客户ID；不能根据“指定客户”猜测具体客户。",
            )

        known_surfaces = {
            item.original_surface for item in conditions
            if item.status != "unsupported" and item.semantic_type in {"metric", "dimension", "concept", "time"}
        }
        for match in re.finditer(r"(?:查询|筛选|找|只看|帮我找)?(?P<surface>[\u4e00-\u9fffA-Za-z]{2,12})客户(?:中|里|的|。|，|,|$)", query):
            surface = self._clean_unknown_surface(match.group("surface"))
            unnegated = surface.lstrip("非不")
            if not surface or any(
                known and (known in surface or surface in known or unnegated in known or known in unnegated)
                for known in known_surfaces
            ):
                continue
            if surface in {"所有", "全部"}:
                continue
            add(
                original_surface=surface, semantic_type="dimension", source="unmatched_user_phrase",
                confidence=0.0, status="unsupported", candidates=self._unknown_options("dimension"),
                reason=f"维度或维度值“{surface}”未在 Dimension Registry / Value Mapping 中注册。",
                question=f"不支持维度条件“{surface}”。当前数据没有该字段或映射，请改用下列已注册维度之一。",
            )

        for match in re.finditer(r"(?:按|客户)(?P<surface>[\u4e00-\u9fffA-Za-z]{2,12}?)(?:分布|统计|筛选)", query):
            surface = self._clean_unknown_surface(match.group("surface"))
            if not surface or any(
                known and (known in surface or surface in known) for known in known_surfaces
            ):
                continue
            if any(
                item.original_surface == surface and item.status != "resolved" for item in conditions
            ):
                continue
            add(
                original_surface=surface, semantic_type="dimension", source="unmatched_user_phrase",
                confidence=0.0, status="unsupported", candidates=self._unknown_options("dimension"),
                reason=f"分析维度“{surface}”未在 Dimension Registry 中注册，不能生成分组计划。",
                question=f"不支持分析维度“{surface}”。请改用已注册的客户等级、状态、性别、年龄、学历、地区或机构维度。",
            )

        for metric_id, hint in self.language.get("metric_hints", {}).items():
            if any(item.target == metric_id for item in conditions):
                continue
            if metric_id in self.metrics and any(marker in query for marker in hint.get("subject_markers", [])) and any(
                marker in query for marker in hint.get("request_markers", [])
            ):
                add(
                    original_surface=next(marker for marker in hint["request_markers"] if marker in query),
                    semantic_type="metric", target=metric_id, source=self.store.source("agent_language.yaml"),
                    confidence=1.0, patch_action=self._patch_action(query, "metric"),
                )

        unique: dict[tuple[Any, ...], GroundedCondition] = {}
        for item in conditions:
            key = (
                item.semantic_type, item.target, item.operator, str(item.value), item.status, item.scope,
                item.original_surface if item.status != "resolved" or item.target is None else None,
            )
            unique[key] = item
        result = list(unique.values())
        for index, item in enumerate(result, 1):
            item.condition_id = f"c{index}"
        return result
