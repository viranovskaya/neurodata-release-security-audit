# NeuroData Release Security Audit

[![tests](https://github.com/viranovskaya/neurodata-release-security-audit/actions/workflows/tests.yml/badge.svg)](https://github.com/viranovskaya/neurodata-release-security-audit/actions/workflows/tests.yml)

I built this as a final local check before sharing an EEG dataset.

It looks for things that can easily survive preprocessing or BIDS conversion by mistake: names, contact details, dates of birth, exact recording dates, old source filenames, local computer paths, participant keys and obvious credentials.

The scanner is read-only. It does not upload anything, change the dataset or load the EEG signal.

## What it checks

- BIDS JSON, TSV and CSV metadata;
- BrainVision `.vhdr` and `.vmrk` files;
- the common header of EDF and BDF files;
- FIF, continuous EEGLAB `.set` and EGI MFF recording metadata with the optional format readers;
- bounded XML metadata inside MFF directories;
- small text files, filenames and the release directory tree;
- backups, spreadsheets, archives, editor files, private configuration directories,
  symlinks and files it could not read.

Detected values are masked in the report. Known identifiers, contact details, dates,
credentials and local or network paths are also masked when they appear in a release
path. Other filenames remain visible, so the report itself should still be checked
before sharing.

## Install

From the repository root:

```bash
python3 -m pip install .
```

This installs the `neurodata-security-audit` command and the standard-library checks.

To inspect FIF, EEGLAB and MFF recording metadata too:

```bash
python3 -m pip install ".[formats]"
```

These readers use MNE with signal preloading disabled. If the optional readers are missing or cannot inspect a format safely, the gap is shown in the report instead of treating the file as clean.

## Run

```bash
neurodata-security-audit scan /path/to/dataset
```

Save both report formats:

```bash
neurodata-security-audit scan /path/to/dataset \
  --json reports/audit.json \
  --markdown reports/audit.md
```

Keep report files outside the dataset being checked. The command rejects report paths inside the dataset so the release tree stays unchanged.

The terminal prints a short summary. Exit status is:

- `0`: no high-severity finding;
- `1`: at least one high-severity finding;
- `2`: the scan or report writing failed.

Review-level findings do not change the exit status. They still need to be read before release.

For development without installation:

```bash
PYTHONPATH=src python3 -m neurodata_security_audit scan /path/to/dataset
```

## Check names or IDs you already know

Generic name detection is unreliable. A project author or laboratory name can look exactly like a participant name. If you know the names, old subject codes or hospital IDs used in the source project, put them in a private text file with one value per line:

```text
Jane Doe
hospital-id-0042
```

Then run:

```bash
neurodata-security-audit scan /path/to/dataset \
  --sensitive-terms /private/path/known_identifiers.txt
```

The matching values are masked in file contents and report paths. The command requires this list to stay outside the dataset. Do not commit it to Git.

## Limits

This is an extra release check, not proof that a dataset is anonymous or legally compliant. It does not replace the BIDS Validator, format-specific anonymisation or human review. It also does not test whether the EEG signal itself could identify someone.

Legacy EEGLAB files that store the whole dataset inside one nested MATLAB structure receive a visible coverage warning. The scanner does not call MNE for that file because it may also load the signal array. MATLAB 7.3 files stay on a conservative text-only path. External data references that leave the selected release directory are reported and are not followed.

The current version is designed for accidental release mistakes. It does not inspect encrypted archives, malware or files written to attack the parser.

## Status

Private v0.1 candidate. The synthetic test suite, real-format FIF, EEGLAB and official MNE MFF fixtures, six public BIDS EEG examples and four real Sleep-EDF files have been checked. Independent review has not happened yet.

The exact scope is in [docs/mvp_spec.md](docs/mvp_spec.md). Test runs are documented in [docs/calibration.md](docs/calibration.md), [docs/real_dataset_check.md](docs/real_dataset_check.md) and [docs/mff_check.md](docs/mff_check.md).

The implemented leak categories and explicit limits are tracked in [docs/leak_coverage.md](docs/leak_coverage.md).

The latest implementation cross-check is in [docs/progress_report_2026-07-23.md](docs/progress_report_2026-07-23.md).

The final local gate is recorded in [docs/final_local_gate_2026-07-23.md](docs/final_local_gate_2026-07-23.md).

The short independent test is in [docs/external_review_guide.md](docs/external_review_guide.md).

## License

MIT
