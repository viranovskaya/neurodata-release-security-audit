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

Every input is tied to an exact public repository commit. The bounded release
slices contain all regular tracked metadata files. Thirty-nine slices also
contain one real signal or image payload downloaded from the public OpenNeuro
object store and checked against its git-annex digest. Two external EEGLAB
`.fdt` companions were included where the selected `.set` file required them.
The fixed dataset IDs, titles, DOIs, commits and redacted run totals are in
[`openneuro_50_results.tsv`](openneuro_50_results.tsv).

Derivatives, sourcedata and stimuli were excluded. Broken git-annex symlinks
were not treated as data files.

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

The nine high-severity findings were limited to populated participant-name and
birth-date fields:

| Dataset | Modality | Field types |
|---|---|---|
| `ds005356` | MEG | two subject-name fields and one birth-date field |
| `ds005398` | iEEG | one subject-name field and one birth-date field |
| `ds005588` | fMRI | two subject-name fields |
| `ds006107` | iEEG | one subject-name field and one birth-date field |

The report masks the field values. These results show that the relevant readers
and detectors were reached; they are not a claim that a complete public dataset
is unsafe.

## Corrections prompted by the run

The first pass exposed two false-positive patterns and one coverage gap:

- contact emails in public README and citation metadata were being treated like
  undisclosed participant contact data;
- escaped JSON strings such as MRI sequence names were being scanned as raw
  source text and could resemble network paths;
- `.bval`, `.bvec`, `.bidsignore`, `.gitattributes` and KIT `.con` metadata were
  visible in the inventory but not yet parsed.

The corrected pass:

- keeps public contact emails as review findings rather than high findings;
- scans decoded JSON string values instead of their escaped representation;
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
audited dataset trees. The exact candidate still requires a new independent
engineering review before any push, merge, release or public claim.
