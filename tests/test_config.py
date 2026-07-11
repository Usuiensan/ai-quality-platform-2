from pathlib import Path
import tempfile
import unittest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ai_quality_platform.config import load_ai_quality_config


class ConfigTests(unittest.TestCase):
    def test_loads_minimal_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".ai-quality.yml"
            path.write_text("version: 1\npreset: generic\nreviewers:\n  code: true\n", encoding="utf-8")
            config = load_ai_quality_config(path)
            self.assertEqual(config.version, 1)
            self.assertEqual(config.preset, "generic")
            self.assertTrue(config.reviewers["code"])


if __name__ == "__main__":
    unittest.main()
