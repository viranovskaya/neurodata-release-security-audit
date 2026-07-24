"""Build the participant packet without the answer key."""

from __future__ import annotations

import argparse
from pathlib import Path

from neurodata_security_audit.usability import render_reviewer_packet

from usability._io import packaged_specification, write_text_new


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with packaged_specification() as specification:
        write_text_new(args.output, render_reviewer_packet(specification))
    output = args.output
    print(output)


if __name__ == "__main__":
    main()
