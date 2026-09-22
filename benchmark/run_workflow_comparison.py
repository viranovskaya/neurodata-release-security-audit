"""Run the bounded, synthetic MNE-plus-audit example; never score competitors."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import date, datetime, timezone
from pathlib import Path

from benchmark.core import _masking_failures_from_text
from neurodata_security_audit import __version__
from neurodata_security_audit.html_report import render_html
from neurodata_security_audit.reporting import render_json, render_markdown
from neurodata_security_audit.scanner import scan_dataset


def _hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*")) if path.is_file()
    }


def _write_audit(report, destination: Path, seeds: list[str]) -> dict[str, list[str]]:
    # Check exactly the UTF-8 bytes saved, never a second renderer invocation.
    texts = (render_json(report), render_markdown(report), render_html(report))
    for suffix, text in zip(("json", "md", "html"), texts):
        (destination / f"audit.{suffix}").write_bytes(text.encode("utf-8"))
    return _masking_failures_from_text(*texts, seeds)


def run(output: Path) -> dict[str, object]:
    import mne
    import numpy as np

    output.mkdir(parents=True, exist_ok=False)
    protocol = Path(__file__).parents[1] / "docs/workflow_comparison_protocol.md"
    protocol_bytes = protocol.read_bytes()
    identity = {
        "protocol_sha256": hashlib.sha256(protocol_bytes).hexdigest(),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "mne": mne.__version__,
        "neurodata": __version__,
        "status": "pre-run; developer-authored synthetic example, not blind",
    }
    (output / "protocol.md").write_bytes(protocol_bytes)
    (output / "prerun.json").write_text(json.dumps(identity, indent=2) + "\n")
    rows = []
    all_gates = []
    for name in ("recording_only", "recording_and_sidecar", "control"):
        root = output / name
        source = root / "input"
        baseline = root / "after_mne"
        source.mkdir(parents=True)
        info = mne.create_info(["Fz"], 100.0, ["eeg"])
        seeds = []
        if name != "control":
            info["subject_info"] = {
                "first_name": "SyntheticGiven", "last_name": "SyntheticFamily",
                "birthday": date(1990, 2, 3),
            }
            seeds.extend(["SyntheticGiven", "SyntheticFamily", "1990-02-03"])
        raw = mne.io.RawArray(np.zeros((1, 10)), info, verbose="ERROR")
        if name != "control":
            raw.set_meas_date(datetime(2020, 2, 3, tzinfo=timezone.utc))
        raw.save(source / "sample_raw.fif", verbose="ERROR")
        raw.close()
        if name != "recording_only":
            email = "n/a" if name == "control" else "synthetic.participant@example.org"
            (source / "participants.tsv").write_text(
                f"participant_id\temail\nsub-01\t{email}\n", encoding="utf-8",
            )
            if name != "control":
                seeds.append(email)
        source_hashes = _hashes(source)
        shutil.copytree(source, baseline)
        with mne.io.read_raw_fif(source / "sample_raw.fif", preload=True, verbose="ERROR") as before:
            after = before.copy().anonymize(daysback=3650, keep_his=False, verbose="ERROR")
            after.save(baseline / "sample_raw.fif", overwrite=True, verbose="ERROR")
            after.close()
            with mne.io.read_raw_fif(baseline / "sample_raw.fif", preload=True, verbose="ERROR") as reopened:
                subject = reopened.info.get("subject_info") or {}
                observations = {
                    "original_first_name_absent": subject.get("first_name") != "SyntheticGiven",
                    "original_last_name_absent": subject.get("last_name") != "SyntheticFamily",
                    "original_birthday_absent": subject.get("birthday") != date(1990, 2, 3),
                    "recording_shift_days": (
                        (before.info["meas_date"] - reopened.info["meas_date"]).days
                        if before.info["meas_date"] and reopened.info["meas_date"] else None
                    ),
                    "signal_equal": bool(np.array_equal(before.get_data(), reopened.get_data())),
                    "channels_equal": before.ch_names == reopened.ch_names,
                    "sampling_rate_equal": before.info["sfreq"] == reopened.info["sfreq"],
                }
        fixed_hashes = _hashes(baseline)
        report_hashes = []
        reports = []
        gates = []
        for repeat in (1, 2):
            destination = root / f"audit{repeat}"
            destination.mkdir()
            report = scan_dataset(baseline)
            failures = _write_audit(report, destination, seeds)
            gates.append({
                "no_seed_leak": not any(failures.values()),
                "manifest_recheck": report.manifest_recheck_passed,
                "tree_recheck": report.release_tree_recheck_passed,
                "fixed_input_unchanged": _hashes(baseline) == fixed_hashes,
                "original_unchanged": _hashes(source) == source_hashes,
            })
            report_hashes.append(_hashes(destination))
            reports.append(report.to_dict())
        gates.append({"report_bytes_identical": report_hashes[0] == report_hashes[1]})
        rows.append({
            "case": name,
            "input_hashes": source_hashes,
            "after_mne_hashes": fixed_hashes,
            "mne_observations": observations,
            "sidecar_unchanged_by_mne": (
                source_hashes["participants.tsv"] == fixed_hashes["participants.tsv"]
                if "participants.tsv" in source_hashes else None
            ),
            "neurodata_findings": [
                {key: finding[key] for key in ("code", "severity", "path", "location")}
                for finding in reports[0]["findings"]
            ],
            "report_hashes": report_hashes,
            "gates": gates,
        })
        all_gates.extend(value for gate in gates for value in gate.values())
    result = {
        "identity": identity, "cases": rows, "mechanical_gates_pass": all(all_gates),
        "semantic_adjudication": "See the written comparison; no superiority score is calculated.",
    }
    (output / "observations.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    result = run(parser.parse_args().output)
    print(json.dumps({"cases": len(result["cases"]), "mechanical_gates_pass": result["mechanical_gates_pass"]}))
    raise SystemExit(0 if result["mechanical_gates_pass"] else 1)
