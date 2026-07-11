from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Callable

from .models import ReviewResult
from .providers.base import Provider


@dataclass(slots=True)
class AutofixOutcome:
    status: str
    rounds: int
    changed_files: list[str] = field(default_factory=list)
    total_changed_lines: int = 0
    reason: str = ""
    repeated_finding_ids: list[str] = field(default_factory=list)


def run_autofix(
    root: Path,
    reviews: list[ReviewResult],
    *,
    max_rounds: int = 3,
    max_changed_lines_per_round: int = 300,
    max_total_changed_lines: int = 800,
    review_fn: Callable[[Path], list[ReviewResult]] | None = None,
    provider: Provider | None = None,
) -> tuple[AutofixOutcome, list[ReviewResult]]:
    current_reviews = reviews
    changed_files: list[str] = []
    total_changed_lines = 0
    seen_fingerprints: set[str] = set()
    repeated_ids: list[str] = []

    for round_no in range(1, max_rounds + 1):
        fixable = _find_fixable_findings(current_reviews)
        if not fixable:
            return AutofixOutcome("PASS", round_no - 1, changed_files, total_changed_lines, "修正対象がありませんでした。", repeated_ids), current_reviews

        if _requires_human_review(fixable):
            return AutofixOutcome("HUMAN_REVIEW_REQUIRED", round_no - 1, changed_files, total_changed_lines, "高リスク変更のため人間確認が必要です。", repeated_ids), current_reviews

        fingerprint = _fingerprint(fixable)
        if fingerprint in seen_fingerprints:
            repeated_ids.extend(sorted({finding.id for finding in fixable}))
            return AutofixOutcome("BLOCK", round_no - 1, changed_files, total_changed_lines, "同一 finding が再発しました。", repeated_ids), current_reviews
        seen_fingerprints.add(fingerprint)

        round_changed = _apply_fixes(root, fixable, provider)
        if round_changed == 0:
            return AutofixOutcome("BLOCK", round_no - 1, changed_files, total_changed_lines, "修正を適用できませんでした。", repeated_ids), current_reviews

        if round_changed > max_changed_lines_per_round:
            return AutofixOutcome("HUMAN_REVIEW_REQUIRED", round_no - 1, changed_files, total_changed_lines, "1回の変更量が上限を超えました。", repeated_ids), current_reviews

        total_changed_lines += round_changed
        if total_changed_lines > max_total_changed_lines:
            return AutofixOutcome("HUMAN_REVIEW_REQUIRED", round_no, changed_files, total_changed_lines, "総変更量が上限を超えました。", repeated_ids), current_reviews

        changed_files.extend(_changed_file_paths(root, fixable))
        current_reviews = review_fn(root) if review_fn else []

        if current_reviews:
            next_fixable = _find_fixable_findings(current_reviews)
            next_fingerprint = _fingerprint(next_fixable)
            if next_fixable and next_fingerprint in seen_fingerprints:
                repeated_ids.extend(sorted({finding.id for finding in next_fixable}))
                return AutofixOutcome("BLOCK", round_no, changed_files, total_changed_lines, "同一 finding が再発しました。", repeated_ids), current_reviews
            if not next_fixable:
                return AutofixOutcome("PASS", round_no, changed_files, total_changed_lines, "修正後の再レビューで問題が解消しました。", repeated_ids), current_reviews

    return AutofixOutcome("HUMAN_REVIEW_REQUIRED", max_rounds, changed_files, total_changed_lines, "最大修正回数に到達しました。", repeated_ids), current_reviews


def _find_fixable_findings(reviews: list[ReviewResult]):
    fixable = []
    for review in reviews:
        for finding in review.findings:
            if finding.blocking or finding.severity in {"high", "critical"}:
                fixable.append(finding)
    return fixable


def _requires_human_review(findings) -> bool:
    categories = {finding.category for finding in findings}
    return bool(categories & {"workflow-change", "dependency-change", "backward-compatibility", "missing-input"})


def _fingerprint(findings) -> str:
    text = "|".join(sorted(f"{finding.id}:{finding.category}:{finding.title}" for finding in findings))
    return sha256(text.encode("utf-8")).hexdigest()


def _apply_fixes(root: Path, findings, provider: Provider | None = None) -> int:
    changed_lines = 0
    for finding in findings:
        changed_lines += _apply_single_fix(root, finding, provider)
    return changed_lines


def _apply_single_fix(root: Path, finding, provider: Provider | None = None) -> int:
    if provider is None or not finding.file:
        return 0

    path = root / finding.file
    if not path.exists():
        return 0
        
    text = path.read_text(encoding="utf-8")
    
    prompt_path = Path("prompts/autofix.md")
    system_prompt = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else "You are an autofix bot."
    
    user_prompt = f"以下のファイルの内容と、指摘内容をもとにコードを修正してください。\n\n【対象ファイル】\n```\n{text}\n```\n\n【指摘内容】\n- ID: {finding.id}\n- タイトル: {finding.title}\n- 詳細: {finding.description}\n- 推奨対応: {finding.recommendation}"
    
    response = provider.generate_review(system_prompt, user_prompt)
    
    import json
    try:
        content = response.content
        # Markdownコードブロックで囲まれている場合を考慮
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
            
        data = json.loads(content.strip())
        if data.get("status") == "fixed":
            search = data.get("search", "")
            replace = data.get("replace", "")
            if search and search in text:
                new_text = text.replace(search, replace, 1)
                path.write_text(new_text, encoding="utf-8")
                return max(1, new_text.count("\n") - text.count("\n"))
    except Exception as e:
        print(f"Autofix format error: {e}")
        
    return 0


def _replace_in_file(root: Path, relative_path: str, needle: str, replacement: str) -> int:
    path = root / relative_path
    if not path.exists():
        return 0
    text = path.read_text(encoding="utf-8")
    if needle not in text:
        return 0
    new_text = text.replace(needle, replacement)
    if new_text == text:
        return 0
    path.write_text(new_text, encoding="utf-8")
    return max(1, new_text.count("\n") - text.count("\n"))


def _changed_file_paths(root: Path, findings) -> list[str]:
    paths = []
    for finding in findings:
        if finding.file:
            paths.append(str((root / finding.file).resolve()))
    return sorted(set(paths))
