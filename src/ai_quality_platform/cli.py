from __future__ import annotations

import argparse
from pathlib import Path

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
    args = parser.parse_args(argv)

    config = load_ai_quality_config(Path(args.config))
    _ = config
    diff_text = read_diff(Path(args.diff)) if args.diff else ""
    code_review = review_diff(diff_text)
    requirements_review = review_requirements(diff_text)
    tests_review = review_tests(diff_text)
    docs_review = review_documentation(diff_text)
    audit = final_audit([code_review, requirements_review, tests_review, docs_review], diff_text)
    for result in [code_review, requirements_review, tests_review, docs_review, audit]:
        payload = to_json_ready(result)
        validate_review_result(payload)
        validate_against_schema(payload, Path("schemas/review-result.schema.json"))
    if args.autofix_root:
        outcome, _ = run_autofix(Path(args.autofix_root), [code_review, requirements_review, tests_review, docs_review], max_rounds=3)
        print(_render_autofix_block(outcome))
    print(_render_full_report([code_review, requirements_review, tests_review, docs_review], audit))
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
