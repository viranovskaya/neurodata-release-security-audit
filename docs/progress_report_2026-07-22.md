# Progress report — expanded leak coverage

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

## Cross-check result

- 54 unit tests pass on Python 3.10 and 3.13.
- Every new personal value used in tests is absent from JSON and Markdown reports.
- A standard `participant_id` value remains clean.
- A public URL and a placeholder password remain clean.
- Six public EEG BIDS examples were rerun.
- Four real Sleep-EDF files still produce `0 high / 12 review` findings.
- A clean package install and two identical installed-command demo runs pass.

The public calibration found useful new review items: BIDS acquisition times, two local MATLAB paths and a `Thumbs.db` file. It did not create a new high-severity finding.

## Still in progress

- Add format-specific readers for FIF, EEGLAB `.set` and EGI MFF as a separate phase.
- Repeat the full package-archive check after the format phase.

External review is postponed until these local tasks are complete.
