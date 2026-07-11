from __future__ import annotations

import json
from pathlib import Path

from .models import Finding, ReviewResult
from .providers.base import Provider


def review_diff(diff_text: str, provider: Provider | None = None) -> ReviewResult:
    if provider is None:
        return ReviewResult(reviewer="code", verdict="ERROR", summary="プロバイダが設定されていません。")

    system_prompt = ""
    code_prompt_path = Path("prompts/code.md")
    if code_prompt_path.exists():
        system_prompt = code_prompt_path.read_text(encoding="utf-8")
    
    system_prompt += "\n\nあなたはコードレビューアです。以下の差分を確認し、ロジック不備、エラーハンドリング、セキュリティリスク、可読性などを指摘してください。必ず指定されたJSONフォーマットで回答してください。"
    
    user_prompt = f"以下のGit差分をレビューしてください:\n\n```diff\n{diff_text}\n```"
    
    schema = {
        "type": "object",
        "properties": {
            "reviewer": {"type": "string"},
            "verdict": {"type": "string", "enum": ["PASS", "WARN", "BLOCK", "ERROR"]},
            "summary": {"type": "string"},
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "severity": {"type": "string", "enum": ["info", "low", "medium", "high", "critical"]},
                        "category": {"type": "string"},
                        "file": {"type": "string"},
                        "line_start": {"type": "integer"},
                        "line_end": {"type": "integer"},
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "recommendation": {"type": "string"},
                        "blocking": {"type": "boolean"},
                        "confidence": {"type": "number"}
                    },
                    "required": ["id", "severity", "category", "file", "line_start", "line_end", "title", "description", "recommendation", "blocking", "confidence"]
                }
            },
            "tested": {"type": "array", "items": {"type": "string"}},
            "not_tested": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["reviewer", "verdict", "summary", "findings", "tested", "not_tested"]
    }
    
    try:
        response = provider.generate_review(system_prompt=system_prompt, user_prompt=user_prompt, schema=schema)
        # 応答のJSONをパース
        # Markdownのコードブロック ```json ... ``` で囲まれている場合を考慮
        content = response.content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        
        data = json.loads(content.strip())
        
        findings = []
        for f in data.get("findings", []):
            findings.append(Finding(
                id=f.get("id", ""),
                severity=f.get("severity", "info"),
                category=f.get("category", ""),
                file=f.get("file", ""),
                line_start=f.get("line_start", 0),
                line_end=f.get("line_end", 0),
                title=f.get("title", ""),
                description=f.get("description", ""),
                recommendation=f.get("recommendation", ""),
                blocking=f.get("blocking", False),
                confidence=f.get("confidence", 0.0)
            ))
        
        return ReviewResult(
            reviewer="code",
            verdict=data.get("verdict", "ERROR"),
            summary=data.get("summary", "エラー"),
            findings=findings,
            tested=data.get("tested", []),
            not_tested=data.get("not_tested", []),
            usage_tokens=response.usage.total_tokens,
            estimated_cost_jpy=response.usage.estimated_cost_jpy
        )
    except Exception as e:
        return ReviewResult(
            reviewer="code",
            verdict="ERROR",
            summary=f"LLMプロバイダ呼び出しエラー: {e}"
        )


def render_report(result: ReviewResult) -> str:
    status = {"PASS": "PASS", "WARN": "WARN", "BLOCK": "BLOCK", "ERROR": "ERROR"}.get(result.verdict, "ERROR")
    lines = [
        "<!-- ai-quality-platform-report -->",
        "# AI品質管理レポート",
        "",
        "## 総合判定",
        "",
        f"**{status}**",
        "",
        "## AIレビュー",
        "",
        "| 担当 | 判定 | 指摘数 |",
        "|---|---:|---:|",
        f"| {result.reviewer} | {status} | {len(result.findings)} |",
        "",
        "## 変更概要",
        "",
        result.summary,
    ]
    return "\n".join(lines)


def build_reusable_diff_summary(changed_files: list[str]) -> str:
    return "\n".join(f"- {path}" for path in changed_files)
