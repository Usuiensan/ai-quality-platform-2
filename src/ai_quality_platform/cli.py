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
    model = config.ai.get("model", "gpt-4o-mini")
    api_key = os.environ.get("AI_API_KEY", "")
    try:
        provider = create_provider(provider_name, model, api_key)
    except Exception as e:
        print(f"Provider initialization warning: {e}")
        provider = None

    diff_text = read_diff(Path(args.diff)) if args.diff else ""
    code_review = review_diff(diff_text, provider)
    requirements_review = review_requirements(diff_text, provider=provider)
    tests_review = review_tests(diff_text, provider=provider)
    docs_review = review_documentation(diff_text, provider=provider)
    audit = final_audit([code_review, requirements_review, tests_review, docs_review], diff_text, provider=provider)
    for result in [code_review, requirements_review, tests_review, docs_review, audit]:
        payload = to_json_ready(result)
        validate_review_result(payload)
        validate_against_schema(payload, Path("schemas/review-result.schema.json"))
    if args.autofix_root:
        import subprocess
        def current_review_fn(root_path: Path):
            # ワーキングツリーの最新のdiffを取得して再レビュー
            proc = subprocess.run(["git", "diff", "HEAD"], capture_output=True, text=True, cwd=root_path)
            new_diff = proc.stdout
            return [
                review_diff(new_diff, provider),
                review_requirements(new_diff, provider=provider),
                review_tests(new_diff, provider=provider),
                review_documentation(new_diff, provider=provider),
            ]
            
        outcome, current_reviews = run_autofix(
            Path(args.autofix_root), 
            [code_review, requirements_review, tests_review, docs_review], 
            provider=provider,
            review_fn=current_review_fn,
            max_rounds=3
        )
        
        # Autofix後の状態を最終監査にかける
        audit = final_audit(current_reviews, diff_text, provider=provider)
        report_text = _render_full_report(current_reviews, audit)
        report_text += "\n\n" + _render_autofix_block(outcome)
        print(report_text)
        
        # 受け入れ判定（OKならコミットしてPush）
        if outcome.status == "PASS" and audit.verdict in {"PASS", "WARN"}:
            print("Autofix changes accepted. Committing and pushing to PR...")
            from .github import git_commit_and_push
            git_commit_and_push("auto: apply AI generated fixes")
            
        if args.github_pr:
            from .github import post_pr_comment
            post_pr_comment(report_text)
            
        return 0 if audit.verdict in {"PASS", "WARN"} else 1
    
    report_text = _render_full_report([code_review, requirements_review, tests_review, docs_review], audit)
    print(report_text)
    
    if args.github_pr:
        from .github import post_pr_comment
        post_pr_comment(report_text)
        
    return 0 if audit.verdict in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())


def _render_full_report(reviews, audit) -> str:
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
    return "\n".join(lines)


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
