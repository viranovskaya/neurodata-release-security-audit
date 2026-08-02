"""Check that the public wheel contains the scanner, not study administration."""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path


def check_wheel(path: Path) -> None:
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        if "neurodata_security_audit/cli.py" not in names:
            raise SystemExit("Wheel is missing the scanner CLI module")

        forbidden = sorted(
            name
            for name in names
            if name.startswith("usability/")
            or name == "neurodata_security_audit/usability.py"
            or "__pycache__" in name
            or name.endswith((".pyc", ".pyo"))
        )
        if forbidden:
            raise SystemExit(
                "Wheel contains source-only study administration or cache files: "
                + ", ".join(forbidden)
            )

        entry_points = next(
            name for name in names if name.endswith(".dist-info/entry_points.txt")
        )
        text = archive.read(entry_points).decode()
        if "neurodata-security-audit" not in text:
            raise SystemExit("Wheel is missing the scanner entry point")
        if "neurodata-usability-" in text:
            raise SystemExit("Wheel exposes source-only usability entry points")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("wheel", type=Path)
    args = parser.parse_args()
    check_wheel(args.wheel)


if __name__ == "__main__":
    main()
