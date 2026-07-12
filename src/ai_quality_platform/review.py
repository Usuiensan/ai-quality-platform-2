from __future__ import annotations

import json
from pathlib import Path

from .models import Finding, ReviewResult
from .providers.base import Provider


def run_ai_review(provider: Provider | None, system_prompt: str, user_prompt: str, reviewer_name: str) -> ReviewResult:
    if provider is None:
        return ReviewResult(reviewer=reviewer_name, verdict="ERROR", summary="プロバイダが設定されていません。")

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
            reviewer=data.get("reviewer", reviewer_name),
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
            reviewer=reviewer_name,
            verdict="ERROR",
            summary=f"LLMプロバイダ呼び出しエラー: {e}"
        )


def review_diff(diff_text: str, provider: Provider | None = None) -> ReviewResult:
    if provider is None:
        findings: list[Finding] = []
        lowered = diff_text.lower()
        if "..\\" in diff_text or "../" in diff_text:
            findings.append(
                Finding(
                    id="SEC-002",
                    severity="high",
                    category="path-traversal",
                    file="",
                    line_start=0,
                    line_end=0,
                    title="相対パスの上位参照があります",
                    description="差分内に上位ディレクトリ参照が含まれており、意図しないファイル書き換えの恐れがあります。",
                    recommendation="許可されたベースディレクトリの外への書き込みを禁止してください。",
                    blocking=True,
                    confidence=0.91,
                )
            )
        if ".github/workflows/" in lowered:
            findings.append(
                Finding(
                    id="CODE-002",
                    severity="medium",
                    category="workflow-change",
                    file=".github/workflows/",
                    line_start=0,
                    line_end=0,
                    title="ワークフロー変更が含まれています",
                    description="ワークフロー変更は権限や実行経路に影響します。",
                    recommendation="人間確認対象として扱ってください。",
                    blocking=False,
                    confidence=0.88,
                )
            )
        if "curl " in diff_text or "Invoke-WebRequest" in diff_text:
            findings.append(
                Finding(
                    id="SEC-001",
                    severity="high",
                    category="shell-injection",
                    file="",
                    line_start=0,
                    line_end=0,
                    title="外部入力をシェル実行へ渡す可能性があります",
                    description="差分内にシェル呼び出しがあり、引数検証が不十分な場合に危険です。",
                    recommendation="シェル文字列連結を避け、引数を分離してください。",
                    blocking=True,
                    confidence=0.82,
                )
            )
        if "requirements.txt" in lowered or "package.json" in lowered:
            findings.append(
                Finding(
                    id="REQ-001",
                    severity="medium",
                    category="dependency-change",
                    file="",
                    line_start=0,
                    line_end=0,
                    title="依存関係の変更が含まれています",
                    description="依存関係の変更は供給網リスクと動作変化を伴います。",
                    recommendation="追加確認を行ってください。",
                    blocking=False,
                    confidence=0.8,
                )
            )
        if "os.remove(" in diff_text and "finally" not in lowered:
            findings.append(
                Finding(
                    id="CODE-001",
                    severity="medium",
                    category="resource-cleanup",
                    file="",
                    line_start=0,
                    line_end=0,
                    title="例外時の後始末が不足しています",
                    description="一時ファイル削除が例外経路で保証されていない可能性があります。",
                    recommendation="finally で後始末してください。",
                    blocking=False,
                    confidence=0.74,
                )
            )

        verdict = "PASS"
        if any(f.severity == "critical" for f in findings) or any(f.blocking for f in findings):
            verdict = "BLOCK"
        elif findings:
            verdict = "WARN"

        summary = "差分を確認し、重大な問題は見つかりませんでした。" if verdict == "PASS" else "差分に修正が必要な項目があります。"
        return ReviewResult(reviewer="code", verdict=verdict, summary=summary, findings=findings)

    system_prompt = ""
    code_prompt_path = Path("prompts/code.md")
    if code_prompt_path.exists():
        system_prompt = code_prompt_path.read_text(encoding="utf-8")
    
    system_prompt += "\n\nあなたはコードレビューアです。以下の差分を確認し、ロジック不備、エラーハンドリング、セキュリティリスク、可読性などを指摘してください。必ず指定されたJSONフォーマットで回答してください。"
    
    user_prompt = f"以下のGit差分をレビューしてください:\n\n```diff\n{diff_text}\n```"
    
    return run_ai_review(provider, system_prompt, user_prompt, "code")


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
