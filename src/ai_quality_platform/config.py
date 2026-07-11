from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


from typing import Any

@dataclass(slots=True)
class AiQualityConfig:
    version: int = 1
    preset: str = "generic"
    risk_level: str = "medium"
    reviewers: dict[str, bool] = field(default_factory=dict)
    localization: dict[str, str] = field(default_factory=dict)
    ai: dict[str, Any] = field(default_factory=dict)
    budget: dict[str, Any] = field(default_factory=dict)


def load_ai_quality_config(path: Path) -> AiQualityConfig:
    if not path.exists():
        return AiQualityConfig()
    data = _parse_minimal_yaml(path.read_text(encoding="utf-8"))
    return AiQualityConfig(
        version=int(data.get("version", 1)),
        preset=str(data.get("preset", "generic")),
        risk_level=str(data.get("risk_level", "medium")),
        reviewers=dict(data.get("reviewers", {})),
        localization=dict(data.get("localization", {})),
        ai=dict(data.get("ai", {})),
        budget=dict(data.get("budget", {})),
    )


def _parse_minimal_yaml(text: str) -> dict:
    root: dict = {}
    stack: list[tuple[int, object]] = [(0, root)]
    current_key: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        content = line.lstrip(" ")

        while len(stack) > 1 and indent < stack[-1][0]:
            stack.pop()

        parent = stack[-1][1]
        if content.startswith("- "):
            if not isinstance(parent, list):
                raise ValueError("リスト構文の位置が不正です")
            parent.append(_parse_scalar(content[2:].strip()))
            continue

        if ":" not in content:
            raise ValueError(f"YAML の構文を解釈できません: {content}")

        key, value = content.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value == "":
            new_container: dict | list = {}
            if isinstance(parent, dict):
                parent[key] = new_container
                current_key = key
            else:
                raise ValueError("入れ子の配置が不正です")
            stack.append((indent + 2, new_container))
            continue

        parsed = _parse_scalar(value)
        if isinstance(parent, dict):
            parent[key] = parsed
            current_key = key
        else:
            raise ValueError("スカラー値の配置が不正です")

    return root


def _parse_scalar(value: str):
    if value in {"true", "false"}:
        return value == "true"
    if value.isdigit():
        return int(value)
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    return value

