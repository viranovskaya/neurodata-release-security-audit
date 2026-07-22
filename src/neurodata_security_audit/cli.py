"""Command-line interface."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .reporting import render_json, render_markdown
from .scanner import scan_dataset


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="neurodata-security-audit")
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    scan = subparsers.add_parser("scan", help="scan one local dataset directory")
    scan.add_argument("dataset", type=Path)
    scan.add_argument("--json", type=Path, dest="json_path")
    scan.add_argument("--markdown", type=Path, dest="markdown_path")
    return parser


def _write_report(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = scan_dataset(args.dataset)
    except (FileNotFoundError, NotADirectoryError, PermissionError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    data = report.to_dict()
    summary = data["summary"]
    print(
        "inspected={files_inspected} skipped={files_skipped} "
        "high={findings_high} review={findings_review} info={findings_info}".format(
            **summary
        )
    )
    if args.json_path:
        _write_report(args.json_path, render_json(report))
    if args.markdown_path:
        _write_report(args.markdown_path, render_markdown(report))
    return 1 if summary["findings_high"] else 0
