"""Run the labelled leak-detection benchmark."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from neurodata_security_audit.benchmark import (
    render_benchmark_markdown,
    run_benchmark,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path(__file__).with_name("cases.json"),
    )
    parser.add_argument("--json", type=Path)
    parser.add_argument("--markdown", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    result = run_benchmark(args.cases)
    json_text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    markdown_text = render_benchmark_markdown(result)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json_text, encoding="utf-8")
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(markdown_text, encoding="utf-8")
    print(markdown_text, end="")
    summary = result["summary"]
    return int(
        summary["matched_findings"] != summary["expected_findings"]
        or summary["unexpected_findings"] != 0
        or summary["matched_references"] != summary["expected_references"]
        or summary["unexpected_references"] != 0
        or summary["matched_container_members"]
        != summary["expected_container_members"]
        or summary["unexpected_container_members"] != 0
        or summary["matched_coverage"] != summary["expected_coverage"]
        or summary["masking_failures"] != 0
        or summary["integrity_failures"] != 0
    )


if __name__ == "__main__":
    raise SystemExit(main())
