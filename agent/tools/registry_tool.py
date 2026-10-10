from __future__ import annotations

from agent.models import ToolResult
from agent.services.metadata_store import MetadataStore


class RegistryTool:
    FILES = {
        "intent": ("intent_registry.yaml", "intents"),
        "metric": ("metrics.yaml", "metrics"),
        "dimension": ("dimensions.yaml", "dimensions"),
        "concept": ("business_dictionary.yaml", "dictionary"),
        "operator": ("operator_registry.yaml", "operators"),
        "time_type": ("time_semantics.yaml", "time_types"),
        "entity_type": ("entity_rules.yaml", "entities"),
    }

    def __init__(self, store: MetadataStore | None = None):
        self.store = store or MetadataStore()

    def ids(self, registry_type: str) -> set[str]:
        if registry_type not in self.FILES:
            return set()
        filename, key = self.FILES[registry_type]
        return set(self.store.yaml(filename).get(key, {}))

    def check(self, registry_type: str, identifier: str) -> ToolResult:
        if registry_type not in self.FILES:
            return ToolResult.fail("UNKNOWN_REGISTRY", f"未知 Registry 类型: {registry_type}", "registry_tool")
        filename, _ = self.FILES[registry_type]
        exists = identifier in self.ids(registry_type)
        if not exists:
            return ToolResult.fail(
                f"UNKNOWN_{registry_type.upper()}",
                f"{registry_type} 未注册: {identifier}",
                self.store.source(filename),
            )
        return ToolResult.ok({"type": registry_type, "id": identifier, "registered": True}, self.store.source(filename))

