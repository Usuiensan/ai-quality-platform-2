from __future__ import annotations

import json


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
