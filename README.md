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
metadata-reading path. The first action section says whether to stop the release,
review an item or continue to the coverage check. It lists the exact file, field
location and next step without exposing the matched value. Unsupported and
untraversed entries are repeated in a separate manual-review list.

The status at the top is the release decision: `STOP`, `HOLD` or no automated
hold. Scan integrity is shown separately and is never presented as release
clearance. Finding filters help with long reports, while printing always includes
the complete finding table.

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

`coverage` says how each file, folder, symlink or other filesystem entry was
handled:

- `fully_inspected_metadata`;
- `header_or_structure_only`;
- `payload_not_opened`;
- `unsupported_manual_review`;
- `not_traversed`.

`manifest` contains the file size and SHA-256 digest. `container_members` records
ZIP and TAR directory entries. `references` shows which supported cross-file links
are valid and which need repair.

A clean findings list does not override a coverage gap.

The report does not contain a delete button. Start with **What to do next**, work
on a copy and use a tool that understands the flagged format. Run the audit again
before replacing a release candidate. JSON and TSV fields can usually be edited
directly. FIF and EDF/BDF headers need format-aware tools, followed by a check
that the signal, channels, sampling, annotations and duration were preserved.
The [format remediation guide](docs/remediation_guide.md) gives a short checklist
for FIF, EEGLAB, EDF/BDF, MFF, DICOM, NIfTI, JSON and TSV.

## Keep track of a private review

Create a TSV checklist from the first JSON report:

```bash
neurodata-security-audit checklist reports/audit.json \
  --tsv review/audit-checklist.tsv
```

After correcting a private copy and scanning it again, compare the two reports:

```bash
neurodata-security-audit compare \
  reports/baseline.json reports/current.json \
  --confirm-same-dataset \
  --json review/comparison.json \
  --markdown review/comparison.md
```

The comparison separates new, remaining and resolved review items. A resolved
item only means that the same masked record is no longer reported. It is not
proof that the dataset is anonymous or ready to share. Use
`--confirm-same-dataset` only after checking that both reports describe versions
of the same release. The
[curator workflow](docs/curator_workflow.md) explains the checklist fields and
the checks that still need a format-aware tool.

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
[docs/report_schema.md](docs/report_schema.md). The private review workflow is in
[docs/curator_workflow.md](docs/curator_workflow.md). Public and real-reader
checks are recorded in [docs/v0.2_calibration.md](docs/v0.2_calibration.md). A separate
[50-dataset OpenNeuro calibration](docs/public_50_dataset_calibration.md) covers
EEG, MEG, iEEG, MRI and fMRI.

The [labelled leak benchmark](docs/privacy_benchmark.md) keeps failed first runs
alongside corrected regression results instead of replacing them. Its separate
public-format layer checks hash-pinned EEGLAB, KIT and EGI MFF fixtures, with no
claim of privacy ground truth.

The separate [report usability pilot](usability/README.md) tests whether an
independent curator can understand the release decision, locate the file and
field, choose a safe next step, notice a coverage gap and treat an integrity
failure correctly. It does not repeat the leak-detection benchmark.

## Status

The private v0.1 snapshot was independently reviewed before it was merged.

The v0.2 work adds complete release inventory, NIfTI and DICOM metadata checks,
archive and cross-file reference checks, stronger integrity checks, an offline
HTML report and calibration on 50 public OpenNeuro datasets. Each frozen
candidate is independently checked before it can be merged.

The project remains private. There is no public release or PyPI package.

## License

MIT
