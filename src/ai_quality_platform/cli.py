from __future__ import annotations

import argparse
import os
from pathlib import Path

from .providers.base import create_provider
from .autofix import run_autofix
from .config import load_ai_quality_config
from .diff import read_diff
from .review import review_diff
from .reviewers import final_audit, review_documentation, review_requirements, review_tests, to_json_ready
from .schema import validate_against_schema, validate_review_result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ai-quality-platform")
    parser.add_argument("--config", default=".ai-quality.yml")
    parser.add_argument("--diff", default=None)
    parser.add_argument("--autofix-root", default=None)
    parser.add_argument("--github-pr", action="store_true", help="Post report to GitHub PR")
    args = parser.parse_args(argv)

    config = load_ai_quality_config(Path(args.config))
    provider_name = config.ai.get("provider", "openai")
    api_key = os.environ.get("AI_API_KEY", "")
    
    # Load Role-based models
    models_config = config.ai.get("models", {})
    if not models_config:
        # Fallback to legacy single model configuration
        base_model = config.ai.get("model", "gpt-4o-mini")
        models_config = {
            "review": base_model,
            "autofix": base_model,
            "fallback": base_model,
            "audit": base_model,
            "report": base_model
        }
        
    def _get_provider(role: str) -> Provider | None:
        model = models_config.get(role)
        if not model:
            return None
        try:
            return create_provider(provider_name, model, api_key)
        except Exception as e:
            print(f"Provider initialization warning for {role}: {e}")
            return None

    provider_review = _get_provider("review")
    provider_autofix = _get_provider("autofix")
    provider_fallback = _get_provider("fallback")
    provider_audit = _get_provider("audit")
    provider_report = _get_provider("report")

    diff_text = read_diff(Path(args.diff)) if args.diff else ""
    
    # Unified Review
    unified = unified_review(diff_text, provider_review)
    audit = final_audit([unified], diff_text, provider=provider_audit)
    
    for result in [unified, audit]:
        from .reviewers import to_json_ready
        payload = to_json_ready(result)
        validate_review_result(payload)
        validate_against_schema(payload, Path("schemas/review-result.schema.json"))
        
    if args.autofix_root:
        import subprocess
        def current_review_fn(root_path: Path):
            proc = subprocess.run(["git", "diff", "HEAD"], capture_output=True, text=True, encoding="utf-8", cwd=root_path)
            new_diff = proc.stdout
            from .reviewers import unified_review
            return [unified_review(new_diff, provider_review)]
            
        outcome, current_reviews = run_autofix(
            Path(args.autofix_root), 
            [unified], 
            provider=provider_autofix,
            fallback_provider=provider_fallback,
            review_fn=current_review_fn,
            max_rounds=3
        )
        
        audit = final_audit(current_reviews, diff_text, provider=provider_audit)
        report_text = _render_full_report(current_reviews, audit, provider_report)
        report_text += "\n\n" + _render_autofix_block(outcome)
        print(report_text)
        
        if outcome.status == "PASS" and audit.verdict in {"PASS", "WARN"}:
            print("Autofix changes accepted. Committing and pushing to PR...")
            from .github import git_commit_and_push
            git_commit_and_push("auto: apply AI generated fixes")
            
        if args.github_pr:
            from .github import post_pr_comment
            post_pr_comment(report_text)
            
        return 0 if audit.verdict in {"PASS", "WARN"} else 1
    
    report_text = _render_full_report([unified], audit, provider_report)
    print(report_text)
    
    if args.github_pr:
        from .github import post_pr_comment
        post_pr_comment(report_text)
        
    return 0 if audit.verdict in {"PASS", "WARN"} else 1





def _render_full_report(reviews, audit, provider_report: Provider | None = None) -> str:
    lines = [
        "<!-- ai-quality-platform-report -->",
        "# AI品質管理レポート",
        "",
        "## 総合判定",
        "",
        f"**{audit.verdict}**",
        "",
        "## AIレビュー",
        "",
        "| 担当 | 判定 | 指摘数 |",
        "|---|---:|---:|",
    ]
    for review in reviews + [audit]:
        lines.append(f"| {review.reviewer} | {review.verdict} | {len(review.findings)} |")
    
    total_cost = sum(r.estimated_cost_jpy for r in reviews + [audit])
    if total_cost > 0:
        lines.extend(["", "### API Cost", "", f"Total estimated cost: ¥{total_cost:.2f}"])
        
    lines.extend(["", "## 変更概要", "", audit.summary])
    
    base_report = "\n".join(lines)
    
    if provider_report:
        try:
            print(f"Formatting report with {provider_report.model}...")
            # We skip JSON schema here and just ask for Markdown text
            response = provider_report.generate_review(
                system_prompt="あなたは優秀なテクニカルライターです。入力されたレビュー結果を元に、人間が読みやすいMarkdownレポートに整形して出力してください。不要な挨拶は省き、レポート本体のみを出力してください。",
                user_prompt=base_report,
                schema=None
            )
            return response.content.strip()
        except Exception as e:
            print(f"Report generation error ({provider_report.model}): {e}")
            return base_report
            
    return base_report


def _render_autofix_block(outcome) -> str:
    return "\n".join(
        [
            "",
            "## 自動修正",
            "",
            f"- 判定: {outcome.status}",
            f"- 反復回数: {outcome.rounds}",
            f"- 変更ファイル数: {len(outcome.changed_files)}",
            f"- 再発 finding: {', '.join(outcome.repeated_finding_ids) if outcome.repeated_finding_ids else 'なし'}",
            f"- 理由: {outcome.reason}",
        ]
    )

if __name__ == "__main__":
    raise SystemExit(main())
