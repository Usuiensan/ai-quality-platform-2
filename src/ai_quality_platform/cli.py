from __future__ import annotations

import argparse
from pathlib import Path

from .config import load_ai_quality_config
from .diff import read_diff
from .review import render_report, review_diff


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ai-quality-platform")
    parser.add_argument("--config", default=".ai-quality.yml")
    parser.add_argument("--diff", default=None)
    args = parser.parse_args(argv)

    config = load_ai_quality_config(Path(args.config))
    _ = config
    diff_text = read_diff(Path(args.diff)) if args.diff else ""
    result = review_diff(diff_text)
    print(render_report(result))
    return 0 if result.verdict in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())

