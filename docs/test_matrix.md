# MVP test matrix

All identifiers below are synthetic.

| Area | Fixture | Expected result |
|---|---|---|
| Clean BIDS text | minimal `dataset_description.json` and README | no high finding |
| Structured JSON | populated date of birth, phone, participant name and recording date | field-specific findings; values masked |
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
| Local path | macOS, Linux and Windows home paths | `LOCAL_PATH`; path value masked |
| Secret | GitHub-token-shaped synthetic string | `POTENTIAL_SECRET`; token masked |
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
| External symlink | symlink points outside dataset root | `EXTERNAL_SYMLINK`; target not followed |
| Symlink loop | symlink resolves to itself | `UNRESOLVED_SYMLINK`; scan continues |
| Oversized text | text exceeds configured byte limit | `TEXT_FILE_TOO_LARGE`; file listed as skipped |
| Malformed EDF | shorter than the common 256-byte header | `MALFORMED_HEADER`; scan continues |
| Malformed JSON | invalid JSON sidecar | `MALFORMED_JSON`; scan continues |
| EDF/BDF Git LFS pointer | repository contains a pointer instead of the payload | informational finding, not `MALFORMED_HEADER` |
| Empty EDF/BDF fixture | public example repository contains a zero-byte placeholder | informational finding, not `MALFORMED_HEADER` |
| Unreadable directory | one nested directory raises a read error | visible review finding; other files still scanned |
| Unreadable file | one text file raises a read error | `UNREADABLE_FILE`; other files still scanned |
| Determinism | scan same tree twice | identical JSON |
| Source integrity | hash fixtures before and after scan | unchanged |
| Offline operation | scan with network unavailable | identical result |
| Report write failure | output path cannot be written | concise error and exit status `2`; no traceback |
