"""Run the audit from the command line."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .reporting import render_json, render_markdown
from .scanner import ScanPolicy, scan_dataset

_MAX_TERM_FILE_BYTES = 1024 * 1024


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="neurodata-security-audit")
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    scan = subparsers.add_parser("scan", help="scan one local dataset directory")
    scan.add_argument("dataset", type=Path)
    scan.add_argument("--json", type=Path, dest="json_path")
    scan.add_argument("--markdown", type=Path, dest="markdown_path")
    scan.add_argument(
        "--sensitive-terms",
        type=Path,
        help="private text file with one known name or identifier per line",
    )
    return parser


def _write_report(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _read_sensitive_terms(path: Path) -> tuple[str, ...]:
    if path.stat().st_size > _MAX_TERM_FILE_BYTES:
        raise ValueError("Sensitive term file is larger than 1 MiB")
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    return tuple(
        line.strip()
        for line in lines
        if line.strip() and not line.lstrip().startswith("#")
    )


def _is_inside_dataset(path: Path, dataset: Path) -> bool:
    dataset_root = dataset.expanduser().resolve(strict=True)
    candidate = path.expanduser().resolve(strict=False)
    return candidate == dataset_root or dataset_root in candidate.parents


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        output_paths = (args.json_path, args.markdown_path)
        if any(
            path is not None and _is_inside_dataset(path, args.dataset)
            for path in output_paths
        ):
            raise ValueError("Report paths must be outside the dataset directory")
        if args.sensitive_terms and _is_inside_dataset(
            args.sensitive_terms,
            args.dataset,
        ):
            raise ValueError("The sensitive term file must be outside the dataset directory")
        terms = _read_sensitive_terms(args.sensitive_terms) if args.sensitive_terms else ()
        policy = ScanPolicy(sensitive_terms=terms)
        report = scan_dataset(args.dataset, policy)
    except (
        OSError,
        RuntimeError,
        UnicodeError,
        ValueError,
    ) as error:
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
    try:
        if args.json_path:
            _write_report(args.json_path, render_json(report))
        if args.markdown_path:
            _write_report(args.markdown_path, render_markdown(report))
    except OSError as error:
        print(f"error: could not write report ({type(error).__name__})", file=sys.stderr)
        return 2
    return 1 if summary["findings_high"] else 0
