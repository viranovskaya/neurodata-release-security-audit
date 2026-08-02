"""Score complete pseudonymous response files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from usability.core import (
    render_usability_markdown,
    score_usability,
)

from usability._io import (
    packaged_specification,
    release_owned_file,
    unlink_if_owned,
    write_text_new,
    write_text_new_owned,
)

PACKAGE_ROOT = Path(__file__).resolve().parent


def _reject_package_output(path: Path) -> None:
    resolved = path.resolve()
    if resolved == PACKAGE_ROOT or PACKAGE_ROOT in resolved.parents:
        raise ValueError("Scorer outputs must be outside the usability source package")


def write_score_outputs(
    response_paths: list[Path],
    json_output: Path,
    markdown_output: Path,
    specification: Path | None = None,
) -> None:
    """Score responses and create two outputs without replacing either file."""
    _reject_package_output(json_output)
    _reject_package_output(markdown_output)
    if json_output.resolve() == markdown_output.resolve():
        raise ValueError("JSON and Markdown outputs must be different files")
    if json_output.exists() or markdown_output.exists():
        raise FileExistsError("Scorer outputs already exist")

    if specification is None:
        with packaged_specification() as packaged:
            result = score_usability(packaged, response_paths)
    else:
        result = score_usability(specification, response_paths)
    json_identity = write_text_new_owned(
        json_output,
        json.dumps(result, indent=2, sort_keys=True) + "\n",
    )
    try:
        write_text_new(
            markdown_output,
            render_usability_markdown(result),
        )
    except BaseException:
        unlink_if_owned(json_output, json_identity)
        raise
    else:
        release_owned_file(json_identity)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("responses", nargs="+", type=Path)
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--markdown", type=Path, required=True)
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    write_score_outputs(
        args.responses,
        args.json,
        args.markdown,
    )


if __name__ == "__main__":
    main()
