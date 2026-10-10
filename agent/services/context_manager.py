from __future__ import annotations

from copy import deepcopy
import re
from typing import Any, Iterable

from agent.models.plan_patch import PatchOperation, PlanPatch


class ContextManager:
    """Build and apply explicit semantic patches to a parent Query Plan."""

    SUPPORTED_ACTIONS = {item.value for item in PatchOperation}
    REMOVE_MARKERS = ("去掉", "移除", "删除", "不要", "不看", "取消")
    REPLACE_MARKERS = ("换成", "改成", "改为", "替换为")
    KEEP_MARKERS = ("不变", "还是看", "继续看", "按刚才", "保持", "保留")
    NEW_TASK_MARKERS = ("换个问题", "另一个问题", "重新查", "重新查询", "新问题")

    @classmethod
    def is_new_task(cls, query: str) -> bool:
        return any(marker in query for marker in cls.NEW_TASK_MARKERS)

    @classmethod
    def is_keep_request(cls, query: str) -> bool:
        return any(marker in query for marker in cls.KEEP_MARKERS) and not any(
            marker in query for marker in cls.REPLACE_MARKERS
        )

    @staticmethod
    def _simple_filter_key(item: dict[str, Any]) -> tuple[str | None, str | None] | None:
        if "logic" in item:
            return None
        return item.get("type"), item.get("target")

    @classmethod
    def _filter_leaves(cls, nodes: Iterable[dict[str, Any]]) -> Iterable[dict[str, Any]]:
        for item in nodes:
            if "logic" in item:
                yield from cls._filter_leaves(item.get("conditions", []))
            else:
                yield item

    @classmethod
    def _find_filters(cls, plan: dict[str, Any], target: str | None) -> list[dict[str, Any]]:
        return [item for item in cls._filter_leaves(plan.get("filters", [])) if item.get("target") == target]

    @classmethod
    def _find_filter(cls, fragment: dict[str, Any], target: str | None) -> dict[str, Any] | None:
        return next(iter(cls._find_filters(fragment, target)), None)

    @classmethod
    def _rewrite_filters(
        cls,
        nodes: list[dict[str, Any]],
        target: str,
        replacement: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        for item in nodes:
            if "logic" not in item:
                if item.get("target") == target:
                    if replacement is not None:
                        output.append(deepcopy(replacement))
                    continue
                output.append(deepcopy(item))
                continue
            children = cls._rewrite_filters(item.get("conditions", []), target, replacement)
            if not children:
                continue
            node = deepcopy(item)
            node["conditions"] = children
            output.append(node)
        return output

    @staticmethod
    def _patch(
        operation: str,
        target: str,
        old_value: Any = None,
        new_value: Any = None,
        source: str = "explicit_follow_up",
        requested_new_value: Any = None,
        resolution_status: str = "resolved",
        patch_status: str = "APPLIED",
    ) -> PlanPatch:
        return PlanPatch(
            operation=PatchOperation(operation), target=target,
            old_value=deepcopy(old_value), new_value=deepcopy(new_value), source=source,
            requested_new_value=deepcopy(requested_new_value),
            resolution_status=resolution_status, patch_status=patch_status,
        )

    @staticmethod
    def patch_result_status(changes: list[dict[str, Any]]) -> str:
        statuses = {item.get("patch_status", "APPLIED") for item in changes}
        if not changes:
            return "FAILED"
        if statuses == {"APPLIED"}:
            return "APPLIED"
        if "APPLIED" in statuses:
            return "PARTIALLY_APPLIED"
        if "UNSUPPORTED" in statuses:
            return "UNSUPPORTED"
        if "NEEDS_CLARIFICATION" in statuses:
            return "NEEDS_CLARIFICATION"
        return "FAILED"

    @classmethod
    def _unresolved_explicit_replacement(
        cls,
        previous: dict[str, Any],
        query: str,
        requested_operations: list[dict[str, Any]],
        patches: list[PlanPatch],
    ) -> PlanPatch | None:
        """Fail closed when an explicit replacement contains an ungrounded residue.

        This is structural: it uses the parent plan and surfaces already grounded by
        registries. It never maps an unknown word to a business value.
        """
        if not any(marker in query for marker in cls.REPLACE_MARKERS):
            return None
        payload = query
        for marker in cls.REPLACE_MARKERS:
            payload = payload.replace(marker, "")
        for request in requested_operations:
            surface = request.get("requested_surface")
            if surface:
                payload = payload.replace(str(surface), "")
        if any(patch.operation == PatchOperation.CHANGE_LIMIT for patch in patches):
            payload = re.sub(r"(?:前|top)?\s*\d+\s*(?:名|个|人|条)?", "", payload, flags=re.IGNORECASE)
        if any(patch.operation == PatchOperation.CHANGE_ORDER for patch in patches):
            payload = re.sub(r"(?:从低到高|从高到低|升序|降序)", "", payload)
        payload = re.sub(r"[，,。；;、！？!?\s]", "", payload)
        payload = re.sub(r"^(?:请|再|然后|同时|并且)+", "", payload)
        payload = payload.replace("只看", "").replace("查询", "").replace("查看", "")
        # Generic class words are not business values; keep the actual unknown token.
        payload = re.sub(r"(?:客户|城市|地区|指标|维度|条件|等级)$", "", payload)
        if not payload:
            return None

        modified = {patch.target for patch in patches if patch.patch_status == "APPLIED"}
        filter_targets = [
            item.get("target") for item in cls._filter_leaves(previous.get("filters", []))
            if item.get("target") and item.get("target") not in modified
        ]
        metric_targets = [item for item in previous.get("metrics", []) if item not in modified]
        dimension_targets = [item for item in previous.get("dimensions", []) if item not in modified]

        if "指标" in query:
            candidates = [("REPLACE_METRIC", item) for item in metric_targets]
        elif any(word in query for word in ("城市", "地区", "城")) and "city" in filter_targets:
            candidates = [("REPLACE_FILTER", "city")]
        elif any(word in query for word in ("等级", "级别")) and "customer_level" in filter_targets:
            candidates = [("REPLACE_FILTER", "customer_level")]
        else:
            candidates = [("REPLACE_FILTER", item) for item in filter_targets]
            if not candidates:
                candidates = [("REPLACE_METRIC", item) for item in metric_targets]
            if not candidates:
                candidates = [("REPLACE_DIMENSION", item) for item in dimension_targets]
        # A failed mutation may identify its semantic target only when the parent
        # context makes that target unique. Otherwise the target itself is unclear.
        unique = list(dict.fromkeys(candidates))
        action, target = unique[0] if len(unique) == 1 else ("REPLACE_FILTER", "unresolved_semantic_target")
        old_filters = cls._find_filters(previous, target)
        old_value: Any = old_filters[0] if len(old_filters) == 1 else old_filters
        if action == "REPLACE_METRIC":
            old_value = target
        elif action == "REPLACE_DIMENSION":
            old_value = target
        return cls._patch(
            action, target, old_value, None, "explicit_mutation_fail_closed",
            requested_new_value=payload, resolution_status="not_found",
            patch_status="NEEDS_CLARIFICATION",
        )

    def build_patch_models(
        self,
        previous: dict[str, Any],
        fragment: dict[str, Any],
        requested_operations: list[dict[str, Any]] | None = None,
        query: str = "",
    ) -> tuple[list[PlanPatch], list[dict[str, Any]]]:
        requested_operations = requested_operations or []
        patches: list[PlanPatch] = []
        ambiguities: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()

        def add(patch: PlanPatch) -> None:
            key = (patch.operation.value, patch.target)
            if key not in seen:
                seen.add(key)
                patches.append(patch)

        for request in requested_operations:
            action = request.get("action")
            target = request.get("target")
            if action not in self.SUPPORTED_ACTIONS or not target:
                continue
            old_filters = self._find_filters(previous, target)
            old_value: Any = old_filters[0] if len(old_filters) == 1 else old_filters
            new_value = request.get("value")
            if action in {"ADD_FILTER", "REPLACE_FILTER"}:
                new_value = self._find_filter(fragment, target)
                if not isinstance(new_value, dict):
                    continue
            elif action in {"ADD_METRIC", "REPLACE_METRIC"}:
                new_value = target
            elif action == "CHANGE_TIME_RANGE":
                new_value = fragment.get("time_range") or new_value
                old_value = previous.get("time_range")
                if new_value is None:
                    continue
            elif action == "CHANGE_ORDER":
                new_value = fragment.get("order_by") or new_value
                old_value = previous.get("order_by", [])
                if not new_value:
                    continue
            elif action == "CHANGE_LIMIT":
                new_value = fragment.get("limit") if fragment.get("limit") is not None else new_value
                old_value = previous.get("limit")
                if new_value is None:
                    continue
            elif action in {"REMOVE_METRIC", "REMOVE_DIMENSION"}:
                old_value = target
            add(self._patch(
                action, target, old_value, new_value,
                requested_new_value=request.get("requested_surface", new_value),
                resolution_status=request.get("resolution_status", "resolved"),
            ))

        removing = any(marker in query for marker in self.REMOVE_MARKERS)
        if removing:
            if any(marker in query for marker in ("时间", "日期", "季度", "月份", "月范围")):
                add(self._patch("REMOVE_TIME_RANGE", "time_range", previous.get("time_range")))
            if any(marker in query for marker in ("排序", "顺序", "高到低", "低到高")):
                add(self._patch("REMOVE_ORDER", "order_by", previous.get("order_by", [])))
            if any(marker in query for marker in ("限制", "数量", "名额", "前几")):
                add(self._patch("REMOVE_LIMIT", "limit", previous.get("limit")))

        if re.search(r"(?:不要排序|取消排序|去掉排序)", query):
            add(self._patch("REMOVE_ORDER", "order_by", previous.get("order_by", [])))
        if re.search(r"(?:不限制(?:数量|条数|人数)?|取消限制|去掉限制)", query):
            add(self._patch("REMOVE_LIMIT", "limit", previous.get("limit")))
        if re.search(r"(?:去掉|取消|不要)(?:原来的)?(?:时间|日期|季度|月份)", query):
            add(self._patch("REMOVE_TIME_RANGE", "time_range", previous.get("time_range")))

        if any(marker in query for marker in ("从低到高", "升序")) and previous.get("order_by"):
            value = [{**item, "direction": "asc"} for item in previous["order_by"]]
            add(self._patch("CHANGE_ORDER", "order_by", previous.get("order_by"), value))
        elif any(marker in query for marker in ("从高到低", "降序")) and previous.get("order_by"):
            value = [{**item, "direction": "desc"} for item in previous["order_by"]]
            add(self._patch("CHANGE_ORDER", "order_by", previous.get("order_by"), value))

        for item in self._filter_leaves(fragment.get("filters", [])):
            key = self._simple_filter_key(item)
            if key is None or any(patch.target == key[1] and patch.operation.value.endswith("FILTER") for patch in patches):
                continue
            old = self._find_filters(previous, key[1])
            action = "REPLACE_FILTER" if old else "ADD_FILTER"
            add(self._patch(action, str(key[1]), old[0] if len(old) == 1 else old, item, "grounded_fragment"))

        explicit_metric_actions = {patch.target for patch in patches if patch.operation.value.endswith("METRIC")}
        for metric in fragment.get("metrics", []):
            if metric not in previous.get("metrics", []) and metric not in explicit_metric_actions:
                add(self._patch("ADD_METRIC", metric, None, metric, "grounded_fragment"))
        if fragment.get("time_range") is not None and fragment.get("time_range") != previous.get("time_range") and not any(
            patch.operation == PatchOperation.CHANGE_TIME_RANGE for patch in patches
        ):
            add(self._patch("CHANGE_TIME_RANGE", "time_range", previous.get("time_range"), fragment["time_range"], "time_parser"))
        if fragment.get("order_by") and fragment.get("order_by") != previous.get("order_by") and not any(
            patch.operation in {PatchOperation.CHANGE_ORDER, PatchOperation.REMOVE_ORDER} for patch in patches
        ):
            add(self._patch("CHANGE_ORDER", "order_by", previous.get("order_by", []), fragment["order_by"], "grounded_fragment"))
        if fragment.get("limit") is not None and fragment.get("limit") != previous.get("limit") and not any(
            patch.operation in {PatchOperation.CHANGE_LIMIT, PatchOperation.REMOVE_LIMIT} for patch in patches
        ):
            add(self._patch("CHANGE_LIMIT", "limit", previous.get("limit"), fragment["limit"], "grounded_fragment"))

        metric_reference = any(marker in query for marker in ("那个指标", "刚才那个指标", "上一条指标"))
        if metric_reference and len(previous.get("metrics", [])) != 1:
            ambiguities.append({
                "term": "那个指标", "type": "metric",
                "reason": "上文存在多个指标，引用无法唯一定位。",
                "question": "请明确要保留或修改哪个指标。",
                "candidates": list(previous.get("metrics", [])),
            })

        if "保留" in query and any(marker in query for marker in self.REPLACE_MARKERS):
            for patch in patches:
                if patch.operation == PatchOperation.REPLACE_FILTER and patch.old_value != patch.new_value:
                    ambiguities.append({
                        "term": patch.target, "type": "other",
                        "reason": "同一指令同时要求保留并替换该条件。",
                        "question": f"请确认是保留还是替换 {patch.target} 条件。",
                        "candidates": [patch.old_value, patch.new_value],
                    })
        failed_replacement = self._unresolved_explicit_replacement(
            previous, query, requested_operations, patches,
        )
        if failed_replacement is not None:
            patches.append(failed_replacement)
            ambiguities.append({
                "term": failed_replacement.requested_new_value,
                "type": "other",
                "reason": "显式修改的新值未能从受控 Metadata、Dictionary 或实体数据中解析；修改已关闭执行。",
                "question": f"无法解析“{failed_replacement.requested_new_value}”，请提供受支持的明确值。",
                "candidates": [],
            })
        return patches, ambiguities

    def build_patch(
        self,
        previous: dict[str, Any],
        fragment: dict[str, Any],
        requested_operations: list[dict[str, Any]] | None = None,
        query: str = "",
    ) -> list[dict[str, Any]]:
        patches, _ = self.build_patch_models(previous, fragment, requested_operations, query)
        return [patch.to_change() for patch in patches]

    @staticmethod
    def _recompute_intent(plan: dict[str, Any], operations: set[PatchOperation]) -> None:
        if PatchOperation.REMOVE_ORDER in operations and plan.get("intent") == "ranking":
            plan["intent"] = "customer_selection" if any(
                item.get("type") == "metric" for item in ContextManager._filter_leaves(plan.get("filters", []))
            ) else "metric_query"
        if PatchOperation.CHANGE_ORDER in operations and plan.get("order_by"):
            plan["intent"] = "ranking"
        if PatchOperation.REMOVE_TIME_RANGE in operations and plan.get("intent") == "trend_analysis":
            plan["intent"] = "metric_query"

    @staticmethod
    def _recompute_status(
        plan: dict[str, Any],
        fragment: dict[str, Any],
        patches: list[PlanPatch],
        patch_ambiguities: list[dict[str, Any]],
        metrics: dict[str, Any] | None,
        query: str,
    ) -> None:
        metrics = metrics or {}
        successful_patch = any(patch.patch_status == "APPLIED" for patch in patches) or ContextManager.is_keep_request(query)
        ambiguities = deepcopy(patch_ambiguities)

        for item in plan.get("ambiguities", []):
            kind = item.get("type")
            if kind == "time" and plan.get("time_range") is not None:
                continue
            if kind == "metric" and plan.get("metrics"):
                continue
            ambiguities.append(deepcopy(item))
        if not successful_patch:
            ambiguities.extend(deepcopy(fragment.get("ambiguities", [])))
        elif any(marker in query for marker in ContextManager.REPLACE_MARKERS):
            # Preserve actual typed grounding ambiguity, but discard the planner's
            # generic "no standalone executable semantics" placeholder for a
            # completely grounded follow-up such as "改成 Q2".
            resolved_surfaces = []
            for patch in patches:
                if patch.patch_status != "APPLIED":
                    continue
                surface = str(patch.requested_new_value or "")
                for marker in ContextManager.REPLACE_MARKERS:
                    surface = surface.replace(marker, "")
                resolved_surfaces.append(re.sub(r"(?:客户|城市|地区|指标|维度|条件|等级)$", "", surface))
            for item in fragment.get("ambiguities", []):
                if item.get("type") == "other":
                    continue
                term = str(item.get("term") or "")
                for marker in ContextManager.REPLACE_MARKERS:
                    term = term.replace(marker, "")
                term = re.sub(r"(?:客户|城市|地区|指标|维度|条件|等级)$", "", term)
                if term and any(term in surface or surface in term for surface in resolved_surfaces if surface):
                    continue
                ambiguities.append(deepcopy(item))

        if any(
            metrics.get(metric_id, {}).get("constraints", {}).get("required_time_range")
            for metric_id in plan.get("metrics", [])
        ) and plan.get("time_range") is None and not any(item.get("type") == "time" for item in ambiguities):
            ambiguities.append({
                "term": "统计期间", "type": "time",
                "reason": "Patch 后指标仍要求明确统计期间。",
                "question": "请补充日期范围、月份或季度。", "candidates": [],
            })
        if not plan.get("metrics") and not any(item.get("type") == "metric" for item in ambiguities):
            ambiguities.append({
                "term": "指标", "type": "metric", "reason": "Patch 后没有可执行指标。",
                "question": "请指定要查询的指标。", "candidates": [],
            })

        deduped: list[dict[str, Any]] = []
        seen = set()
        for item in ambiguities:
            key = (item.get("type"), item.get("term"), item.get("reason"))
            if key not in seen:
                seen.add(key)
                deduped.append(item)
        plan["ambiguities"] = deduped
        plan["status"] = "needs_clarification" if deduped else "ready"
        confidence = 0.5 if deduped else 1.0
        confidence_block = plan.setdefault("confidence", {})
        confidence_block["overall"] = confidence
        if not deduped:
            for component in ("intent", "metrics", "dimensions", "entities", "time", "filters"):
                confidence_block[component] = 1.0

    def apply(
        self,
        previous: dict[str, Any],
        fragment: dict[str, Any],
        parent_plan_id: str | None = None,
        requested_operations: list[dict[str, Any]] | None = None,
        *,
        query: str = "",
        metrics: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        merged = deepcopy(previous)
        patches, patch_ambiguities = self.build_patch_models(previous, fragment, requested_operations, query)
        operations = {patch.operation for patch in patches}
        for patch in patches:
            if patch.patch_status != "APPLIED":
                continue
            action, target = patch.operation, patch.target
            if action == PatchOperation.ADD_FILTER:
                merged.setdefault("filters", []).append(deepcopy(patch.new_value))
            elif action == PatchOperation.REMOVE_FILTER:
                merged["filters"] = self._rewrite_filters(merged.get("filters", []), target, None)
            elif action == PatchOperation.REPLACE_FILTER:
                merged["filters"] = self._rewrite_filters(merged.get("filters", []), target, patch.new_value)
                if not self._find_filters(previous, target):
                    merged.setdefault("filters", []).append(deepcopy(patch.new_value))
            elif action == PatchOperation.ADD_METRIC:
                merged["metrics"] = list(dict.fromkeys([*merged.get("metrics", []), patch.new_value]))
            elif action == PatchOperation.REMOVE_METRIC:
                merged["metrics"] = [item for item in merged.get("metrics", []) if item != target]
                merged["order_by"] = [item for item in merged.get("order_by", []) if item.get("field") != target]
            elif action == PatchOperation.REPLACE_METRIC:
                old_metrics = set(merged.get("metrics", []))
                merged["metrics"] = [patch.new_value]
                merged["order_by"] = [
                    {**item, "field": patch.new_value} if item.get("field") in old_metrics else item
                    for item in merged.get("order_by", [])
                ]
            elif action == PatchOperation.CHANGE_TIME_RANGE:
                merged["time_range"] = deepcopy(patch.new_value)
            elif action == PatchOperation.REMOVE_TIME_RANGE:
                merged["time_range"] = None
            elif action == PatchOperation.CHANGE_ORDER:
                merged["order_by"] = deepcopy(patch.new_value)
            elif action == PatchOperation.REMOVE_ORDER:
                merged["order_by"] = []
            elif action == PatchOperation.CHANGE_LIMIT:
                merged["limit"] = patch.new_value
            elif action == PatchOperation.REMOVE_LIMIT:
                merged["limit"] = None
            elif action == PatchOperation.ADD_DIMENSION:
                merged["dimensions"] = list(dict.fromkeys([*merged.get("dimensions", []), patch.new_value or target]))
            elif action == PatchOperation.REMOVE_DIMENSION:
                merged["dimensions"] = [item for item in merged.get("dimensions", []) if item != target]
                merged["group_by"] = [item for item in merged.get("group_by", []) if item != target]
            elif action == PatchOperation.REPLACE_DIMENSION:
                merged["dimensions"] = [patch.new_value if item == target else item for item in merged.get("dimensions", [])]
                merged["group_by"] = [patch.new_value if item == target else item for item in merged.get("group_by", [])]

        if fragment.get("entities"):
            by_type = {item.get("entity_type"): item for item in merged.get("entities", [])}
            for entity in fragment["entities"]:
                by_type[entity.get("entity_type")] = deepcopy(entity)
            merged["entities"] = list(by_type.values())
        filter_dimensions = [
            item.get("target") for item in self._filter_leaves(merged.get("filters", []))
            if item.get("type") == "dimension" and item.get("target")
        ]
        merged["dimensions"] = list(dict.fromkeys([*merged.get("dimensions", []), *filter_dimensions]))
        self._recompute_intent(merged, operations)
        self._recompute_status(merged, fragment, patches, patch_ambiguities, metrics, query)
        merged["context"] = {
            "parent_plan_id": parent_plan_id or previous.get("context", {}).get("parent_plan_id") or "previous_plan",
            "operation": "refine",
        }
        changes = [patch.to_change() for patch in patches]
        return merged, changes
