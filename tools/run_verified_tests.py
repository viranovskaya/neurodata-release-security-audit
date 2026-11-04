"""Run unittest and bind its result to runtime imports in the same process."""

from __future__ import annotations

import argparse
import base64
import contextlib
import csv
import hashlib
import importlib
import io
import json
import platform
import sys
import unittest
import zipfile
from pathlib import Path, PurePosixPath


def _verify_installed_wheel(wheel: Path, expected_sha256: str, package_root: Path) -> dict[str, object]:
    data = wheel.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected_sha256:
        raise ValueError("Wheel SHA-256 differs from the explicitly expected artifact")
    # Resolve metadata beside the imported package, never through sys.path:
    # source-tree egg-info may otherwise shadow the installed distribution.
    installation_root = package_root.resolve().parent
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()
        records = [name for name in names if name.endswith(".dist-info/RECORD")]
        if len(set(names)) != len(names) or len(records) != 1:
            raise ValueError("Wheel has duplicate members or an ambiguous RECORD")
        record_name = records[0]
        metadata_root = record_name.split("/")[0]
        for name in names:
            path = PurePosixPath(name)
            if (path.is_absolute() or ".." in path.parts or "\\" in name
                    or not path.parts or path.parts[0] not in ("neurodata_security_audit", metadata_root)):
                raise ValueError("Unsafe or unsupported wheel member")
        rows = list(csv.reader(io.StringIO(archive.read(record_name).decode("utf-8"))))
        if (any(len(row) != 3 for row in rows) or len(rows) != len(names)
                or {row[0] for row in rows} != set(names)):
            raise ValueError("Wheel RECORD does not describe every member exactly once")
        installed_record = (installation_root / record_name).read_bytes()
        installed_rows = list(csv.reader(io.StringIO(installed_record.decode("utf-8"))))
        if any(len(row) != 3 for row in installed_rows):
            raise ValueError("Malformed installed RECORD")
        installed = {row[0]: row[1:] for row in installed_rows}
        if len(installed) != len(installed_rows):
            raise ValueError("Duplicate installed RECORD rows")
        for name, recorded_hash, size in rows:
            payload = archive.read(name)
            if name == record_name:
                if recorded_hash or size:
                    raise ValueError("Wheel RECORD must not hash itself")
                continue
            encoded = base64.urlsafe_b64encode(hashlib.sha256(payload).digest()).rstrip(b"=").decode("ascii")
            if recorded_hash != "sha256=" + encoded or size != str(len(payload)):
                raise ValueError("Wheel RECORD hash or size mismatch")
            if (installed.get(name) != [recorded_hash, size]
                    or (installation_root / name).read_bytes() != payload):
                raise ValueError("Wheel member differs from its installed bytes or RECORD")
    return {"filename": wheel.name, "sha256": digest, "record_rows": len(rows),
            "installed_record_sha256": hashlib.sha256(installed_record).hexdigest()}


def run(root: Path, output: Path, origin: str, wheel: Path | None = None,
        wheel_sha256: str | None = None) -> dict[str, object]:
    if origin == "wheel" and (wheel is None or wheel_sha256 is None):
        raise ValueError("Wheel mode requires an artifact path and explicit expected SHA-256")
    root = root.resolve()
    source = root / "src"
    # Remove inherited source paths before selecting the intended runtime.
    sys.path[:] = [item for item in sys.path if Path(item or ".").resolve() != source]
    sys.path.insert(0, str(root))
    if origin == "source":
        sys.path.insert(0, str(source))
    package = importlib.import_module("neurodata_security_audit")
    package_root = Path(package.__file__).resolve().parent
    expected_source = source / "neurodata_security_audit"
    if origin == "source" and package_root != expected_source:
        raise ValueError("Source test imported the wrong package origin")
    if origin == "wheel" and (
        package_root == expected_source or "site-packages" not in package_root.parts
    ):
        raise ValueError("Wheel test did not import an installed package")
    files = sorted(expected_source.rglob("*.py"))
    expected = {path.relative_to(expected_source).as_posix():
                hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
    actual = {path.relative_to(package_root).as_posix():
              hashlib.sha256(path.read_bytes()).hexdigest()
              for path in sorted(package_root.rglob("*.py"))}
    if actual != expected:
        raise ValueError("Imported runtime differs from the tested source snapshot")
    wheel_identity = _verify_installed_wheel(wheel, wheel_sha256, package_root) if origin == "wheel" else None
    if package_root.is_relative_to(root):
        logical_origin = "project://" + package_root.relative_to(root).as_posix()
    elif package_root.is_relative_to(Path(sys.prefix)):
        logical_origin = "environment://" + package_root.relative_to(sys.prefix).as_posix()
    else:
        logical_origin = "external-site-packages://neurodata_security_audit"
    identity = {
        "requested_origin": origin,
        "import_origin": logical_origin,
        "python": platform.python_version(),
        "executable_name": Path(sys.executable).name,
        "executable_sha256": hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),
        "runtime_sha256": actual,
        "wheel": wheel_identity,
        "cwd_relation": (Path.cwd().relative_to(root).as_posix()
                         if Path.cwd().is_relative_to(root) else "outside-project"),
        "path_policy": "Project added for source-only tests; src included only for source mode",
        "command": ["python", "tools/run_verified_tests.py", "--origin", origin,
                    "--output", "<new-output-directory>"],
        "path_privacy": "Origins normalized to project/environment; no home path is recorded",
    }
    output.mkdir(parents=True, exist_ok=False)
    (output / "before.json").write_text(json.dumps(identity, indent=2, sort_keys=True) + "\n")
    with (output / "tests.log").open("x", encoding="utf-8") as log:
        with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            suite = unittest.defaultTestLoader.discover(str(root / "tests"), top_level_dir=str(root))
            result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    loaded = {}
    for name, module in sorted(sys.modules.items()):
        if name == "neurodata_security_audit" or name.startswith("neurodata_security_audit."):
            path = Path(module.__file__).resolve()
            if not path.is_relative_to(package_root):
                raise ValueError("A test imported a runtime module from a different origin")
            loaded[name] = path.relative_to(package_root).as_posix()
    after = {path.relative_to(package_root).as_posix():
             hashlib.sha256(path.read_bytes()).hexdigest()
             for path in sorted(package_root.rglob("*.py"))}
    wheel_unchanged = (origin != "wheel" or wheel_identity ==
                       _verify_installed_wheel(wheel, wheel_sha256, package_root))
    summary = {
        "identity": identity, "loaded_modules": loaded,
        "tests_run": result.testsRun, "failures": len(result.failures),
        "errors": len(result.errors), "skips": len(result.skipped),
        "runtime_unchanged": after == actual,
        "wheel_unchanged": wheel_unchanged,
        "success": result.wasSuccessful() and after == actual and wheel_unchanged,
        "log_sha256": hashlib.sha256((output / "tests.log").read_bytes()).hexdigest(),
    }
    (output / "after.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin", choices=("source", "wheel"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--wheel", type=Path)
    parser.add_argument("--wheel-sha256")
    args = parser.parse_args()
    summary = run(Path(__file__).resolve().parents[1], args.output, args.origin,
                  args.wheel, args.wheel_sha256)
    print(json.dumps({key: summary[key] for key in ("tests_run", "failures", "errors", "skips", "success")}))
    raise SystemExit(0 if summary["success"] else 1)
