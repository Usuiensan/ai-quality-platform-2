from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class Finding:
    id: str
    severity: str
    category: str
    file: str
    line_start: int
    line_end: int
    title: str
    description: str
    recommendation: str
    blocking: bool
    confidence: float


@dataclass(slots=True)
class ReviewResult:
    reviewer: str
    verdict: str
    summary: str
    findings: list[Finding] = field(default_factory=list)
    tested: list[str] = field(default_factory=list)
    not_tested: list[str] = field(default_factory=list)


def review_diff(diff_text: str) -> ReviewResult:
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
