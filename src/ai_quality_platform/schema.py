from __future__ import annotations

import json
from pathlib import Path


def load_json_schema(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


REVIEW_RESULT_SCHEMA = {
    "type": "object",
    "required": ["reviewer", "verdict", "summary", "findings", "tested", "not_tested"],
}


def validate_review_result(payload: dict) -> None:
    required = REVIEW_RESULT_SCHEMA["required"]
    missing = [name for name in required if name not in payload]
    if missing:
        raise ValueError(f"不足している必須キー: {', '.join(missing)}")
    if payload["verdict"] not in {"PASS", "WARN", "BLOCK", "ERROR"}:
        raise ValueError("不正な verdict です")


def parse_review_result(text: str) -> dict:
    if not text.strip():
        raise ValueError("AI 応答が空です")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("AI 応答の JSON 解析に失敗しました") from exc
    if not isinstance(payload, dict):
        raise ValueError("AI 応答の形式が不正です")
    validate_review_result(payload)
    return payload


def validate_against_schema(payload: dict, schema_path: Path) -> None:
    schema = load_json_schema(schema_path)
    required = schema.get("required", [])
    missing = [name for name in required if name not in payload]
    if missing:
        raise ValueError(f"JSON Schema の必須キーが不足しています: {', '.join(missing)}")
    verdict_schema = schema.get("properties", {}).get("verdict", {})
    allowed = verdict_schema.get("enum")
    if allowed and payload.get("verdict") not in allowed:
        raise ValueError("JSON Schema に対して verdict が不正です")
