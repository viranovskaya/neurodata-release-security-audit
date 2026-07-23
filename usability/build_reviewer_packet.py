"""Build the participant packet without the answer key."""

from __future__ import annotations

from pathlib import Path

from neurodata_security_audit.usability import render_reviewer_packet

ROOT = Path(__file__).resolve().parent


def main() -> None:
    output = ROOT / "reviewer_packet.md"
    output.write_text(
        render_reviewer_packet(ROOT / "spec.json"),
        encoding="utf-8",
    )
    print(output)


if __name__ == "__main__":
    main()
