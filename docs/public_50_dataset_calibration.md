# Public 50-dataset calibration

This calibration checks whether the scanner behaves consistently on varied real
public neurodata rather than only on synthetic fixtures.

## Fixed sample

The sample contains 50 OpenNeuro datasets:

- 24 EEG;
- 8 MEG;
- 5 iEEG;
- 10 fMRI;
- 2 MRI;
- 1 combined EEG and fMRI dataset.

The registry was frozen on 23 July 2026. It was selected to exercise several
modalities and supported file readers; it is not a random or representative
sample of OpenNeuro. All 50 snapshots declare the CC0 licence in
`dataset_description.json`.

Every input is tied to an exact public repository commit. The bounded release
slices contain all regular tracked metadata files. Thirty-nine slices also
contain one real signal or image payload downloaded from the public OpenNeuro
object store and checked against its git-annex digest. Two external EEGLAB
`.fdt` companions were included where the selected `.set` file required them.
The fixed dataset IDs, titles, DOIs, commits and payload status are in
[`openneuro_50_registry.tsv`](openneuro_50_registry.tsv).

Derivatives, sourcedata and stimuli were excluded. The payload ceiling was
80 MiB, with up to 120 MiB allowed for an EEGLAB `.fdt` companion. Broken
git-annex symlinks were not treated as data files.

The final run used Python 3.13.7, MNE 1.12.1, nibabel 5.4.2 and pydicom 3.0.2.
Each slice was scanned with `neurodata-security-audit 0.2.0.dev0`, writing JSON,
Markdown and HTML outside the source tree. The exact payload digests, slice
inventory hashes, commands and redacted per-dataset report hashes are retained
in the private independent-review handoff rather than the repository.

## Result

| Measure | Result |
|---|---:|
| Datasets completed | 50 / 50 |
| Real-payload slices | 39 |
| Metadata-only slices | 11 |
| Release entries | 31,472 |
| Regular files in the integrity manifest | 24,442 |
| Files inspected | 24,434 |
| Deliberately skipped payload or legacy structures | 11 |
| Both integrity rechecks passed | 50 / 50 |
| Datasets without a high-severity finding | 46 |
| Datasets with a high-severity finding | 4 |

The nine high-severity findings were six populated participant-name fields and
three birth-date fields. The report masks the values. Dataset-level mappings are
intentionally withheld: any credible source-specific privacy concern must be
handled privately with the dataset maintainers before it is discussed publicly.
The aggregate results show that the relevant readers and detectors were reached;
they are not a claim that a complete public dataset is unsafe.

## Corrections prompted by the run

The first pass exposed two false-positive patterns and one coverage gap:

- contact emails in public README and citation metadata were being treated like
  undisclosed participant contact data;
- escaped JSON strings such as MRI sequence names were being scanned as raw
  source text and could resemble network paths;
- `.bval`, `.bvec`, `.bidsignore`, `.gitattributes` and KIT `.con` metadata were
  visible in the inventory but not yet parsed.

The corrected pass:

- distinguishes author/public contact emails from participant-contact context;
- scans decoded JSON string values, array items and object keys without
  reproducing sensitive keys in report locations;
- fully inspects the small BIDS text files;
- reads KIT metadata through MNE with `preload=False`.

After these corrections, only eight signal or image payloads and three legacy
EEGLAB structures remained deliberately unparsed. There was no optional-reader
failure in the final run.

## Interpretation limits

This is an engineering robustness and field-sensitivity calibration. It is not:

- a privacy benchmark;
- an anonymity, GDPR, HIPAA or ethics assessment;
- a complete copy of each source dataset;
- evidence that review-level findings are source-dataset defects.

The bounded slices omit many git-annex payloads, so missing-reference findings
mostly reflect the calibration design. Signal samples, image voxels, DICOM
pixels, archive member payloads and external link targets were not loaded.

The redacted aggregate files and browser report are generated outside the
audited dataset trees. Exact payload provenance and report hashes are retained
in the private review handoff. Any code or report change requires a fresh
independent check before merge, release or a public claim.
