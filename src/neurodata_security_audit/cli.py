"""Run the audit from the command line."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .curator import (
    compare_reports,
    load_report,
    render_checklist_tsv,
    render_comparison_json,
    render_comparison_markdown,
    write_text_new,
    write_texts_new,
)
from .html_report import render_html
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
        "--html",
        type=Path,
        dest="html_path",
        help="write a self-contained visual report",
    )
    scan.add_argument(
        "--sensitive-terms",
        type=Path,
        help="private text file with one known name or identifier per line",
    )
    checklist = subparsers.add_parser(
        "checklist",
        help="create a curator checklist from one JSON audit report",
    )
    checklist.add_argument("report", type=Path)
    checklist.add_argument("--tsv", type=Path, required=True, dest="tsv_path")
    compare = subparsers.add_parser(
        "compare",
        help="compare review items in two JSON audit reports",
    )
    compare.add_argument("baseline", type=Path)
    compare.add_argument("current", type=Path)
    compare.add_argument(
        "--confirm-same-dataset",
        action="store_true",
        required=True,
        help="confirm that both reports describe versions of the same dataset",
    )
    compare.add_argument("--json", type=Path, required=True, dest="json_path")
    compare.add_argument(
        "--markdown",
        type=Path,
        required=True,
        dest="markdown_path",
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


def _scan(args: argparse.Namespace) -> int:
    try:
        output_paths = (args.json_path, args.markdown_path, args.html_path)
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
    integrity_ok = (
        summary["manifest_recheck_passed"]
        and summary["release_tree_recheck_passed"]
    )
    print(
        "entries={entries_total} manifest={manifest_files} "
        "references={references_valid}/{references_checked} "
        "inspected={files_inspected} skipped={files_skipped} "
        "high={findings_high} review={findings_review} info={findings_info} "
        "integrity={integrity}".format(
            integrity="ok" if integrity_ok else "failed",
            **summary,
        )
    )
    try:
        if args.json_path:
            _write_report(args.json_path, render_json(report))
        if args.markdown_path:
            _write_report(args.markdown_path, render_markdown(report))
        if args.html_path:
            _write_report(args.html_path, render_html(report))
    except OSError as error:
        print(f"error: could not write report ({type(error).__name__})", file=sys.stderr)
        return 2
    if not integrity_ok:
        return 2
    return 1 if summary["findings_high"] else 0


def _checklist(args: argparse.Namespace) -> int:
    try:
        report = load_report(args.report)
        checklist = render_checklist_tsv(report)
        write_text_new(args.tsv_path, checklist)
    except (
        OSError,
        RuntimeError,
        UnicodeError,
        ValueError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    item_count = max(0, checklist.count("\n") - 1)
    print(f"checklist_items={item_count}")
    return 0


def _compare(args: argparse.Namespace) -> int:
    try:
        if args.json_path.resolve(strict=False) == args.markdown_path.resolve(
            strict=False
        ):
            raise ValueError("JSON and Markdown outputs must be different files")
        baseline = load_report(args.baseline)
        current = load_report(args.current)
        comparison = compare_reports(
            baseline,
            current,
            same_dataset_confirmed=args.confirm_same_dataset,
        )
        write_texts_new(
            {
                args.json_path: render_comparison_json(comparison),
                args.markdown_path: render_comparison_markdown(comparison),
            }
        )
    except (
        OSError,
        RuntimeError,
        UnicodeError,
        ValueError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    summary = comparison["summary"]
    print(
        f"new={summary['new']} remaining={summary['remaining']} "
        f"resolved={summary['resolved']}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "scan":
        return _scan(args)
    if args.command == "checklist":
        return _checklist(args)
    if args.command == "compare":
        return _compare(args)
    raise AssertionError(f"Unhandled command: {args.command}")
