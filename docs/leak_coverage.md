# Coverage matrix

This matrix separates implemented checks from explicit review boundaries.

## Personal and operational metadata

| Area | Examples | v0.2 status |
|---|---|---|
| Direct contacts | email, labelled phone | detected and masked |
| Participant names | structured fields, format headers, private term list | detected and masked |
| Birth dates | text, tables, EEG, NIfTI free text and DICOM | detected and masked |
| Direct IDs | medical, national, passport, tax and insurance fields | detected and masked |
| Linked source IDs | hospital, legacy, accession and study identifiers | review finding |
| Postal addresses | structured, labelled and DICOM fields | detected and masked |
| Exact dates | BIDS, BrainVision, EDF/BDF, DICOM | review finding |
| Staff and site data | operator, experimenter, institution, department | review finding |
| Device identifiers | scanner serial, station, acquisition system ID | review finding |
| Free text | comments, history, descriptions and protocol fields | review finding plus pattern checks |
| Demographic combinations | age, sex and group uniqueness | outside scope; use a disclosure-risk tool |
| Signal or image identity | EEG biometrics, faces, anatomy | outside scope |

## Technical leakage

| Area | Examples | v0.2 status |
|---|---|---|
| Local and network paths | home directories, mounts and UNC shares | detected and masked |
| Host and account data | workstation, IP, MAC and login | review finding |
| Credentials | tokens, keys, passwords and authenticated URLs | detected and masked |
| Source files | Python, MATLAB, shell, notebooks and configuration | bounded text inspection |
| Release remnants | backups, editor files, OS metadata and participant keys | visible finding |
| Development directories | Git, environments, caches and IDE folders | every descendant inventoried; content not parsed |
| Symlinks | internal, external, broken and looping | classified and never followed |
| Cross-file links | BrainVision, EEGLAB and selected BIDS fields | internal target resolution |
| Filename collisions | repeated and case-colliding names | information or review finding |

## Format coverage

| Format | What is read | Payload boundary |
|---|---|---|
| JSON, TSV, CSV, XML and text | complete bounded file | oversized text is manual review |
| BrainVision | header and marker text plus references | `.eeg` samples not interpreted |
| EDF/BDF | common 256-byte header | samples not interpreted |
| FIF | `Info` through MNE | preload forbidden |
| EEGLAB | safe MATLAB text fields and continuous metadata | unsupported nested layouts fail visibly |
| EGI MFF | MNE metadata plus bounded XML | preload forbidden |
| NIfTI | selected header text fields | no voxel request; extensions not interpreted |
| DICOM | file metadata and elements before Pixel Data | no pixels; later elements not read |
| ZIP/TAR | member directory or header table | no extraction or member-payload reads |
| RAR, 7z, `.tar.zst`, plain gzip | file inventory and hash only | manual review |
| Unknown formats | path, type, size and SHA-256 | manual review |

## Integrity and report safety

| Check | v0.2 status |
|---|---|
| Every encountered entry has one coverage record | implemented |
| Every readable regular file has a SHA-256 manifest entry | implemented |
| Files are rehashed after metadata inspection | implemented |
| Added, removed or type-changed entries are detected | implemented |
| Archive members are listed without extraction | implemented for ZIP and TAR |
| Sensitive evidence is masked | implemented for supported patterns and private terms |
| Arbitrary unidentified text in filenames is guaranteed safe | not claimed |
| Report is automatically safe to publish | not claimed |

## Gate before external review

- every implemented branch has a positive, clean and failure-path test;
- no seeded personal value appears in JSON or Markdown;
- source hashes and release-tree state are unchanged;
- base, EEG-format and imaging installs pass the full suite;
- public calibration remains explainable;
- schema, documentation and code describe the same boundary;
- the exact local candidate is frozen and hashed.
