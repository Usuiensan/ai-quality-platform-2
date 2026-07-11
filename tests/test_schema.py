import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ai_quality_platform.schema import validate_review_result
from ai_quality_platform.schema import parse_review_result


class SchemaTests(unittest.TestCase):
    def test_rejects_missing_keys(self) -> None:
        with self.assertRaises(ValueError):
            validate_review_result({"reviewer": "code"})

    def test_accepts_valid_payload(self) -> None:
        validate_review_result(
            {
                "reviewer": "code",
                "verdict": "PASS",
                "summary": "ok",
                "findings": [],
                "tested": [],
                "not_tested": [],
            }
        )

    def test_rejects_malformed_json(self) -> None:
        with self.assertRaises(ValueError):
            parse_review_result('{"reviewer": "code", "verdict": "PASS"')

    def test_rejects_empty_json(self) -> None:
        with self.assertRaises(ValueError):
            parse_review_result(" ")


if __name__ == "__main__":
    unittest.main()
