from pathlib import Path
import sys
import yaml


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


FILES = [
    Path("metadata/value_mappings.yaml"),
    Path("metadata/concept_aliases.yaml"),
    Path("metadata/business_dictionary.yaml"),
    Path("metadata/segment_rules.yaml"),
    Path("metadata/entity_rules.yaml"),
    Path("metadata/ambiguity_rules.yaml"),
    Path("metadata/intent_registry.yaml"),
    Path("metadata/operator_registry.yaml"),
    Path("metadata/time_semantics.yaml"),
    Path("metadata/query_capabilities.yaml"),
    Path("metadata/query_plan_confidence.yaml"),
    Path("metadata/agent_language.yaml"),
]
def check_yaml(path: Path):
    print("=" * 60)
    print(f"检查文件: {path}")

    if not path.exists():
        print("❌ 文件不存在")
        return False

    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        print("✅ YAML 语法正确")

        if data is None:
            print("⚠ 文件可以解析，但内容为空")
        elif isinstance(data, dict):
            print(f"顶层键: {list(data.keys())}")
        else:
            print(f"顶层数据类型: {type(data).__name__}")

        return True

    except yaml.YAMLError as e:
        print("❌ YAML 语法错误")
        print(e)
        return False

    except UnicodeDecodeError as e:
        print("❌ 文件编码不是 UTF-8")
        print(e)
        return False

    except Exception as e:
        print("❌ 其他错误")
        print(e)
        return False


def main():
    success = True

    for path in FILES:
        if not check_yaml(path):
            success = False

    print("=" * 60)

    if success:
        print("✅  YAML 文件全部检查通过")
    else:
        print("❌ 至少有一个 YAML 文件存在问题")


if __name__ == "__main__":
    main()
