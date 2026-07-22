# NeuroData Release Security Audit

Working title for a local pre-release privacy checker for EEG datasets organised with BIDS.

**Status:** private v0.1 candidate, 22 July 2026. Implemented and tested; not publicly released or independently validated.

## The problem

Researchers can validate a BIDS dataset and anonymise recordings during conversion, but still accidentally publish identifying or operational information elsewhere in the release. Common examples include an original participant name in an EEG header, an exact recording date in a marker file, an email address in a free-text field, a local computer path, or a forgotten participant-key spreadsheet.

The first version answers one narrow question:

> Does this release contain obvious direct identifiers or technical remnants that should be reviewed before it is shared?

It is an independent check after conversion. It does not replace the BIDS Validator, MNE-BIDS anonymisation, metaprivBIDS, or human review.

## Intended user

A researcher or data manager preparing an EEG dataset for:

- a public repository such as OpenNeuro;
- transfer to another research group;
- an institutional archive;
- a supplementary research-software release.

## MVP scope

The tool receives one local dataset directory and scans it without modifying the source files.

### Files inspected

- BIDS `.tsv` and `.json` metadata;
- BrainVision `.vhdr` and `.vmrk` files;
- the fixed header area of EDF and BDF files;
- FIF, continuous EEGLAB `.set` and EGI MFF recording metadata through optional readers;
- bounded XML metadata, including MFF XML files;
- small text, source, config and notebook files;
- filenames and the dataset directory structure;
- unexpected release files such as spreadsheets, backups and temporary exports.

The EEG signal payload is not loaded or analysed.

### Initial finding types

| Code | Example | Initial severity |
|---|---|---|
| `DIRECT_EMAIL` | email address in a sidecar or README | high |
| `DIRECT_PHONE` | phone number in a note or log | high |
| `SUBJECT_NAME_FIELD` | populated patient-name field in EDF | high |
| `BIRTH_DATE_FIELD` | full date of birth in a header or table | high |
| `DIRECT_PERSONAL_ID` | medical record, national or passport identifier | high |
| `POSTAL_ADDRESS_FIELD` | participant home or postal address | high |
| `SUBJECT_KEY_FILE` | participant mapping spreadsheet in the release tree | high |
| `KNOWN_IDENTIFIER` | value from a private project-specific name or ID list | high |
| `LINKED_SOURCE_ID` | source, hospital, legacy or genetic identifier | review |
| `EXACT_RECORDING_DATE` | unshifted BrainVision or EDF acquisition date | review |
| `LOCAL_PATH` | `/Users/name/...` or `C:\Users\name\...` | review |
| `NETWORK_PATH` | UNC share or mounted-volume path | review |
| `LOCAL_HOSTNAME` | acquisition computer or workstation name | review |
| `NETWORK_ADDRESS` | labelled IP address | review |
| `DEVICE_ADDRESS` | labelled MAC or device address | review |
| `ACCOUNT_NAME` | local login or account name | review |
| `SOURCE_FILENAME` | original participant-labelled recording name | review |
| `UNEXPECTED_FILE` | `.xlsx`, `.bak`, temporary export or archive | review |
| `UNEXPECTED_DIRECTORY` | `.git`, `.venv` or cache directory | review |
| `SENSITIVE_CONFIG_FILE` | `.env`, credential file or private-key filename | review |
| `OS_METADATA_FILE` | `.DS_Store`, `Thumbs.db` or `desktop.ini` | review |
| `POTENTIAL_SECRET` | obvious token or credential pattern | high |
| `PERSONNEL_FIELD` | experimenter, operator or technician field | review |
| `DEVICE_IDENTIFIER` | acquisition device serial or site identifier | review |
| `ACQUISITION_SYSTEM_ID` | FIF machine ID or original acquisition GUID | review |
| `PROJECT_IDENTIFIER` | internal project ID or name in format metadata | review |
| `FREE_TEXT_METADATA` | populated description, comments or processing history | review |
| `FORMAT_READER_UNAVAILABLE` | optional reader is not installed | review |
| `EEGLAB_METADATA_READER_UNAVAILABLE` | safe MATLAB text-field reader is not installed | review |
| `EEGLAB_METADATA_COVERAGE_LIMIT` | legacy nested MATLAB structure cannot be separated safely from signal data | review |
| `EXTERNAL_DATA_REFERENCE` | EEGLAB data path points outside the selected release | review |

Rules should prefer structured fields and clear patterns. Generic person-name detection is out of scope for the first version because it would create too many false positives.

## Safety rules

- Local execution only. No dataset content is uploaded.
- Read-only by default. The tool never redacts or rewrites source files.
- Reports never reproduce a complete sensitive value. They show the finding type, file, location and a masked preview.
- The scanner stays inside the directory explicitly supplied by the user.
- Symlinks that point outside the dataset are reported and not followed.
- Large binary files are not read beyond the header bytes required for the check.
- Optional MNE readers are called with signal preloading disabled.
- A reader that returns preloaded signal data produces a visible coverage finding.
- XML document types and entities are rejected before parsing.
- Every skipped or unreadable file is listed in the report.
- Development and cache directories are not traversed, but remain visible as skipped entries.
- A private term list can be supplied for names and old IDs already known to the researcher. Its values are never copied into the report.
- Report files and the private term list must stay outside the dataset being checked.

Relative filenames remain visible so the curator can locate a finding. Matched emails and values from the private term list are masked in paths, but other identifying text may still be present. Reports are working review artifacts and must not be assumed safe to publish unchanged.

The MVP assumes accidental disclosure by an honest dataset curator. Malicious concurrent changes during a scan, encrypted archives, malware and adversarial parser inputs are outside the current threat model.

## Output

The MVP produces:

1. a concise terminal summary;
2. a deterministic JSON report for CI or archiving;
3. an optional Markdown report for manual review.

Each report records:

- scanner version;
- files inspected, skipped and unreadable;
- finding code and severity;
- relative file path and safe location information;
- masked evidence;
- a short explanation and suggested manual check.

The report must say **review required**, not **dataset is anonymous**.

## Explicit non-goals

The project does not:

- certify GDPR, HIPAA or ethics compliance;
- guarantee anonymity or rule out re-identification;
- measure uniqueness in demographic tables;
- assess whether the EEG signal itself can identify a participant;
- remove information automatically;
- scan remote storage, cloud accounts or databases;
- perform malware analysis or penetration testing.

Statistical disclosure risk in `participants.tsv` is already addressed by metaprivBIDS and should remain a separate task.

## Validation plan

The first benchmark uses synthetic data only:

- a clean minimal BIDS/BrainVision dataset;
- the same dataset with one seeded leak per rule;
- an EDF fixture with synthetic patient and recording fields;
- unexpected spreadsheet, backup, log and symlink cases;
- realistic clean strings that should not be flagged.
- boundary-aware matching against a private synthetic name and identifier list.

Acceptance criteria for v0.1:

- every seeded high-risk leak is detected;
- no complete seeded identifier appears in the generated report;
- clean fixtures produce no high-risk findings;
- repeated scans produce identical JSON;
- tests confirm that source files are unchanged;
- the scanner performs no network requests;
- unsupported or malformed files fail safely and remain visible in the report.

Public datasets can be used later for usability testing, not as a source of known leaks. Any credible privacy problem found in a public dataset must be reported privately to its maintainers before details are discussed publicly.

## Relationship to existing tools

| Tool | Relationship |
|---|---|
| BIDS Validator | validates dataset structure; this project checks release-time privacy indicators |
| MNE-BIDS | can anonymise during conversion; this project audits the resulting release |
| metaprivBIDS | measures statistical re-identification risk in tables; this project checks direct and technical leakage |
| BIDSonym | focuses mainly on MRI de-identification and metadata removal |
| EDF de-identification tools | rewrite one format; this project performs a read-only cross-file audit |

## Possible later work

- support for additional EEGLAB MATLAB layouts without loading signal arrays;
- optional metaprivBIDS hand-off for participant-table analysis;
- configurable institutional policies;
- HTML report;
- integration with release CI;
- a benchmark paper or software publication after independent validation.

## Naming

Current working title: **NeuroData Release Security Audit**.

Possible repository name: `neurodata-release-security-audit`.

A private GitHub repository now uses this name. No public release or PyPI project exists yet.
