"""Run hash-pinned public format checks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from benchmark.external import (
    render_external_format_markdown,
    run_external_format_checks,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures-root", type=Path, required=True)
    parser.add_argument(
        "--manifest",
        type=Path,
        required=True,
    )
    parser.add_argument("--json", type=Path)
    parser.add_argument("--markdown", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    result = run_external_format_checks(args.manifest, args.fixtures_root)
    json_text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    markdown_text = render_external_format_markdown(result)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json_text, encoding="utf-8")
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(markdown_text, encoding="utf-8")
    print(markdown_text, end="")
    return int(result["summary"]["failed"] != 0)


if __name__ == "__main__":
    raise SystemExit(main())
