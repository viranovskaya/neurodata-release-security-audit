"""Create one administrator response file for a completed reviewer packet."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from usability.core import build_response_template

from usability._io import packaged_specification, write_text_new

PACKAGE_ROOT = Path(__file__).resolve().parent


def build_response_file(participant_id: str, output: Path) -> Path:
    """Create a blank pseudonymous response outside the usability source package."""
    resolved = output.resolve()
    if resolved == PACKAGE_ROOT or PACKAGE_ROOT in resolved.parents:
        raise ValueError("Response output must be outside the usability source package")
    with packaged_specification() as specification:
        response = build_response_template(specification, participant_id)
    write_text_new(
        resolved,
        json.dumps(response, indent=2) + "\n",
    )
    return resolved


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--participant-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(build_response_file(args.participant_id, args.output))


if __name__ == "__main__":
    main()
