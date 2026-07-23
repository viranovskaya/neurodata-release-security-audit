# MVP test matrix

All identifiers below are synthetic.

| Area | Fixture | Expected result |
|---|---|---|
| Clean BIDS text | minimal `dataset_description.json` and README | no high finding |
| Structured JSON | populated date of birth, phone, participant name and recording date | field-specific findings; values masked |
| BIDS-style JSON keys | CamelCase date, phone, patient-name and acquisition-time fields | field-specific findings; values masked |
| Common name aliases | given name, family name, forename and surname fields | participant-name findings; values masked |
| Additional direct IDs | driving-licence, tax, insurance and personal-number fields | `DIRECT_PERSONAL_ID`; values masked |
| Nested JSON participant name | `participant.fullName` plus author and dataset names | participant name reported; author and dataset names ignored |
| Untrusted structured key | private text in a JSON key, XML tag or nested MNE mapping key | stable field placeholder; private key absent from report location |
| Participants table | populated `date_of_birth`, `name` and `phone` columns | field-specific findings; values masked |
| Ordinary BIDS name | dataset `Name` in `dataset_description.json` | no participant-name finding |
| Author full name | `full_name` inside author metadata | no participant-name finding |
| Known name in text | value appears in a private term list | `KNOWN_IDENTIFIER`; value masked |
| Known ID in filename | value appears in a private term list | `KNOWN_IDENTIFIER`; report path masked |
| Known EDF subject code | alphanumeric code appears in a private term list | `KNOWN_IDENTIFIER`; value masked |
| Known name inside an ordinary word | `Ann` in `annotations` | no finding |
| Multiple known IDs in paths | two different private IDs | distinct masked report paths |
| Repeated known term | same value with different letter case | one private-list entry |
| Direct email | email in a text sidecar | `DIRECT_EMAIL`; full email absent from reports |
| Email in filename | filename is an email address | `DIRECT_EMAIL`; report path masked |
| Labelled phone | `Phone: +1 202 555 0199` | `DIRECT_PHONE`; number masked |
| Direct personal ID | medical record or national identifier field | `DIRECT_PERSONAL_ID`; value masked |
| Participant address | structured or labelled address | `POSTAL_ADDRESS_FIELD`; value masked |
| Linked source ID | original, hospital, legacy or genetic ID | `LINKED_SOURCE_ID`; value masked |
| Standard BIDS participant ID | `participant_id` with `sub-01` | no source-ID finding |
| BIDS acquisition time | `acq_time` in `*_scans.tsv` | `EXACT_RECORDING_DATE`; value masked |
| Local path | macOS, Linux and Windows home paths | `LOCAL_PATH`; path value masked |
| Network and mounted paths | UNC share and `/mnt/...` path | `NETWORK_PATH`; value masked |
| Host and account details | hostname, IP, MAC and username | review findings; values masked |
| Secret | GitHub-token-shaped synthetic string | `POTENTIAL_SECRET`; token masked |
| Config secret | password assignment and database URL | `POTENTIAL_SECRET`; values masked |
| Common service secret | GitLab, Slack, Google-key, `sk-`, JWT and authenticated-URL shapes | `POTENTIAL_SECRET`; values masked |
| Short token example | deliberately short documentation placeholders | no secret finding |
| Source and notebook text | Python path and notebook host value | files inspected; findings masked |
| Sensitive filename | phone, personal ID or token in a path | finding path masked |
| Date in release path | labelled birth date or recording date | field-specific finding; report path masked |
| Local path inside release path | nested `/Users/...` sequence | `LOCAL_PATH`; report path masked |
| Empty sensitive directory | known identifier or participant-key phrase with no files | finding is still reported; path masked |
| BrainVision date | `New Segment` marker with full timestamp | `EXACT_RECORDING_DATE` |
| Clean BrainVision | header and marker files without identifying fields | no high finding |
| BrainVision source name | released header references an old recording basename | `SOURCE_FILENAME`; source name masked |
| EDF patient name | populated EDF+ patient-name position | `SUBJECT_NAME_FIELD` |
| EDF alphanumeric subject code | pseudocode in the EDF+ patient-name position | general field review, not a name finding |
| EDF birth date | populated EDF+ birth-date position | `BIRTH_DATE_FIELD` |
| EDF recording date | non-placeholder start date | `EXACT_RECORDING_DATE` |
| Clean EDF | placeholder patient/recording fields and anonymised date | no high finding |
| Participant key | `participant_name_key.xlsx` | `SUBJECT_KEY_FILE` |
| Unexpected backup | `.bak`, `.old`, `.zip` or temporary export | `UNEXPECTED_FILE` |
| Archive and editor remnants | TAR archive, patch, workspace or editor-backup name | `UNEXPECTED_FILE`; bounded text still inspected |
| Development directory | version-control, environment, editor or cache directory in the release tree | `UNEXPECTED_DIRECTORY`; directory listed as skipped |
| Case-variant remnant | `.ENV` and `.GIT` | same result as lowercase names |
| Sensitive config file | `.env`, credential JSON or private-key filename | `SENSITIVE_CONFIG_FILE` |
| Sensitive config directory | `.ssh`, `.aws`, `.kube` or similar directory | visible review finding; bounded child text is scanned |
| Ordinary release paths | `.github`, `participants.tsv` and empty `recording.fif.gz` | no archive, development-directory, subject-key or private-config finding |
| OS metadata | `.DS_Store`, `Thumbs.db` or `desktop.ini` | `OS_METADATA_FILE` |
| External symlink | symlink points outside dataset root | `EXTERNAL_SYMLINK`; target not followed |
| Internal symlink | symlink points to another release file | `SYMLINK_REVIEW`; target not followed through the link |
| Symlink loop | symlink resolves to itself | `UNRESOLVED_SYMLINK`; scan continues |
| Oversized text | text exceeds configured byte limit | `TEXT_FILE_TOO_LARGE`; file listed as skipped |
| Malformed EDF | shorter than the common 256-byte header | `MALFORMED_HEADER`; scan continues |
| Malformed JSON | invalid JSON sidecar | `MALFORMED_JSON`; scan continues |
| Malformed table | delimited-table reader fails | `MALFORMED_TABLE`; private error text is not reported |
| EDF/BDF Git LFS pointer | repository contains a pointer instead of the payload | informational finding, not `MALFORMED_HEADER` |
| Empty EDF/BDF fixture | public example repository contains a zero-byte placeholder | informational finding, not `MALFORMED_HEADER` |
| FIF personal metadata | names, birthday, source ID, measurement date and experimenter in `Info` | field-specific findings; values masked |
| FIF device metadata | device serial and site in `Info` | `DEVICE_IDENTIFIER`; values masked |
| FIF acquisition identifiers | non-zero `file_id`, `meas_id`, processing GUID and project fields | review findings; values masked |
| Format free text | MNE description and EEGLAB comments/history | `FREE_TEXT_METADATA` plus clear pattern findings |
| EEGLAB top-level metadata | subject, source filename, filepath and comments | source ID, filename, path and contact findings; values masked |
| EEGLAB signal handling | continuous embedded and external `.fdt` layouts | MNE reader called with `preload=False`; preloaded result fails visibly |
| Legacy nested EEGLAB | one `EEG` or `ALLEEG` MATLAB variable | `EEGLAB_METADATA_COVERAGE_LIMIT`; signal structure not loaded |
| External EEGLAB data reference | `.set` points to an absolute or escaping `.fdt` path | visible finding; MNE reader is not called |
| Missing EEGLAB text reader | main MNE reader works but safe MATLAB text reader is missing | visible `EEGLAB_METADATA_READER_UNAVAILABLE` finding |
| EEGLAB metadata failure | safe MATLAB metadata pass raises an error | visible `EEGLAB_METADATA_UNREADABLE`; private error text is not reported |
| Optional format failure | FIF, SET or MFF metadata reader raises an error | visible `FORMAT_METADATA_UNREADABLE`; private error text is not reported |
| MFF recording | optional MNE reader plus bounded XML files | reader uses `preload=False`; XML remains independently inspected |
| MFF personal XML | subject name, ID, date, operator and device serial | field-specific findings; values masked |
| MFF dynamic patient field | `<name>` contains a field label and `<data>` its value | classify the paired value; do not report the label as a participant name |
| MFF format dependency | optional `formats` installation | `defusedxml` is declared for MNE's MFF XML reader |
| XML document type or entity | bounded XML contains a declaration that can expand content | `UNSAFE_XML_DECLARATION`; document not parsed |
| Optional format placeholder | empty file or Git LFS pointer | informational coverage note without importing MNE |
| Unreadable directory | one nested directory raises a read error | visible review finding; other files still scanned |
| Unreadable filesystem entry | entry type cannot be classified | visible `UNREADABLE_ENTRY`; other files still scanned |
| Unreadable file | one text file raises a read error | `UNREADABLE_FILE`; other files still scanned |
| Determinism | scan same tree twice | identical JSON |
| Source integrity | hash fixtures before and after scan | unchanged |
| Offline operation | scan with network unavailable | identical result |
| Report write failure | output path cannot be written | concise error and exit status `2`; no traceback |
| Report inside dataset | output path is within the audited tree | rejected before scanning or writing |
| Private term list inside dataset | identifier list is within the audited tree | rejected before scanning |
