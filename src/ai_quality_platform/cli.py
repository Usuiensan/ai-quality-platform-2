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
    base_url = config.ai.get("base_url") or os.environ.get("AI_BASE_URL", None)
    api_key_missing = (provider_name in {"openai", "gemini"} and not api_key)
    if api_key_missing:
        print("警告: AI_API_KEY が設定されていないため、AIモデルによる詳細なレビューはスキップされ、簡易的なローカルチェックのみ実行されます。")
    
    diff_text = read_diff(Path(args.diff)) if args.diff else ""
    
    def request_budget_approval(target_cost: float, prompt_prefix: str = "承認しますか？") -> bool:
        threshold = max(1.0, float(config.budget.get("auto_approve_threshold", 0.0)))
        if target_cost < threshold:
            print(f"コストが自動承認しきい値 ({threshold:.2f} JPY) 未満のため自動承認されました ({target_cost:.2f} JPY)。")
            return True
        elif target_cost <= 100.0:
            reply = input(f"{prompt_prefix} 見積もりコスト: {target_cost:.2f} JPY。進行するには 'ok' と入力してください: ")
            if reply.strip().lower() != "ok":
                print("ユーザーにより処理が中断されました。")
                return False
            return True
        else:
            try:
                from num2words import num2words
                integer_part = int(target_cost)
                # Generate words, strip 'and', and capitalize the first letter
                words = num2words(integer_part).replace(" and ", " ").capitalize()
                expected_str = f"{words} yen"
            except ImportError:
                expected_str = f"{target_cost:.2f} yen"
            
            # Load rejection words from external file
            rejection_words = [
                "takai", "haraeru", "fuck", "shit", "no", "abort", "cancel", "reject",
                "だめ", "ダメ", "高い", "払えるか"
            ]
            rejection_words_path = Path(__file__).parent / "rejection_words.json"
            if rejection_words_path.exists():
                try:
                    import json
                    rejection_words = json.loads(rejection_words_path.read_text(encoding="utf-8"))
                except Exception as e:
                    print(f"警告: 拒否ワードファイルの読み込みに失敗しました: {e}")
            
            number_keywords = {
                "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
                "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen",
                "eighteen", "nineteen", "twenty", "thirty", "forty", "fifty", "sixty", "seventy",
                "eighty", "ninety", "hundred", "thousand", "million", "billion", "yen", "and"
            }
            
            print(f"【高額警告】見積もりコストは JPY {target_cost:.2f} です。")
            while True:
                reply = input(f"承認するには、正確に '{expected_str}' と入力してください: ").strip()
                if reply == expected_str:
                    return True
                
                # Check rejection words
                reply_lower = reply.lower()
                words_in_reply = {w.strip("!,.-?\"'") for w in reply_lower.split()}
                
                is_reject = False
                for rw in rejection_words:
                    rw_lower = rw.lower()
                    # If it's alphanumeric and pure ASCII, check whole word
                    if rw_lower.isalnum() and all(c.isascii() for c in rw_lower):
                        if rw_lower in words_in_reply:
                            is_reject = True
                            break
                    else:
                        # Otherwise check substring (e.g. Japanese words)
                        if rw_lower in reply_lower:
                            is_reject = True
                            break
                
                if is_reject:
                    print("ユーザーにより処理が中断されました（ユーザーの拒否意図を伺わせる単語が検出されました）。")
                    return False
                
                # Check if it looks like an attempted spell-out or numbers (for typo check)
                words_in_reply_loose = {w.lower() for w in reply.replace("-", " ").replace(",", "").split()}
                has_number_kw = bool(words_in_reply_loose & number_keywords)
                has_digits = any(char.isdigit() for char in reply)
                
                if has_number_kw or has_digits:
                    print(f"入力内容が予想される文字列 '{expected_str}' と一致しませんでした。")
                    choice = input("本当に拒否しますか？それとも再入力しますか？ [retry (再入力) / abort (中断)]: ").strip().lower()
                    if choice in ("retry", "r", "再入力"):
                        continue
                    else:
                        print("ユーザーにより処理が中断されました。")
                        return False
                else:
                    # Anything else that's not matching keywords (nonsense words) -> Immediate abort
                    print("ユーザーにより処理が中断されました（無効な入力が検出されました）。")
                    return False

    total_approved_cost = 0.0

    if args.urgent:
        from .pricing import estimate_tokens, select_urgent_models, estimate_cost_jpy
        input_tokens = estimate_tokens(diff_text)
        print(f"[お急ぎモード] 想定入力トークン数: {input_tokens}")
        models_config = select_urgent_models(input_tokens)
        provider_name = "openai" if "gpt" in models_config["review"] else "gemini"
        
        # Calculate conservative multi-stage cost (Happy path)
        cost_review = estimate_cost_jpy(models_config["review"], input_tokens, 1500)
        cost_autofix = estimate_cost_jpy(models_config["autofix"], input_tokens, 2000)
        cost_audit = estimate_cost_jpy(models_config["audit"], input_tokens, 1000)
        cost_report = estimate_cost_jpy(models_config["report"], 3000, 2000)
        
        raw_cost = cost_review + cost_autofix + cost_audit + cost_report
        safe_cost = raw_cost * 1.2
        
        import math
        if safe_cost > 10.0:
            cost = math.ceil(safe_cost / 10.0) * 10.0
        elif safe_cost >= 1.0:
            cost = float(math.ceil(safe_cost))
        else:
            cost = safe_cost
            
        total_approved_cost = cost

        print(f"[お急ぎモード] 選択プロバイダ: {provider_name}")
        print(f"[お急ぎモード] 使用モデル: {models_config}")
        print(f"[お急ぎモード] 初回見積もり（最大想定額）: JPY {cost:.2f}")
        
        if not args.yes:
            if not request_budget_approval(cost, "初回見積もりコストを承認しますか？"):
                return 1

    else:
        # Load Role-based models
        models_config = config.ai.get("models", {})
        if not models_config:
            base_model = config.ai.get("model", "gpt-4o-mini")
            models_config = {
                "review": base_model,
                "autofix": base_model,
                "fallback": base_model,
                "audit": base_model,
                "report": base_model
            }
        
    def _get_provider(role: str) -> Provider | None:
        if provider_name in {"openai", "gemini"} and not api_key:
            return None
        model = models_config.get(role)
        if not model:
            return None
        try:
            return create_provider(provider_name, model, api_key, base_url)
        except Exception as e:
            print(f"Provider initialization warning for {role}: {e}")
            return None

    provider_review = _get_provider("review")
    provider_autofix = _get_provider("autofix")
    provider_fallback = _get_provider("fallback")
    provider_audit = _get_provider("audit")
    provider_report = _get_provider("report")
    
    def approval_callback(action_name: str, p: Provider, text: str) -> bool:
        if not args.urgent or args.yes:
            return True
            
        from .pricing import estimate_tokens, estimate_cost_jpy
        import math
        
        tokens = estimate_tokens(text)
        raw_cost = estimate_cost_jpy(p.model, tokens, 2000)
        safe_cost = raw_cost * 1.2
        
        if safe_cost > 10.0:
            add_cost = math.ceil(safe_cost / 10.0) * 10.0
        elif safe_cost >= 1.0:
            add_cost = float(math.ceil(safe_cost))
        else:
            add_cost = safe_cost
            
        nonlocal total_approved_cost
        new_total = total_approved_cost + add_cost
        
        print(f"\n[追加見積もり] {action_name}")
        print(f"追加コスト: +JPY {add_cost:.2f} (合計: JPY {new_total:.2f})")
        
        if request_budget_approval(add_cost, "追加コストを承認しますか？"):
            total_approved_cost = new_total
            return True
        return False
    
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
            max_rounds=3,
            approval_callback=approval_callback
        )
        
        audit = final_audit(current_reviews, diff_text, provider=provider_audit)
        report_text = _render_full_report(current_reviews, audit, provider_report, api_key_missing=api_key_missing)
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
    
    report_text = _render_full_report([unified], audit, provider_report, api_key_missing=api_key_missing)
    print(report_text)
    
    if args.github_pr:
        from .github import post_pr_comment
        post_pr_comment(report_text)
        
    return 0 if audit.verdict in {"PASS", "WARN"} else 1





def _render_full_report(reviews, audit, provider_report: Provider | None = None, api_key_missing: bool = False) -> str:
    lines = [
        "<!-- ai-quality-platform-report -->",
        "# AI品質管理レポート",
        "",
    ]
    if api_key_missing:
        lines.extend([
            "> [!WARNING]",
            "> APIキーが設定されていないため、AIモデルによる詳細なレビューはスキップされ、簡易的なローカルチェックのみ実行されました。",
            "",
        ])
    lines.extend([
        "## 総合判定",
        "",
        f"**{audit.verdict}**",
        "",
        "## AIレビュー",
        "",
        "| 担当 | 判定 | 指摘数 |",
        "|---|---:|---:|",
    ])
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
