from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from .models import Finding, ReviewResult
from .providers.base import Provider
from .review import render_report, run_ai_review

def _base_result(reviewer: str) -> ReviewResult:
    return ReviewResult(reviewer=reviewer, verdict="PASS", summary="No issues requiring fix were found.")

def unified_review(diff_text: str, provider: Provider | None = None) -> ReviewResult:
    if provider is None:
        from .review import review_diff
        result = review_diff(diff_text, None)
        result.reviewer = "unified_review"
        return result
        
    system_prompt = ""
    prompt_path = Path("prompts/unified-review.md")
    if prompt_path.exists():
        system_prompt = prompt_path.read_text(encoding="utf-8")
        
    system_prompt += "\n\nYou are a unified reviewer. You must respond in the specified JSON format."
    
    user_prompt = f"Please review the following information comprehensively:\n\n[Git Diff]\n```diff\n{diff_text}\n```"
    
    return run_ai_review(provider, system_prompt, user_prompt, "unified_review")




def final_audit(reviews: list[ReviewResult], diff_text: str, ci_text: str = "", provider: Provider | None = None) -> ReviewResult:
    if provider is None:
        result = ReviewResult(reviewer="final_audit", verdict="PASS", summary="最終監査でブロック要因は見つかりませんでした。")
        combined = f"{diff_text}\n{ci_text}".lower()
        findings: list[Finding] = []
        if not reviews:
            findings.append(
                Finding(
                    id="AUDIT-001",
                    severity="high",
                    category="missing-input",
                    file="",
                    line_start=0,
                    line_end=0,
                    title="監査対象のレビュー結果がありません",
                    description="最終監査に必要な入力が不足しています。",
                    recommendation="各レビューを先に実行してください。",
                    blocking=True,
                    confidence=0.95,
                )
            )
        if any(review.verdict == "BLOCK" for review in reviews):
            findings.append(
                Finding(
                    id="AUDIT-002",
                    severity="high",
                    category="prior-block",
                    file="",
                    line_start=0,
                    line_end=0,
                    title="前段レビューでブロックが出ています",
                    description="いずれかのレビューがブロック判定です。",
                    recommendation="ブロック指摘を解消してから再監査してください。",
                    blocking=True,
                    confidence=0.93,
                )
            )
        if "workflow" in combined and "human review" not in combined and "human確認" not in combined:
            findings.append(
                Finding(
                    id="AUDIT-003",
                    severity="medium",
                    category="review-gap",
                    file="",
                    line_start=0,
                    line_end=0,
                    title="ワークフロー変更の人間確認が不足しています",
                    description="ワークフロー変更は権限や実行経路に直結します。",
                    recommendation="人間確認事項を PR に明記してください。",
                    blocking=False,
                    confidence=0.77,
                )
            )
        return _finalize(result, findings)

    system_prompt = ""
    prompt_path = Path("prompts/final-audit.md")
    if prompt_path.exists():
        system_prompt = prompt_path.read_text(encoding="utf-8")
        
    system_prompt += "\n\nYou are the final auditor. Make a comprehensive judgment including the other AI review results, and you must respond in the specified JSON format."
    
    import json
    reviews_data = [to_json_ready(r) for r in reviews]
    reviews_json = json.dumps(reviews_data, ensure_ascii=False, indent=2)
    
    user_prompt = f"Please review the following information:\n\n[Review Results]\n```json\n{reviews_json}\n```\n\n[Git Diff]\n```diff\n{diff_text}\n```\n\n[CI Results]\n{ci_text}"
    
    return run_ai_review(provider, system_prompt, user_prompt, "final_audit")



def _finalize(result: ReviewResult, findings: list[Finding]) -> ReviewResult:
    result.findings = findings
    if any(f.severity == "critical" for f in findings) or any(f.blocking for f in findings):
        result.verdict = "BLOCK"
    elif findings:
        result.verdict = "WARN"
    return result


def to_json_ready(result: ReviewResult) -> dict:
    payload = asdict(result)
    payload["findings"] = [asdict(finding) for finding in result.findings]
    return payload


def build_review_markdown(result: ReviewResult) -> str:
    return render_report(result)


def review_requirements(diff_text: str, issue_text: str = "") -> ReviewResult:
    result = _base_result("requirements")
    combined = f"{diff_text}\n{issue_text}".lower()
    findings: list[Finding] = []
    if "breaking change" in combined or "破壊的変更" in combined:
        findings.append(
            Finding(
                id="REQ-001",
                severity="high",
                category="backward-compatibility",
                file="",
                line_start=0,
                line_end=0,
                title="後方互換性の破壊が示唆されています",
                description="差分または説明に破壊的変更の可能性があります。",
                recommendation="影響範囲と移行手順を明記してください。",
                blocking=True,
                confidence=0.8,
            )
        )
    if "todo" in combined or "未実装" in combined:
        findings.append(
            Finding(
                id="REQ-002",
                severity="medium",
                category="acceptance-criteria",
                file="",
                line_start=0,
                line_end=0,
                title="未完了項目が残っています",
                description="受け入れ条件に対して未実装または未確認の項目があります。",
                recommendation="PR本文か差分で完了条件を満たすことを示してください。",
                blocking=False,
                confidence=0.76,
            )
        )
    if "docs" in combined and "readme" not in combined:
        findings.append(
            Finding(
                id="REQ-003",
                severity="low",
                category="documentation-alignment",
                file="",
                line_start=0,
                line_end=0,
                title="ドキュメント更新の整合性確認が必要です",
                description="説明と実装の差異がある可能性があります。",
                recommendation="README などの関連文書も確認してください。",
                blocking=False,
                confidence=0.55,
            )
        )
    return _finalize(result, findings)


def review_tests(diff_text: str, ci_text: str = "") -> ReviewResult:
    result = _base_result("tests")
    combined = f"{diff_text}\n{ci_text}".lower()
    findings: list[Finding] = []
    if "assert false" in combined or "skip" in combined:
        findings.append(
            Finding(
                id="TEST-001",
                severity="high",
                category="test-coverage",
                file="",
                line_start=0,
                line_end=0,
                title="失敗を隠すテスト変更の可能性があります",
                description="差分にテストの弱体化や回避が含まれている可能性があります。",
                recommendation="正常系と異常系の両方を確認してください。",
                blocking=True,
                confidence=0.79,
            )
        )
    if "pytest" not in combined and "test" in combined:
        findings.append(
            Finding(
                id="TEST-002",
                severity="medium",
                category="test-missing",
                file="",
                line_start=0,
                line_end=0,
                title="テスト実行方法が不明瞭です",
                description="変更内容に対する具体的なテスト実行が見えません。",
                recommendation="実施したテストコマンドを PR に記載してください。",
                blocking=False,
                confidence=0.72,
            )
        )
    return _finalize(result, findings)


def review_documentation(diff_text: str, readme_text: str = "") -> ReviewResult:
    result = _base_result("documentation")
    combined = f"{diff_text}\n{readme_text}".lower()
    findings: list[Finding] = []
    if "readme" not in combined and "docs" not in combined:
        findings.append(
            Finding(
                id="DOC-001",
                severity="medium",
                category="docs-missing",
                file="",
                line_start=0,
                line_end=0,
                title="利用者向け説明が不足しています",
                description="機能追加に対して README または運用説明の更新が見えません。",
                recommendation="導入手順、設定、注意事項を追記してください。",
                blocking=False,
                confidence=0.7,
            )
        )
    if "env" in combined and "example" not in combined:
        findings.append(
            Finding(
                id="DOC-002",
                severity="low",
                category="environment-variables",
                file="",
                line_start=0,
                line_end=0,
                title="環境変数の説明が具体的ではありません",
                description="環境変数の用途と例が不足しています。",
                recommendation="必要な環境変数と例を README に追加してください。",
                blocking=False,
                confidence=0.6,
            )
        )
    return _finalize(result, findings)


