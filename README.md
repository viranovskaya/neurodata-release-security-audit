# NeuroData Release Security Audit

[![tests](https://github.com/viranovskaya/neurodata-release-security-audit/actions/workflows/tests.yml/badge.svg)](https://github.com/viranovskaya/neurodata-release-security-audit/actions/workflows/tests.yml)

A local final check for EEG and neuroimaging datasets before sharing them.

The audit looks for privacy-relevant metadata, forgotten files, broken
references, unsupported content and changes made while the scan is running. It
creates a readable HTML report without uploading the dataset or modifying it.

> **Beta software:** this tool helps a human curator find things to review. It
> does not prove anonymity, approve a release, or replace legal, ethical or
> scientific review.

## Quick start

Python 3.10 or newer is required. Download the wheel and `SHA256SUMS` from the
[`v0.3.0b1` prerelease](https://github.com/viranovskaya/neurodata-release-security-audit/releases/tag/v0.3.0b1), then install it in a fresh environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install ./neurodata_release_security_audit-0.3.0b1-py3-none-any.whl
```

Start the local browser interface:

```bash
neurodata-security-audit ui
```

Your browser will open a temporary page on `127.0.0.1`.

1. Enter the full path to the dataset folder.
2. Enter a separate, new folder for the reports.
3. Choose **Run local audit**.
4. Open the HTML report and review every high, review and coverage item.

The dataset stays on your computer. The interface reads it in place and writes
`audit.json`, `audit.md` and `audit.html` to the report folder. It never
uploads dataset files or report contents.

Close the terminal process with `Ctrl+C` when you finish.

## What the audit checks

- participant, staff, device and acquisition metadata;
- names, dates, IDs, local paths, email addresses, credentials and known private
  terms in supported fields;
- every file, folder, symlink and unsupported filesystem entry in the release;
- linked files used by BrainVision, EEGLAB and supported BIDS structures;
- ZIP and TAR member names and structure without extraction;
- whether files or symlink targets changed during the scan;
- whether a file was fully inspected, inspected only at header level, skipped,
  unsupported or left for manual review.

Findings are masked in the reports. The audit tells you where to look without
copying the detected value into a shareable report.

## Supported formats

The base install handles BIDS metadata, small text/configuration files,
BrainVision headers, EDF/BDF headers, XLSX, DOCX, ZIP and TAR. Optional readers
extend metadata coverage:

| Format | What is inspected | Extra |
|---|---|---|
| BIDS JSON/TSV/CSV and small text files | decoded metadata and bounded text | base |
| BrainVision | header and marker metadata, linked-file references | base |
| EDF/BDF | common fixed header, not signal samples | base |
| XLSX/DOCX | bounded text, comments, core metadata, macros and external links | base |
| ZIP/TAR | member names and archive structure, not member payloads | base |
| FIF, EEGLAB SET, KIT, MFF | metadata through optional MNE readers, without preload | `formats` |
| MATLAB | variable names, classes, shapes and small string values | `formats` |
| NIfTI | header metadata, not voxels | `imaging` |
| DICOM | metadata before Pixel Data, not pixels | `imaging` |

For mixed datasets, install both optional groups:

```bash
python3 -m pip install \
  "./neurodata_release_security_audit-0.3.0b1-py3-none-any.whl[formats,imaging]"
```

Format support is intentionally bounded. A supported extension does not mean
that every payload or every re-identification risk inside that format is
inspected.

## How to read the result

The report separates **findings**, **coverage** and **scan integrity**.

| State | Meaning | What to do |
|---|---|---|
| `STOP` | the release changed during the scan or the audit could not complete safely | do not use this report; make a stable copy and scan again |
| `HOLD` | at least one high-priority finding remains | inspect the original field and correct or document it before release |
| `Review required` | no automatic high-priority hold, but human decisions are still required | review findings, coverage gaps and format limits |

Passing integrity checks only means that the selected release stayed stable
during the audit. It is not proof that the dataset is safe to publish.

## Command-line use

The same audit can run without the browser:

```bash
neurodata-security-audit scan /path/to/dataset \
  --json /path/to/reports/audit.json \
  --markdown /path/to/reports/audit.md \
  --html /path/to/reports/audit.html
```

Report paths must be outside the dataset and must not already exist. Exit status
is `0` when there is no high-priority finding, `1` when a high-priority finding
creates a hold, and `2` when scanning, integrity checking or report publication
fails. Exit status `0` still requires human review.

Try the included synthetic demo first. It deliberately returns a hold:

```bash
mkdir -p /tmp/neurodata-audit-demo-reports
neurodata-security-audit scan examples/reviewer_demo \
  --json /tmp/neurodata-audit-demo-reports/audit.json \
  --markdown /tmp/neurodata-audit-demo-reports/audit.md \
  --html /tmp/neurodata-audit-demo-reports/audit.html
```

If you know private names or identifiers that should never appear in the
release, keep them in a text file outside the dataset and add:

```bash
neurodata-security-audit scan /path/to/dataset \
  --sensitive-terms /private/path/known_identifiers.txt
```

Treat audit reports and sensitive-term files as private working material.

## Review a corrected dataset

After fixing a private working copy, scan it again to new report paths. You can
then create a checklist or compare two reports from the same dataset:

```bash
neurodata-security-audit checklist reports/audit.json \
  --tsv review/audit-checklist.tsv

neurodata-security-audit compare \
  reports/baseline.json reports/current.json \
  --confirm-same-dataset \
  --json review/comparison.json \
  --markdown review/comparison.md
```

Documenting an expected or false-positive match records a curator decision. It
does not remove the original finding or turn the audit into release approval.

## What the audit does not do

- prove that a dataset is anonymous;
- certify GDPR, HIPAA, ethics or other legal compliance;
- assess signal, image or tabular re-identification risk;
- deface MRI images, run OCR, inspect image pixels or signal samples;
- scan encrypted archive contents, archive member payloads or Office embedded
  objects;
- inspect NIfTI extension contents or DICOM metadata after the first Pixel Data
  element;
- provide malware analysis, clinical validation or scientific validation;
- protect against a malicious local user controlling the computer during the
  scan.

See the [scope](docs/v0.2_scope.md), [report schema](docs/report_schema.md),
[remediation guide](docs/remediation_guide.md) and [security policy](SECURITY.md)
for the detailed boundaries.

## Evidence and reproducibility

The repository contains code, synthetic fixtures, redacted benchmark labels and
aggregate calibration records. It does not contain participant datasets or
reports generated from potentially sensitive source metadata.

Current evidence includes:

- a 50-case synthetic leak benchmark with 103 labelled findings;
- generated BrainVision, EDF/BDF, FIF, NIfTI and DICOM fixtures;
- three hash-pinned public EEGLAB, KIT and MFF smoke fixtures;
- a fixed, bounded 50-dataset OpenNeuro calibration;
- a fixed public [MATLAB/Office calibration](docs/matlab_office_calibration.md);
- exploratory report-comprehension pilots, which are not leak-detection or
  psychometric validation.

The 50-dataset run is an engineering calibration, not a representative privacy
study and not evidence that any source dataset is unsafe. Its exact scope is in
the [calibration record](docs/public_50_dataset_calibration.md).

CI tests Python 3.10, 3.12 and 3.13, base and optional-reader installs, exact
installed wheels outside the source checkout, clean installs on Linux, macOS
and Windows, deterministic builds and report-schema validation.

## Development install

```bash
git clone https://github.com/viranovskaya/neurodata-release-security-audit.git
cd neurodata-release-security-audit
git checkout v0.3.0b1
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install ".[formats,imaging]"
python3 -m unittest -v
```

## Feedback and citation

This is a public beta. Practical reports from researchers using their own local
release copies are especially useful. Do not attach datasets, raw identifiers
or unredacted audit reports to public issues. Use the private reporting path in
[`SECURITY.md`](SECURITY.md) for a possible privacy or security issue.

If you use the software, cite the release described in
[`CITATION.cff`](CITATION.cff). GitHub Releases are the only package
distribution channel for this beta; it is not published on PyPI.

Released under the [MIT License](LICENSE).
