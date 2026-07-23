# NeuroData Release Security Audit

[![tests](https://github.com/viranovskaya/neurodata-release-security-audit/actions/workflows/tests.yml/badge.svg)](https://github.com/viranovskaya/neurodata-release-security-audit/actions/workflows/tests.yml)

I built this as a final local check before sharing an EEG or neuroimaging dataset.

It looks for information that can survive preprocessing or BIDS conversion by
mistake: participant names, contact details, dates of birth, exact recording dates,
old source IDs, staff names, scanner identifiers, local paths, credentials and
forgotten mapping files.

The scanner is read-only. It does not upload data, rewrite the release, extract
archives, follow symlinks or load EEG samples, image voxels or DICOM pixels.

## What it does

### Accounts for the whole release

- records every file, directory, symlink and special filesystem entry;
- calculates a deterministic size and SHA-256 manifest for every readable regular
  file;
- hashes files again after metadata inspection;
- checks that no entry was added, removed or changed during the scan;
- separates privacy findings from coverage limits.

Hashing streams all file bytes. It verifies integrity but does not interpret the
signal or image payload.

### Reads supported metadata

- BIDS JSON, TSV and CSV metadata;
- BrainVision `.vhdr` and `.vmrk`;
- the common EDF and BDF header;
- FIF, KIT `.con`/`.sqd`, continuous EEGLAB `.set` and EGI MFF metadata with
  the optional EEG readers;
- bounded XML metadata inside MFF directories;
- NIfTI headers without requesting voxel data;
- DICOM metadata before Pixel Data;
- small text, source, configuration and notebook files, including BIDS
  `.bval`, `.bvec`, `.bidsignore` and `.gitattributes`.

### Checks containers and links

- lists ZIP and TAR members without extraction;
- reports encrypted, nested, path-traversing, colliding and special archive entries;
- checks BrainVision, EEGLAB and supported BIDS cross-file references;
- reports missing, external, symlinked and wrong-case targets;
- keeps unsupported formats and payloads visible instead of treating them as clean.

## Install

The base install uses the Python standard library:

```bash
python3 -m pip install .
```

Add EEG format readers:

```bash
python3 -m pip install ".[formats]"
```

Add NIfTI and DICOM readers:

```bash
python3 -m pip install ".[imaging]"
```

Install both groups:

```bash
python3 -m pip install ".[formats,imaging]"
```

Optional readers fail visibly when they are missing or cannot read a file safely.

## Run

```bash
neurodata-security-audit scan /path/to/dataset
```

Save deterministic JSON, Markdown and visual HTML reports:

```bash
neurodata-security-audit scan /path/to/dataset \
  --json reports/audit.json \
  --markdown reports/audit.md \
  --html reports/audit.html
```

Keep reports outside the dataset. The command rejects report paths inside the
selected release so the source tree is not changed by the audit.

The HTML file is self-contained and works offline. It shows the finding severity,
coverage, integrity result, cross-file references and full SHA-256 manifest. It
uses the same masked report data as JSON and Markdown; it does not add another
metadata-reading path. When high-priority findings are present, the first link
jumps straight to a short table with the exact file, field location and a
plain-language next step.

Treat every report as private working material. Detected values are masked, but
an identifier that no rule recognized may still appear in a relative filename or
field location. Review the report before sharing or publishing it.

The terminal exits with:

- `0` when no high-severity finding is present;
- `1` when at least one high-severity finding is present;
- `2` when the scan fails, the release changes during the scan or report writing
  fails.

Review-level findings still need a decision even when the exit status is `0`.

## Add known names or source IDs

Generic name detection creates too many false positives. If you know the names,
hospital IDs or old subject codes used in the project, keep them in a private text
file with one value per line:

```text
Jane Doe
hospital-id-0042
```

Then run:

```bash
neurodata-security-audit scan /path/to/dataset \
  --sensitive-terms /private/path/known_identifiers.txt
```

The list must stay outside the dataset and should not be committed to Git.

## How to read the report

`findings` says what may be sensitive or unsafe.

`coverage` says how each release entry was handled:

- `fully_inspected_metadata`;
- `header_or_structure_only`;
- `payload_not_opened`;
- `unsupported_manual_review`;
- `not_traversed`.

`manifest` contains the file size and SHA-256 digest. `container_members` records
ZIP and TAR directory entries. `references` shows which supported cross-file links
are valid and which need repair.

A clean findings list does not override a coverage gap.

The report does not contain a delete button. Work on a copy, use a tool that
understands the flagged format, and run the audit again before replacing a
release candidate. JSON and TSV fields can usually be edited directly. FIF and
EDF/BDF headers need format-aware tools, followed by a check that the signal,
channels, sampling, annotations and duration were preserved.

## Limits

This is a practical release check for an honest curator. It is not proof that a
dataset is anonymous, secure or legally compliant.

The current version does not:

- test whether EEG signals or images can identify a person;
- perform MRI defacing, OCR or visual inspection;
- interpret NIfTI extension content;
- open DICOM pixels or metadata stored after the first Pixel Data element;
- scan archive member payloads or decrypt encrypted archives;
- analyse malware or hostile parser inputs;
- measure statistical re-identification risk in participant tables;
- replace the BIDS Validator, format-specific anonymisation or human review.

The full v0.2 boundary is in
[docs/v0.2_scope.md](docs/v0.2_scope.md). The report contract is in
[docs/report_schema.md](docs/report_schema.md). Public and real-reader checks are
recorded in [docs/v0.2_calibration.md](docs/v0.2_calibration.md). A separate
[50-dataset OpenNeuro calibration](docs/public_50_dataset_calibration.md) covers
EEG, MEG, iEEG, MRI and fMRI.

## Status

The private v0.1 snapshot was independently reviewed before it was merged.

The frozen v0.2 engineering candidate at `0275f36` also passed a separate
independent review after the complete inventory, NIfTI, DICOM, archive, reference
and integrity work was implemented. The visual HTML report was added later and is
not covered by that review. The first 50-dataset calibration candidate was
rejected during its separate review; its successor is still under local QA and
has no independent PASS. The project remains private. There is no public release
or PyPI package.

## License

MIT
