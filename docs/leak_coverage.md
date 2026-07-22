# Leak coverage plan

This matrix keeps the project scope concrete. A checked item has a detector, masking test and clean counterexample. A pending item is not part of the current claims yet.

## Personal data

| Area | Examples | Status |
|---|---|---|
| Direct contact details | email, labelled phone | implemented |
| Participant names | structured name fields, EDF patient name, private term list | implemented |
| Birth dates | text, JSON, tables and EDF patient field | implemented |
| Direct personal identifiers | medical record, national, passport and insurance numbers | implemented |
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
| Credentials | common tokens, bearer strings and private-key blocks | implemented |
| Network locations | UNC paths, mounted volumes, hostnames and IP addresses | implemented |
| Config credentials | password, API key and connection-string assignments | implemented |
| Source and config files | Python, MATLAB, shell, YAML, TOML, INI and notebooks | implemented |
| Secret-bearing files | `.env`, credential files, private keys and certificate bundles | implemented |
| OS and editor remnants | `.DS_Store`, `Thumbs.db`, swap and patch files | implemented |
| Development directories | `.git`, virtual environments and caches | implemented as visible skipped entries |
| Archives and backups | ZIP, 7z, RAR, `.bak`, `.old` and temporary exports | implemented as review findings |
| Symlinks and unreadable entries | internal, external, broken and inaccessible paths | implemented without following targets |

## Format boundary

The current readers cover BIDS text metadata, BrainVision and EDF/BDF common headers. FIF, EEGLAB `.set` and EGI MFF need separate readers and fixtures. They will be added only after the text and release-tree coverage above passes calibration.

## Gate before external review

- every implemented rule has a positive test, a masking assertion and a clean counterexample;
- reports contain no complete seeded value;
- supported source files are unchanged;
- public BIDS examples and real EEG files are recalibrated after each batch;
- unsupported formats and directories remain visible instead of looking clean.
