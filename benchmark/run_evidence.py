"""Preserve paired benchmark reruns and optionally recover historical hidden evidence."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import io
import json
import platform
import subprocess
import sys
import zipfile
from pathlib import Path

from benchmark.core import render_benchmark_markdown, run_benchmark
import neurodata_security_audit


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _source_hashes(root: Path) -> dict[str, str]:
    paths = [root / "pyproject.toml", root / ".github/constraints/calibration-readers.txt"]
    for folder in ("src", "benchmark", "tests", "tools", "usability"):
        paths.extend(path for path in (root / folder).rglob("*")
                     if path.suffix in (".py", ".json") and "results" not in path.parts)
    return {path.relative_to(root).as_posix(): _sha(path.read_bytes()) for path in sorted(paths)}


def _runtime_identity(root: Path) -> dict[str, object]:
    """Bind the imported scanner to source bytes before and after a replay."""
    package = Path(neurodata_security_audit.__file__).resolve().parent
    source = root.resolve() / "src/neurodata_security_audit"
    expected = {p.relative_to(source).as_posix(): _sha(p.read_bytes())
                for p in sorted(source.rglob("*.py"))}
    actual = {p.relative_to(package).as_posix(): _sha(p.read_bytes())
              for p in sorted(package.rglob("*.py"))}
    if not expected or actual != expected:
        raise ValueError("Imported scanner runtime differs from source snapshot")
    for name, module in tuple(sys.modules.items()):
        if name == "neurodata_security_audit" or name.startswith("neurodata_security_audit."):
            filename = getattr(module, "__file__", None)
            if filename is None or not Path(filename).resolve().is_relative_to(package):
                raise ValueError("Scanner module imported from a different runtime origin")
    if package == source:
        origin = "source://neurodata_security_audit"
    elif package.is_relative_to(Path(sys.prefix).resolve()):
        origin = "environment://" + package.relative_to(Path(sys.prefix).resolve()).as_posix()
    else:
        origin = "external://neurodata_security_audit"
    return {"import_origin": origin, "module_sha256": actual}


def _git_identity(root: Path) -> dict[str, str | None]:
    identity = {"git_mode": "source-snapshot", "git_head": None,
                "tracked_diff_sha256": None}
    # Never let Git silently discover an unrelated enclosing repository.
    if not (root / ".git").exists():
        return identity
    try:
        top = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], cwd=root,
            text=True, stderr=subprocess.DEVNULL,
        ).strip()
        if Path(top).resolve() != root.resolve():
            return identity
        head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root,
            text=True, stderr=subprocess.DEVNULL,
        ).strip()
        diff = subprocess.check_output(
            ["git", "diff", "--binary", "HEAD"], cwd=root,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        identity["git_mode"] = "git-metadata-unavailable"
        return identity
    return {"git_mode": "project-checkout", "git_head": head,
            "tracked_diff_sha256": _sha(diff)}


def _recover_hidden(archives: Path, output: Path) -> dict[str, object]:
    specifications = (
        ("v1", "neurodata-benchmark-hidden-v1-blocked-76ee38c.zip", "hidden_cases.json", "hidden_result.json",
         "825f90386ca6c2ebf95ea6b488da03dcbe08d9d06d189c02ee2abaae15e34c72",
         "913e4c7ae76fa6453d542057f53b017752b4dd2118fe15750b0fdb0dde331611",
         "ee798ac258daa8d32e15d1eefc34626898941c10ea005abfbacde7303f80d24d"),
        ("v2", "neurodata-benchmark-hidden-v2-pass-5471b39.zip", "hidden_cases_v2.json", "hidden_result_v2_a.json",
         "5040c1572177cebe8ca0d1ff992d5487c7215f03898dbff5cba79792a5936962",
         "c90db8b3208164c801ee14c7b568d6cba80927960331d2bfe01046a310a75f80",
         "4d6a0bd3bf3c32902faf0c331311a7e326cfa8dbe02499257bb6d8f8cabcf496"),
    )
    recovered = {}
    case_documents = []
    for version, filename, cases_name, result_name, cases_sha, result_sha, archive_sha in specifications:
        archive_bytes = (archives / filename).read_bytes()
        if _sha(archive_bytes) != archive_sha:
            raise ValueError("Historical full archive hash differs from the frozen review")
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            if archive.testzip() is not None:
                raise ValueError("Historical archive integrity failed")
            contents = {name: archive.read(name) for name in archive.namelist()}
        if _sha(contents[cases_name]) != cases_sha or _sha(contents[result_name]) != result_sha:
            raise ValueError("Historical case/result identity differs from the frozen review")
        # No extraction: retain the exact original ZIP, avoiding archive path traversal.
        (output / filename).write_bytes(archive_bytes)
        member_hashes = {name: _sha(data) for name, data in contents.items()}
        cases = json.loads(contents[cases_name])
        case_documents.append(cases)
        result_text = contents[result_name].decode()
        result, end = json.JSONDecoder().raw_decode(result_text)
        trailer = result_text[end:]
        # The hash-pinned v2 archive has a literal backslash-n after its JSON.
        # Preserve the original bytes and disclose this, rather than silently
        # replacing the historical artifact with a newly serialized result.
        literal_newline = version == "v2" and trailer == "\\n"
        if trailer.strip() and not literal_newline:
            raise ValueError("Unexpected trailing data in historical JSON")
        recovered[version] = {
            "archive": filename, "archive_sha256": _sha(archive_bytes),
            "member_sha256": member_hashes, "summary": result["summary"],
            "literal_backslash_n_trailer": literal_newline,
            "verification": "Archive/member hashes and preserved result; NOT a rerun of the historical wheel",
        }
    before, after = case_documents
    # Compare every other byte-equivalent JSON value, not just the disputed case.
    corrected = json.loads(json.dumps(before))
    changes = []
    for case in corrected["cases"]:
        if case["case_id"] == "hidden_xml_dynamic_identifier":
            for label in case["expected_findings"]:
                if label["location"] == "XML dynamic field record.field":
                    label["location"] = "XML dynamic field record.<field>"
                    changes.append("hidden_xml_dynamic_identifier: report-safe XML location")
    if len(changes) != 1 or corrected != after:
        raise ValueError("Hidden v1/v2 difference is not exactly the documented label adjudication")
    recovered["case_diff"] = changes
    recovered["limitations"] = [
        "Independent here refers to the historical machine reviewer, not human validation.",
        "Adjudicated v2 is not a second blind evaluation.",
        "Historical zero masking failures used the old encoding-naive oracle.",
    ]
    return recovered


def run(output: Path, hidden_archives: Path | None) -> dict[str, object]:
    root = Path(__file__).resolve().parents[1]
    sources = _source_hashes(root)
    runtime = _runtime_identity(root)
    identity = {
        **_git_identity(root),
        "source_sha256": sources,
        "runtime": runtime,
        "source_fingerprint": _sha(json.dumps(sources, sort_keys=True).encode()),
        "python": platform.python_version(),
        "platform": platform.system() + "-" + platform.machine(),
        "packages": dict(sorted((dist.metadata["Name"], dist.version) for dist in importlib.metadata.distributions())),
        "scope": "Source snapshot replay; publication status is not inferred; not independent validation",
    }
    output.mkdir(parents=True, exist_ok=False)
    _write_json(output / "identity-before.json", identity)
    summaries = {}
    gates = []
    for name, relative in (
        ("development", "benchmark/cases.json"),
        ("locked_v2", "benchmark/locked_v2.json"),
        ("challenge_v1", "benchmark/challenge_v1.json"),
        ("adversarial", "benchmark/cases/development_privacy_adversarial.json"),
    ):
        hashes = []
        for repeat in (1, 2):
            result = run_benchmark(root / relative)
            json_path = output / f"{name}-run{repeat}.json"
            md_path = output / f"{name}-run{repeat}.md"
            _write_json(json_path, result)
            md_path.write_text(render_benchmark_markdown(result), encoding="utf-8")
            hashes.append({"json": _sha(json_path.read_bytes()), "markdown": _sha(md_path.read_bytes())})
        summary = result["summary"]
        passed = all(summary[f"matched_{metric}"] == summary[f"expected_{metric}"]
                     for metric in ("findings", "references", "container_members", "coverage"))
        passed = passed and all(summary[metric] == 0 for metric in (
            "unexpected_findings", "unexpected_references", "unexpected_container_members",
            "masking_failures", "integrity_failures",
        ))
        passed = passed and summary["clean_controls"] == summary["control_cases"]
        summaries[name] = {"input": relative, "summary": summary, "hashes": hashes,
                           "paired_bytes_identical": hashes[0] == hashes[1], "target_gate": passed}
        gates.extend([passed, hashes[0] == hashes[1]])
        print(f"{name}: {summary['matched_findings']}/{summary['expected_findings']}; paired={hashes[0] == hashes[1]}", flush=True)
    history = _recover_hidden(hidden_archives, output) if hidden_archives else None
    source_unchanged = sources == _source_hashes(root)
    runtime_after = _runtime_identity(root)
    runtime_unchanged = runtime == runtime_after
    result = {"identity": identity, "suites": summaries, "historical_hidden": history,
              "source_unchanged": source_unchanged, "runtime_after": runtime_after,
              "runtime_unchanged": runtime_unchanged,
              "all_gates_pass": all(gates) and source_unchanged and runtime_unchanged}
    _write_json(output / "evidence.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--hidden-archives", type=Path)
    args = parser.parse_args()
    raise SystemExit(0 if run(args.output, args.hidden_archives)["all_gates_pass"] else 1)
