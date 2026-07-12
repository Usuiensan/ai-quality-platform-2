from __future__ import annotations

import argparse
import os
from pathlib import Path

from .providers.base import create_provider
from .autofix import run_autofix
from .config import load_ai_quality_config
from .diff import read_diff
from .review import review_diff
from .reviewers import final_audit, unified_review, to_json_ready
from .schema import validate_against_schema, validate_review_result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ai-quality-platform")
    parser.add_argument("--config", default=".ai-quality.yml")
    parser.add_argument("--diff", default=None)
    parser.add_argument("--autofix-root", default=None)
    parser.add_argument("--github-pr", action="store_true", help="Post report to GitHub PR")
    parser.add_argument("--urgent", action="store_true", help="Run in high-performance mode using cloud APIs")
    parser.add_argument("--yes", "-y", action="store_true", help="Automatically approve budget estimates")
    args = parser.parse_args(argv)

    config = load_ai_quality_config(Path(args.config))
    provider_name = config.ai.get("provider", "openai")
    api_key = os.environ.get("AI_API_KEY", "")
    
    diff_text = read_diff(Path(args.diff)) if args.diff else ""
    
    if args.urgent:
        from .pricing import estimate_tokens, select_urgent_models, estimate_cost_jpy
        input_tokens = estimate_tokens(diff_text)
        print(f"[Urgent Mode] Estimated input tokens: {input_tokens}")
        models_config = select_urgent_models(input_tokens)
        provider_name = "openai" if "gpt" in models_config["review"] else "gemini"
        
        # Estimate output tokens (rough guess: 10% of input, min 500)
        input_tokens = estimate_tokens(diff_text)
        
        # Calculate conservative multi-stage cost
        # Review
        cost_review = estimate_cost_jpy(models_config["review"], input_tokens, 1500)
        # Autofix (Assume 1 round + 1 fallback round for safety)
        cost_autofix = estimate_cost_jpy(models_config["autofix"], input_tokens, 2000)
        cost_fallback = estimate_cost_jpy(models_config["fallback"], input_tokens, 2000)
        # Audit
        cost_audit = estimate_cost_jpy(models_config["audit"], input_tokens, 1000)
        # Report (approx 3000 input, 2000 output)
        cost_report = estimate_cost_jpy(models_config["report"], 3000, 2000)
        
        raw_cost = cost_review + cost_autofix + cost_fallback + cost_audit + cost_report
        # Apply 1.2x safety factor
        safe_cost = raw_cost * 1.2
        
        # Rounding up (e.g., to nearest 10 if > 10, else to integer)
        import math
        if safe_cost > 10.0:
            cost = math.ceil(safe_cost / 10.0) * 10.0
        elif safe_cost >= 1.0:
            cost = float(math.ceil(safe_cost))
        else:
            cost = safe_cost  # Keep under 1.0 raw for auto-approval

        print(f"[Urgent Mode] Selected provider: {provider_name}")
        print(f"[Urgent Mode] Models: {models_config}")
        print(f"[Urgent Mode] Estimated Max Cost: JPY {cost:.2f}")
        
        if cost < 1.0:
            print(f"Cost is under 1 JPY ({cost:.2f} JPY). Auto-approving.")
        elif cost <= 100.0:
            if not args.yes:
                reply = input(f"Approve estimated max cost of JPY {cost:.2f}? Type 'ok' to proceed: ")
                if reply.strip().lower() != "ok":
                    print("Aborted by user.")
                    return 1
        else:
            if not args.yes:
                try:
                    from num2words import num2words
                    words = num2words(int(cost)).replace(" ", "-").replace(",", "")
                    expected_str = f"{words}-JPY"
                except ImportError:
                    expected_str = f"{int(cost)}-JPY"
                
                print(f"High cost warning! Estimated cost is JPY {cost:.2f}.")
                reply = input(f"To approve, please type exactly '{expected_str}': ")
                if reply.strip().lower() != expected_str.lower():
                    print("Aborted by user. Input did not match.")
                    return 1
    else:
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
        lines.extend(["", "### API Cost", "", f"Total estimated cost: JPY {total_cost:.2f}"])
        
    lines.extend(["", "## 変更概要", "", audit.summary])
    
    base_report = "\n".join(lines)
    
    if provider_report:
        try:
            print(f"Formatting report with {provider_report.model}...")
            # We skip JSON schema here and just ask for Markdown text
            response = provider_report.generate_review(
                system_prompt="You are an excellent technical writer. Based on the input review results, format them into a human-readable Markdown report. Output MUST be in Japanese. Omit unnecessary greetings and output only the report body.",
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
