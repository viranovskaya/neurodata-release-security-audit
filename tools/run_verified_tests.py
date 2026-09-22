"""Run unittest and bind its result to runtime imports in the same process."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib
import json
import platform
import sys
import unittest
from pathlib import Path


def run(root: Path, output: Path, origin: str) -> dict[str, object]:
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
    summary = {
        "identity": identity, "loaded_modules": loaded,
        "tests_run": result.testsRun, "failures": len(result.failures),
        "errors": len(result.errors), "skips": len(result.skipped),
        "runtime_unchanged": after == actual,
        "success": result.wasSuccessful() and after == actual,
        "log_sha256": hashlib.sha256((output / "tests.log").read_bytes()).hexdigest(),
    }
    (output / "after.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin", choices=("source", "wheel"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    summary = run(Path(__file__).resolve().parents[1], args.output, args.origin)
    print(json.dumps({key: summary[key] for key in ("tests_run", "failures", "errors", "skips", "success")}))
    raise SystemExit(0 if summary["success"] else 1)
