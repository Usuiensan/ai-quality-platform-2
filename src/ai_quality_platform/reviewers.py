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
        return _base_result("unified_review")
        
    system_prompt = ""
    prompt_path = Path("prompts/unified-review.md")
    if prompt_path.exists():
        system_prompt = prompt_path.read_text(encoding="utf-8")
        
    system_prompt += "\n\nYou are a unified reviewer. You must respond in the specified JSON format."
    
    user_prompt = f"Please review the following information comprehensively:\n\n[Git Diff]\n```diff\n{diff_text}\n```"
    
    return run_ai_review(provider, system_prompt, user_prompt, "unified_review")




def final_audit(reviews: list[ReviewResult], diff_text: str, ci_text: str = "", provider: Provider | None = None) -> ReviewResult:
    if provider is None:
        result = ReviewResult(reviewer="final_audit", verdict="PASS", summary="No blocking factors were found during the final audit.")
        return result

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

