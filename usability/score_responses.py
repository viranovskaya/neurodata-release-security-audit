"""Score complete pseudonymous response files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from neurodata_security_audit.usability import (
    render_usability_markdown,
    score_usability,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("responses", nargs="+", type=Path)
    parser.add_argument(
        "--specification",
        type=Path,
        default=Path(__file__).with_name("spec.json"),
    )
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--markdown", type=Path, required=True)
    args = parser.parse_args()

    result = score_usability(args.specification, args.responses)
    args.json.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.markdown.write_text(
        render_usability_markdown(result),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
