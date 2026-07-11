import tempfile
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ai_quality_platform.autofix import run_autofix
from ai_quality_platform.models import Finding, ReviewResult


class AutofixTests(unittest.TestCase):
    def test_rewrites_fixable_command_injection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "scripts"
            path.mkdir()
            target = path / "run.ps1"
            target.write_text('Invoke-WebRequest $url', encoding="utf-8")
            review = ReviewResult(
                reviewer="code",
                verdict="BLOCK",
                summary="",
                findings=[
                    Finding(
                        id="SEC-001",
                        severity="high",
                        category="shell-injection",
                        file="scripts/run.ps1",
                        line_start=1,
                        line_end=1,
                        title="",
                        description="",
                        recommendation="",
                        blocking=True,
                        confidence=0.9,
                    )
                ],
            )
            outcome, _ = run_autofix(root, [review])
            self.assertEqual(outcome.status, "PASS")
            self.assertIn("TODO", target.read_text(encoding="utf-8"))

    def test_stops_on_repeated_finding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            review = ReviewResult(
                reviewer="code",
                verdict="BLOCK",
                summary="",
                findings=[
                    Finding(
                        id="SEC-001",
                        severity="high",
                        category="shell-injection",
                        file="scripts/run.ps1",
                        line_start=1,
                        line_end=1,
                        title="",
                        description="",
                        recommendation="",
                        blocking=True,
                        confidence=0.9,
                    )
                ],
            )
            outcome, _ = run_autofix(root, [review], max_rounds=3, review_fn=lambda _: [review])
            self.assertEqual(outcome.status, "BLOCK")

    def test_human_review_required_for_workflow_change(self) -> None:
        review = ReviewResult(
            reviewer="code",
            verdict="BLOCK",
            summary="",
            findings=[
                Finding(
                    id="CODE-002",
                    severity="high",
                    category="workflow-change",
                    file=".github/workflows/ci.yml",
                    line_start=1,
                    line_end=1,
                    title="",
                    description="",
                    recommendation="",
                    blocking=True,
                    confidence=0.9,
                )
            ],
        )
        outcome, _ = run_autofix(Path("."), [review])
        self.assertEqual(outcome.status, "HUMAN_REVIEW_REQUIRED")


if __name__ == "__main__":
    unittest.main()
