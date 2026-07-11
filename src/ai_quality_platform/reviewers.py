from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from .models import Finding, ReviewResult
from .providers.base import Provider
from .review import render_report, run_ai_review

def _base_result(reviewer: str) -> ReviewResult:
    return ReviewResult(reviewer=reviewer, verdict="PASS", summary="修正が必要な問題は見つかりませんでした。")

def review_requirements(diff_text: str, issue_text: str = "", pr_text: str = "", provider: Provider | None = None) -> ReviewResult:
    if provider is None:
        return _base_result("requirements")
        
    system_prompt = ""
    prompt_path = Path("prompts/requirements.md")
    if prompt_path.exists():
        system_prompt = prompt_path.read_text(encoding="utf-8")
    
    system_prompt += "\n\nあなたは要求・仕様のレビュアーです。必ず指定されたJSONフォーマットで回答してください。"
    
    user_prompt = f"以下の情報をレビューしてください:\n\n【Issue/要求内容】\n{issue_text}\n\n【PR本文】\n{pr_text}\n\n【Git差分】\n```diff\n{diff_text}\n```"
    
    return run_ai_review(provider, system_prompt, user_prompt, "requirements")



def review_tests(diff_text: str, ci_text: str = "", provider: Provider | None = None) -> ReviewResult:
    if provider is None:
        return _base_result("tests")
        
    system_prompt = ""
    prompt_path = Path("prompts/tests.md")
    if prompt_path.exists():
        system_prompt = prompt_path.read_text(encoding="utf-8")
        
    system_prompt += "\n\nあなたはテストのレビュアーです。必ず指定されたJSONフォーマットで回答してください。"
    
    user_prompt = f"以下の情報をレビューしてください:\n\n【CI実行結果】\n{ci_text}\n\n【Git差分】\n```diff\n{diff_text}\n```"
    
    return run_ai_review(provider, system_prompt, user_prompt, "tests")



def review_documentation(diff_text: str, readme_text: str = "", provider: Provider | None = None) -> ReviewResult:
    if provider is None:
        return _base_result("documentation")
        
    system_prompt = ""
    prompt_path = Path("prompts/documentation.md")
    if prompt_path.exists():
        system_prompt = prompt_path.read_text(encoding="utf-8")
        
    system_prompt += "\n\nあなたはドキュメントのレビュアーです。必ず指定されたJSONフォーマットで回答してください。"
    
    user_prompt = f"以下の情報をレビューしてください:\n\n【現在のREADME等】\n{readme_text}\n\n【Git差分】\n```diff\n{diff_text}\n```"
    
    return run_ai_review(provider, system_prompt, user_prompt, "documentation")



def final_audit(reviews: list[ReviewResult], diff_text: str, ci_text: str = "", provider: Provider | None = None) -> ReviewResult:
    if provider is None:
        result = ReviewResult(reviewer="final_audit", verdict="PASS", summary="最終監査でブロック要因は見つかりませんでした。")
        return result

    system_prompt = ""
    prompt_path = Path("prompts/final-audit.md")
    if prompt_path.exists():
        system_prompt = prompt_path.read_text(encoding="utf-8")
        
    system_prompt += "\n\nあなたは最終的な監査役です。他のAIレビュー結果を含めて総合的に判断し、必ず指定されたJSONフォーマットで回答してください。"
    
    import json
    reviews_data = [to_json_ready(r) for r in reviews]
    reviews_json = json.dumps(reviews_data, ensure_ascii=False, indent=2)
    
    user_prompt = f"以下の情報をレビューしてください:\n\n【各レビュアーの判定結果】\n```json\n{reviews_json}\n```\n\n【Git差分】\n```diff\n{diff_text}\n```\n\n【CI実行結果】\n{ci_text}"
    
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

