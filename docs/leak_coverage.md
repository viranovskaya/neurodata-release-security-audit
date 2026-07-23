# Leak coverage plan

This matrix keeps the project scope concrete. A checked item has a detector, masking test and clean counterexample. A pending item is not part of the current claims yet.

## Personal data

| Area | Examples | Status |
|---|---|---|
| Direct contact details | email, labelled phone | implemented |
| Participant names | structured name fields, EDF patient name, private term list | implemented |
| Birth dates | text, JSON, tables and EDF patient field | implemented |
| Direct personal identifiers | medical record, national, passport, driving-licence, tax and insurance numbers | implemented |
| Postal addresses | participant address fields and labelled text | implemented |
| Linked source identifiers | original, hospital, legacy, genetic and source IDs | implemented as review findings |
| Exact acquisition dates | BIDS `acq_time`, JSON, BrainVision and EDF/BDF | implemented as review findings |
| Quasi-identifiers in participant tables | age, sex, group combinations | delegated to metaprivBIDS; outside this tool |
| Signal-based re-identification | biometric information in EEG samples | outside the current threat model |

## Technical data

| Area | Examples | Status |
|---|---|---|
| Local user paths | macOS, Linux and Windows home paths | implemented |
| Source recording names | BrainVision references to old basenames | implemented |
| External format references | EEGLAB signal path leaves the selected release directory | implemented as a review finding; reference is not followed |
| Credentials | common service tokens, bearer and JWT strings, private-key blocks and authenticated URLs | implemented |
| Network locations | UNC paths, mounted volumes, hostnames and IP addresses | implemented |
| Acquisition-system traces | FIF machine IDs, original GUIDs, project IDs and device serials | implemented as review findings |
| Format free text | FIF descriptions and EEGLAB comments/history | implemented as manual-review findings plus pattern checks |
| Config credentials | password, API key and connection-string assignments | implemented |
| Source and config files | Python, MATLAB, shell, YAML, TOML, INI and notebooks | implemented |
| Secret-bearing files | `.env`, credential files, private keys and certificate bundles | implemented |
| Private configuration directories | `.ssh`, `.aws`, `.kube` and similar paths | implemented as visible review findings; bounded text inside is still scanned |
| OS and editor remnants | `.DS_Store`, `Thumbs.db`, swap, patch and workspace files | implemented |
| Development directories | version-control folders, virtual environments, editor folders and caches | implemented as visible skipped entries, case-insensitively |
| Archives and backups | ZIP, TAR, 7z, RAR, `.bak`, `.old` and temporary exports | implemented as review findings |
| Symlinks and unreadable entries | internal, external, broken and inaccessible paths | implemented without following targets |
| Report path safety | known identifiers, contacts, dates, credentials and detected local or network paths | implemented; arbitrary unmatched filenames remain a documented manual-review boundary |
| Report location safety | untrusted JSON, table, XML and nested metadata keys | replaced with stable field placeholders |

## Format boundary

The current readers cover BIDS text metadata, BrainVision, EDF/BDF common headers, FIF `Info`, continuous EEGLAB `.set` metadata and EGI MFF recording metadata. FIF, EEGLAB and MFF use the optional `formats` installation because they depend on MNE. MFF XML is still checked as bounded text when that extra is not installed.

EEGLAB top-level MATLAB metadata and MATLAB 7.3 text fields are checked without selecting the signal array. A legacy file that stores everything inside one nested `EEG` or `ALLEEG` variable receives `EEGLAB_METADATA_COVERAGE_LIMIT`; the MNE reader is not called for that file. MATLAB 7.3 files stay on the same conservative text-only path. An absolute or escaping external data reference receives `EXTERNAL_DATA_REFERENCE` and also stops the MNE reader. Epoched EEGLAB data have the same safe limitation if a metadata-only reader is not available.

## Gate before external review

- every implemented rule has a positive test, a masking assertion and a clean counterexample;
- every finding code has an explicit test path, including reader and filesystem failures;
- reports contain no complete seeded value;
- supported source files are unchanged;
- public BIDS examples and real EEG files are recalibrated after each batch;
- unsupported formats and directories remain visible instead of looking clean.
