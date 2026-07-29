"""Check that a wheel separates administrator and participant materials."""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path


def check_wheel(path: Path) -> None:
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        required = {
            "usability/__init__.py",
            "usability/_io.py",
            "usability/build_participant_bundle.py",
            "usability/build_response.py",
            "usability/build_reports.py",
            "usability/build_reviewer_packet.py",
            "usability/score_responses.py",
            "usability/README.md",
            "usability/prolific_pilot1_results.md",
            "usability/spec.json",
        }
        missing = sorted(required - names)
        if missing:
            raise SystemExit("Wheel is missing administrator files: " + ", ".join(missing))

        forbidden = sorted(
            name
            for name in names
            if name.startswith(("usability/reports/", "usability/results/"))
            or name
            in {
                "usability/response_template.json",
                "usability/reviewer_packet.md",
            }
            or "__pycache__" in name
            or name.endswith((".pyc", ".pyo"))
        )
        if forbidden:
            raise SystemExit(
                "Wheel contains participant outputs or local artifacts: "
                + ", ".join(forbidden)
            )

        entry_points = next(
            name for name in names if name.endswith(".dist-info/entry_points.txt")
        )
        text = archive.read(entry_points).decode()
        for command in (
            "neurodata-usability-build-bundle",
            "neurodata-usability-build-response",
            "neurodata-usability-score",
        ):
            if command not in text:
                raise SystemExit(f"Wheel is missing the {command} entry point")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("wheel", type=Path)
    args = parser.parse_args()
    check_wheel(args.wheel)


if __name__ == "__main__":
    main()
