# Safe remediation by format

The report points to a file and field, but it does not rewrite research data.
Make each correction in a private working copy and keep the original unchanged.

For every format:

1. confirm that the report passed both integrity rechecks;
2. open the named file with a tool that understands the format;
3. change only the field that was reviewed and save to a new file or directory;
4. rerun the audit on the complete candidate;
5. compare the scientific content and acquisition metadata with the original;
6. record the decision and the tool version used.

Do not edit a binary file with a text or hex editor. Do not treat a changed hash
as an error by itself: a corrected file should have a new hash. The important
checks are that the intended field changed, the scientific data did not change
unexpectedly and the new audit passes.

## FIF

Use MNE-Python or another FIF-aware tool. Inspect the exact entry under
`raw.info`, such as `subject_info`, `meas_date`, `device_info` or
`experimenter`, and write a new FIF file.

Before replacing the candidate, compare:

- channel names, types and order;
- sampling frequency and number of samples;
- first and last sample;
- annotations and their onset, duration and description;
- bad-channel list, projectors and digitisation points;
- measurement date and any subject or device fields you meant to keep.

Saving may rewrite internal FIF structure, so byte equality with the original is
not expected.

## EEGLAB

Use EEGLAB in MATLAB for `.set` files unless the dataset has a tested
MNE-Python round trip. Review fields such as `EEG.subject`, `EEG.comments`,
`EEG.etc`, channel metadata and event metadata. If the `.set` points to an
external `.fdt`, keep the pair together and verify the reference after saving.

Compare `nbchan`, `pnts`, `trials`, `srate`, channel locations, event count,
event types and event latencies. Confirm that the data-storage mode did not
change unexpectedly.

## EDF and BDF

Use an EDF/BDF-aware editor or library. Common fields needing review include
patient identification, recording identification, technician details and the
exact start date. Write a new file; do not patch fixed-width header bytes by
hand.

Compare:

- number and order of signals;
- label, unit and sampling rate for every signal;
- physical and digital min/max values;
- record duration, number of records and total samples;
- EDF+ or BDF+ annotations;
- start time if it was not intentionally changed.

Some writers rescale or quantise samples. Test the chosen round trip on a copy
before using it for a release.

## EGI MFF

Treat an MFF recording as one directory-format object. Use EGI/Net Station
export tools or a tested format-aware workflow. The XML files inside the
directory can contain subject, operator, device and exact-time metadata, but
deleting or renaming one XML file by hand can break the recording.

After re-export, compare channel count, sampling rate, duration, event timing
and labels, sensor layout and all files required by the directory structure.
Run the audit on the MFF directory inside the complete release candidate.

## DICOM

DICOM de-identification needs a project policy and a DICOM-aware tool. Review
standard identity fields, dates, UIDs, free text, institution and device fields,
private tags and linked objects. Preserve required relationships when UIDs are
replaced.

This scanner stops before Pixel Data. It does not detect burned-in text or
faces. Use a separate clinical imaging workflow for pixel inspection,
de-facing, OCR and private-tag policy. Validate the corrected series with a
DICOM viewer and compare modality, dimensions, spacing, orientation, slice
order and series membership.

## NIfTI

Use nibabel or another NIfTI-aware tool for header fields and extensions. Review
`descrip`, `aux_file`, intent metadata and extension blocks. A NIfTI header
change does not remove identifiable anatomy from voxel data.

If defacing is required, use a separate validated defacing workflow and perform
visual quality control. Compare shape, dtype, voxel sizes, affine, orientation,
time points, scaling and extensions before accepting the result.

## JSON and TSV

Edit JSON and TSV on a private copy with a schema-aware editor or script.
Change the exact field named by the report. Do not remove required BIDS keys or
columns just because one cell needs correction.

Check that:

- JSON still parses and keeps the intended key types;
- TSV keeps tab delimiters, column order and row count;
- missing values keep their intended representation;
- participant and file references still resolve;
- the BIDS Validator passes when the dataset is BIDS.

## Final release check

Run the audit again on the whole candidate, not only the edited file. A
candidate is not ready while either integrity recheck fails, any high-priority
finding remains, or an unsupported entry still lacks a documented manual
decision.

The audit does not certify anonymity, GDPR or HIPAA compliance, ethical
sufficiency or scientific validity.
