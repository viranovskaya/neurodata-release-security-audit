from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import re
import zipfile


SITE = Path(__file__).resolve().parents[1]
REPO = SITE.parent
RELEASE_MODULE = SITE / "src" / "release.js"
DOWNLOADS = SITE / "public" / "downloads"
TEMPLATES = SITE / "kit"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def release_values() -> dict[str, str]:
    text = RELEASE_MODULE.read_text(encoding="utf-8")
    return dict(re.findall(r'^\s*([A-Za-z][A-Za-z0-9]*):\s*"([^"]*)",?$', text, flags=re.MULTILINE))


def render_template(path: Path, values: dict[str, str]) -> bytes:
    replacements = {
        "{{VERSION}}": values["version"],
        "{{ARCHIVE}}": values["archive"],
        "{{WHEEL}}": values["wheel"],
    }
    text = path.read_text(encoding="utf-8")
    for marker, value in replacements.items():
        text = text.replace(marker, value)
    if re.search(r"{{[A-Z_]+}}", text):
        raise RuntimeError(f"Unresolved template marker in {path.name}")
    return text.encode("utf-8")


def verify_wheel(path: Path, values: dict[str, str]) -> bytes:
    data = path.read_bytes()
    if path.name != values["wheel"]:
        raise RuntimeError(f"Expected wheel filename {values['wheel']}")
    if sha256_bytes(data) != values["wheelSha256"]:
        raise RuntimeError("Wheel SHA-256 does not match the published release asset")
    with zipfile.ZipFile(path) as wheel:
        metadata_names = [name for name in wheel.namelist() if name.endswith(".dist-info/METADATA")]
        if len(metadata_names) != 1:
            raise RuntimeError("Wheel must contain exactly one METADATA file")
        metadata = wheel.read(metadata_names[0]).decode("utf-8")
        if f"Version: {values['version']}\n" not in metadata:
            raise RuntimeError("Wheel metadata version does not match the beta version")
    return data


def kit_files(wheel_path: Path, values: dict[str, str]) -> dict[str, bytes]:
    files = {
        "README_EN.md": render_template(TEMPLATES / "README_EN.md", values),
        "FEEDBACK_EN.md": render_template(TEMPLATES / "FEEDBACK_EN.md", values),
        "LICENSE": (REPO / "LICENSE").read_bytes(),
        values["wheel"]: verify_wheel(wheel_path, values),
    }
    demo = REPO / "examples" / "reviewer_demo"
    for path in sorted(item for item in demo.rglob("*") if item.is_file()):
        files[path.relative_to(REPO).as_posix()] = path.read_bytes()
    checksums = "".join(
        f"{sha256_bytes(files[name])}  {name}\n" for name in sorted(files)
    )
    files["SHA256SUMS.txt"] = checksums.encode("utf-8")
    return files


def write_archive(path: Path, files: dict[str, bytes]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, files[name])
    return sha256_bytes(path.read_bytes())


def update_archive_hash(digest: str) -> None:
    text = RELEASE_MODULE.read_text(encoding="utf-8")
    updated, changes = re.subn(
        r'archiveSha256: "[^"]+"',
        f'archiveSha256: "{digest}"',
        text,
    )
    if changes != 1:
        raise RuntimeError("Could not update archive SHA-256 in release.js")
    RELEASE_MODULE.write_text(updated, encoding="utf-8")


def main() -> None:
    values = release_values()
    parser = argparse.ArgumentParser(description="Build the deterministic researcher beta archive")
    parser.add_argument(
        "--wheel",
        type=Path,
        default=SITE / ".artifacts" / values["wheel"],
        help="path to the exact published release wheel",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail instead of updating release.js when the archive hash differs",
    )
    args = parser.parse_args()

    archive = DOWNLOADS / values["archive"]
    first = write_archive(archive, kit_files(args.wheel, values))
    second = write_archive(archive, kit_files(args.wheel, values))
    if first != second:
        raise RuntimeError("Beta archive build is not deterministic")
    if args.check:
        if values["archiveSha256"] != second:
            raise RuntimeError("Archive SHA-256 does not match release.js")
    else:
        update_archive_hash(second)
    print(f"{second}  {archive.name}")


if __name__ == "__main__":
    main()
