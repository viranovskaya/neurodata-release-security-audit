# Progress report — expanded leak and format coverage

Date: 22 July 2026

## Work completed in this batch

- Added BIDS `acq_time` and common acquisition-date aliases.
- Added structured and labelled medical, national, passport and insurance identifiers.
- Added participant postal-address checks.
- Added review findings for original, hospital, legacy, genetic and source IDs without treating normal BIDS `participant_id` as a leak.
- Added UNC and mounted-volume paths, hostnames, IPv4 addresses, MAC addresses and local account names.
- Added password/API-key assignments and credential-bearing database URLs.
- Added bounded scanning for common source, config and notebook files.
- Added visible findings for sensitive config names, private-key files, OS metadata and editor remnants.
- Added masking for phone numbers, direct IDs and token-shaped values that appear in filenames.
- Added optional metadata-only readers for FIF, continuous EEGLAB `.set` and EGI MFF.
- Added separate EEGLAB checks for subject labels, source filenames, saved paths, comments and history.
- Added bounded XML field checks for participant names, IDs, dates, staff and device identifiers.
- Added visible gaps for missing readers, unsafe XML declarations and legacy nested EEGLAB structures.

## Cross-check result

- 68 unit tests pass on Python 3.10 and 3.13.
- Every new personal value used in tests is absent from JSON and Markdown reports.
- A standard `participant_id` value remains clean.
- A public URL and a placeholder password remain clean.
- Six public EEG BIDS examples were rerun.
- Four real Sleep-EDF files still produce `0 high / 12 review` findings.
- A clean package install and two identical installed-command demo runs pass.
- Small real-format FIF and EEGLAB files were read with the optional MNE 1.12.1 integration; both external `.fdt` and embedded continuous `.set` layouts stayed at `preload=False`.
- The real-format reports mask seeded names, source IDs, staff names, device identifiers, local paths and email addresses.

The public calibration found useful new review items: BIDS acquisition times, two local MATLAB paths and a `Thumbs.db` file. It did not create a new high-severity finding.

## Local gate result

- The final wheel was built twice and both files had the same SHA-256 hash.
- The wheel passed all 68 tests after clean installation on Python 3.10 and 3.13.
- The installed reviewer demo was deterministic on both Python versions and produced the documented `5 / 2 / 6 / 4 / 0` summary.
- The installed package passed the real-format FIF and EEGLAB check with MNE 1.12.1.
- The source tree was checked for private local values and automated-writing markers.

The exact results are in `final_local_gate_2026-07-22.md`. External review has not started yet.
