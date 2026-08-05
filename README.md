# NeuroData Release Security Audit

[![tests](https://github.com/viranovskaya/neurodata-release-security-audit/actions/workflows/tests.yml/badge.svg)](https://github.com/viranovskaya/neurodata-release-security-audit/actions/workflows/tests.yml)

## Purpose

This repository provides a local, read-only pre-release audit of privacy-relevant metadata, file coverage, references, and integrity in EEG and neuroimaging datasets.

## Practical problem

Participant names, dates, source IDs, staff or scanner identifiers, local paths, credentials, and forgotten mapping files can survive preprocessing or BIDS conversion. A release curator needs one inventory that distinguishes detected findings from files or payloads that the scanner did not interpret.

The audit supports a release decision; it does not prove anonymity or replace format-aware remediation, legal review, or scientific validation.

## What I implemented

I implemented:

- deterministic inventory and SHA-256 manifests for regular files, with before/after integrity checks;
- descriptor-bound, no-follow reads for core files so path replacement or symlink substitution fails closed;
- privacy-pattern checks for BIDS tables and metadata, small text/configuration files, BrainVision headers, EDF/BDF headers, and optional format readers;
- bounded metadata inspection for FIF, EEGLAB, KIT, MFF, MATLAB, XLSX, DOCX, NIfTI, and DICOM without requesting signal arrays, image voxels, embedded Office objects, or DICOM pixels;
- ZIP/TAR member inspection without extraction, including traversal, collision, encryption, nesting, and special-entry checks;
- BrainVision, EEGLAB, and supported BIDS reference checks;
- deterministic masked JSON, Markdown, and self-contained HTML reports;
- private review checklists and report-to-report comparison.

The report keeps three concepts separate: findings, coverage, and scan integrity. Its top-level release state is `STOP`, `HOLD`, or no automated hold; a clean findings list cannot override a coverage gap.

## Data and sample

The repository contains code, synthetic fixtures, aggregate calibration records, and redacted benchmark labels. It does not contain participant datasets or reports generated from potentially sensitive source metadata.

Evidence is deliberately split by source:

- a 50-case synthetic leak benchmark contains 103 labelled findings across text, EEG, imaging, archive, and reference cases;
- generated format fixtures exercise BrainVision, EDF/BDF, FIF, NIfTI, and DICOM paths;
- three hash-pinned public fixtures exercise EEGLAB, KIT, and MFF readers;
- a fixed, non-random 50-dataset OpenNeuro calibration uses bounded slices: 39 include one hash-checked public payload and 11 are metadata-only;
- two small exploratory web-pilot samples tested report comprehension (five and eight complete responses), not leak detection or psychometric validity.

## Validated outputs

The scanner emits:

- a complete entry inventory and regular-file manifest;
- masked findings with severity and field location;
- per-entry coverage states;
- cross-file reference results;
- integrity status;
- deterministic JSON, Markdown, and offline HTML reports.

Format claims are bounded by the evidence actually run:

| Format or structure | Implemented inspection | Current evidence |
|---|---|---|
| BIDS JSON/TSV/CSV and small metadata files | decoded metadata and bounded text checks | synthetic tests and public BIDS/OpenNeuro calibration |
| BrainVision | text headers, marker metadata, and references; no signal samples | synthetic fixtures and public calibration |
| EDF/BDF | common fixed header; no signal samples | generated benchmark cases and four public Sleep-EDF files |
| FIF | optional MNE metadata; no preload | generated format fixture |
| EEGLAB, KIT, MFF | optional reader metadata and linked-file checks; no preload | synthetic tests plus three hash-pinned public smoke fixtures |
| MATLAB | variable names, classes, shapes, and small string values; no numeric-array load | synthetic tests and a fixed GIN run with 20 explicit nested-structure limits |
| XLSX/DOCX | bounded text, comments, core metadata, macros, and external-link checks | synthetic tests and fixed GIN calibration files |
| NIfTI | header metadata; no voxel request; extensions remain a visible limit | generated nibabel fixture and public OpenNeuro calibration |
| DICOM | metadata before Pixel Data; no pixel request | generated pydicom fixture only |
| ZIP/TAR | member names and structure; no extraction or member-payload scan | synthetic archive tests |

The frozen 50-dataset calibration completed 50/50 bounded slices and passed both integrity rechecks. It is an engineering robustness and field-sensitivity calibration, not a representative privacy study. Exact scope and aggregate results are in [the calibration record](docs/public_50_dataset_calibration.md).

## Reproducibility

CI tests Python 3.10 and 3.13 with the base package, EEG-reader extras, imaging-reader extras, and both groups together. Separate jobs build the wheel twice, compare bytes, install the exact wheel outside the checkout, run the copied functional suite, validate report schemas, and exercise the installed CLI.

Supported optional-reader ranges are declared in `pyproject.toml`. Exact versions used for the frozen public calibration are recorded in its documentation; a code or report change requires a new calibration claim rather than reuse of the old result.

The labelled benchmark keeps failed first runs and corrected results instead of replacing them. Public-format smoke inputs are hash-pinned. The 50-dataset registry binds dataset IDs, source commits, and payload status, while sensitive per-dataset reports remain outside the repository.

## Limitations

- The scanner does not test signal, image, or tabular re-identification risk.
- It does not perform MRI defacing, OCR, malware analysis, or visual inspection.
- NIfTI extension contents, DICOM metadata after the first Pixel Data element, Office embedded objects, archive member payloads, encrypted archives, and external link targets are not inspected.
- Legacy nested EEGLAB and standalone MATLAB structures can remain explicit manual-review cases.
- Optional third-party readers receive stable checked paths, but their internal path handling is outside this package.
- DICOM evidence uses generated fixtures; supported-format behavior is not evidence of general clinical-data coverage.
- The OpenNeuro sample is bounded and non-random, and its aggregate findings do not establish that any source dataset is unsafe.
- A successful scan is not proof of anonymity, GDPR/HIPAA compliance, ethical shareability, or scientific validity.

The detailed boundaries are in [v0.2 scope](docs/v0.2_scope.md), the [report schema](docs/report_schema.md), and the [remediation guide](docs/remediation_guide.md).

## Installation and run

Python 3.10 or newer is required.

```bash
git clone https://github.com/viranovskaya/neurodata-release-security-audit.git
cd neurodata-release-security-audit
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install .
```

Install optional metadata readers as needed:

```bash
python3 -m pip install ".[formats]"
python3 -m pip install ".[imaging]"
python3 -m pip install ".[formats,imaging]"
```

Run a local audit and keep reports outside the selected release:

```bash
neurodata-security-audit scan /path/to/dataset \
  --json reports/audit.json \
  --markdown reports/audit.md \
  --html reports/audit.html
```

The command refuses report paths inside the dataset and refuses to replace an existing report. Exit status is `0` with no high-severity finding, `1` with at least one high-severity finding, and `2` for scan, integrity, or report-publication failure. Review-level findings still require a decision when the exit status is `0`.

Known private terms can be supplied from a file kept outside the dataset:

```bash
neurodata-security-audit scan /path/to/dataset \
  --sensitive-terms /private/path/known_identifiers.txt
```

Create a private checklist or compare two scans of the same release candidate:

```bash
neurodata-security-audit checklist reports/audit.json \
  --tsv review/audit-checklist.tsv

neurodata-security-audit compare \
  reports/baseline.json reports/current.json \
  --confirm-same-dataset \
  --json review/comparison.json \
  --markdown review/comparison.md
```

Treat reports and known-term files as private working material. Use only synthetic or fully redacted examples in public issues; private vulnerability reporting is described in [SECURITY.md](SECURITY.md).

## Citation

Public beta `v0.2.0b1` is the current GitHub prerelease. The `main` branch uses development version `0.2.1.dev0`; it is not a release. Citation metadata for version `0.2.0-beta.1` is in [`CITATION.cff`](CITATION.cff). The code is released under the [MIT License](LICENSE); there is no PyPI release.

## Current status

- **Implemented:** local inventory, privacy findings, bounded metadata readers, archive/reference checks, integrity rechecks, reports, checklist, and comparison.
- **Tested:** synthetic unit/integration cases, exact-wheel installs, deterministic builds, schema validation, and three hash-pinned public format smoke fixtures.
- **Evaluated:** bounded local scans of 50 fixed OpenNeuro slices and two exploratory report-comprehension samples.
- **Planned:** independent curator use on separately controlled release copies; no additional format or detector is claimed without new evidence.
- **Not yet validated:** arbitrary format variants, hostile inputs, anonymity, legal/ethical compliance, clinical use, or scientific suitability.
