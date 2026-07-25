"""Build a participant-facing bundle without the private answer key."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from neurodata_security_audit.usability import render_reviewer_packet

from usability._io import packaged_specification, write_text_new
from usability.build_reports import build_reports


def _answer_key_material(specification: dict[str, object]) -> tuple[str, str]:
    tasks = specification["tasks"]
    assert isinstance(tasks, list)
    answer_key = {
        str(task["task_id"]): str(task["expected"])
        for task in tasks
        if isinstance(task, dict)
    }
    serialized = json.dumps(
        answer_key,
        sort_keys=True,
        separators=(",", ":"),
    )
    return serialized, hashlib.sha256(serialized.encode()).hexdigest()


def _check_bundle(destination: Path, specification: dict[str, object]) -> None:
    files = sorted(path for path in destination.rglob("*") if path.is_file())
    relative_names = [path.relative_to(destination).as_posix() for path in files]
    forbidden_names = [
        name
        for name in relative_names
        if "spec" in name.lower() or "answer" in name.lower()
    ]
    if forbidden_names:
        raise RuntimeError(
            "Participant bundle contains an administrator-only filename: "
            + ", ".join(forbidden_names)
        )

    joined = "\n".join(
        f"{name}\n{path.read_text(encoding='utf-8')}"
        for name, path in zip(relative_names, files, strict=True)
    )
    serialized, fingerprint = _answer_key_material(specification)
    forbidden_content = {
        '"expected"',
        "spec.json",
        serialized,
        fingerprint,
    }
    leaked = sorted(value for value in forbidden_content if value in joined)
    if leaked:
        raise RuntimeError("Participant bundle contains answer-key material")


def build_participant_bundle(destination: Path) -> list[Path]:
    """Create a reviewer directory and return resolved absolute file paths.

    Resolving once at the boundary keeps macOS ``/var`` and ``/private/var``
    aliases from producing mixed path identities.
    """
    destination = destination.resolve()
    package_root = Path(__file__).resolve().parent
    if destination == package_root or package_root in destination.parents:
        raise ValueError("Participant output must be outside the installed package")

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.mkdir()
    try:
        with packaged_specification() as specification_path:
            specification = json.loads(
                specification_path.read_text(encoding="utf-8")
            )
            if not isinstance(specification, dict):
                raise ValueError("Usability specification must be a JSON object")
            build_reports(destination / "reports")
            write_text_new(
                destination / "reviewer_packet.md",
                render_reviewer_packet(specification_path),
            )
        _check_bundle(destination, specification)
    except BaseException:
        shutil.rmtree(destination, ignore_errors=True)
        raise
    return sorted(path for path in destination.rglob("*") if path.is_file())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    for path in build_participant_bundle(args.output_dir):
        print(path)


if __name__ == "__main__":
    main()
