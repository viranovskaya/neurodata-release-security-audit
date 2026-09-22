"""Read-only evidence ZIP verification; no Git, installed scanner or extraction."""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
import zipfile
from pathlib import Path, PurePosixPath


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _members(data: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate archive member")
        if any(PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts
               or "\\" in name for name in names):
            raise ValueError("Unsafe archive member name")
        if sum(item.file_size for item in archive.infolist()) > 128 * 1024 * 1024:
            raise ValueError("Evidence archive exceeds the 128 MiB verification limit")
        return {name: archive.read(name) for name in names}


def verify(path: Path, expected_sha256: str | None = None) -> dict[str, object]:
    data = path.read_bytes()
    digest = _sha(data)
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError("Bundle SHA-256 mismatch")
    files = _members(data)
    manifest = json.loads(files["MANIFEST.json"])
    expected = manifest["artifact_sha256"]
    if set(files) != set(expected) | {"MANIFEST.json"}:
        raise ValueError("Artifact inventory mismatch")
    for name, value in expected.items():
        if _sha(files[name]) != value:
            raise ValueError(f"Artifact hash mismatch: {name}")
    source_bytes = files["source-snapshot.zip"]
    if _sha(source_bytes) != manifest["source_snapshot_sha256"]:
        raise ValueError("Source snapshot hash mismatch")
    source = _members(source_bytes)
    if set(source) != set(manifest["source_file_sha256"]):
        raise ValueError("Source inventory mismatch")
    for name, value in manifest["source_file_sha256"].items():
        if _sha(source[name]) != value:
            raise ValueError(f"Source hash mismatch: {name}")
    wheel_names = [name for name in files if name.endswith(".whl")]
    if len(wheel_names) != 1:
        raise ValueError("Expected exactly one scanner wheel")
    wheel_bytes = files[wheel_names[0]]
    if _sha(wheel_bytes) != manifest["wheel_a_b_sha256"]:
        raise ValueError("Wheel hash mismatch")
    wheel = _members(wheel_bytes)
    records = [name for name in wheel if name.endswith(".dist-info/RECORD")]
    if len(records) != 1:
        raise ValueError("Expected exactly one wheel RECORD")
    record_name = records[0]
    rows = list(csv.reader(io.StringIO(wheel[record_name].decode())))
    if len(rows) != len(wheel) or {row[0] for row in rows} != set(wheel):
        raise ValueError("Wheel RECORD inventory mismatch")
    for name, value, size in rows:
        if name == record_name:
            if value or size:
                raise ValueError("Wheel RECORD must not hash itself")
            continue
        actual = "sha256=" + base64.urlsafe_b64encode(
            hashlib.sha256(wheel[name]).digest()).rstrip(b"=").decode()
        if value != actual or int(size) != len(wheel[name]):
            raise ValueError("Wheel RECORD hash/size mismatch")
    modules = [name for name in wheel
               if name.startswith("neurodata_security_audit/") and name.endswith(".py")]
    source_modules = {name.removeprefix("src/") for name in source
                      if name.startswith("src/neurodata_security_audit/") and name.endswith(".py")}
    if set(modules) != source_modules or any(wheel[name] != source["src/" + name] for name in modules):
        raise ValueError("Wheel Python modules differ from source")
    return {"verified": True, "bundle_sha256": digest,
            "expected_bundle_hash_checked": expected_sha256 is not None,
            "source_files": len(source), "artifacts": len(expected),
            "wheel_modules": len(modules), "record_rows": len(rows),
            "scope": "Byte integrity only; not authenticity without a trusted hash, or scientific validation"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--sha256")
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.bundle, args.sha256), indent=2))
    except (ValueError, KeyError, OSError, zipfile.BadZipFile) as error:
        raise SystemExit(str(error)) from error
