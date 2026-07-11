import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ai_quality_platform.review import review_diff, render_report


class ReviewTests(unittest.TestCase):
    def test_blocks_shell_injection_like_change(self) -> None:
        result = review_diff("Invoke-WebRequest https://example.test")
        self.assertEqual(result.verdict, "BLOCK")
        self.assertGreaterEqual(len(result.findings), 1)

    def test_report_contains_fixed_marker(self) -> None:
        report = render_report(review_diff(""))
        self.assertIn("<!-- ai-quality-platform-report -->", report)
        self.assertIn("AI品質管理レポート", report)

    def test_path_traversal_fixture_blocks(self) -> None:
        diff = Path("fixtures/path-traversal/diff.txt").read_text(encoding="utf-8")
        result = review_diff(diff)
        self.assertEqual(result.verdict, "BLOCK")

    def test_dependency_change_fixture_warns(self) -> None:
        diff = Path("fixtures/dependency-change/diff.txt").read_text(encoding="utf-8")
        result = review_diff(diff)
        self.assertIn(result.verdict, {"WARN", "BLOCK"})


if __name__ == "__main__":
    unittest.main()
