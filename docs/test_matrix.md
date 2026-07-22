# MVP test matrix

All identifiers below are synthetic.

| Area | Fixture | Expected result |
|---|---|---|
| Clean BIDS text | minimal `dataset_description.json` and README | no high finding |
| Structured JSON | populated date of birth, phone, participant name and recording date | field-specific findings; values masked |
| Participants table | populated `date_of_birth`, `name` and `phone` columns | field-specific findings; values masked |
| Ordinary BIDS name | dataset `Name` in `dataset_description.json` | no participant-name finding |
| Direct email | email in a text sidecar | `DIRECT_EMAIL`; full email absent from reports |
| Labelled phone | `Phone: +1 202 555 0199` | `DIRECT_PHONE`; number masked |
| Local path | macOS, Linux and Windows home paths | `LOCAL_PATH`; path value masked |
| Secret | GitHub-token-shaped synthetic string | `POTENTIAL_SECRET`; token masked |
| BrainVision date | `New Segment` marker with full timestamp | `EXACT_RECORDING_DATE` |
| Clean BrainVision | header and marker files without identifying fields | no high finding |
| BrainVision source name | released header references an old recording basename | `SOURCE_FILENAME`; source name masked |
| EDF patient name | populated EDF+ patient-name position | `SUBJECT_NAME_FIELD` |
| EDF birth date | populated EDF+ birth-date position | `BIRTH_DATE_FIELD` |
| EDF recording date | non-placeholder start date | `EXACT_RECORDING_DATE` |
| Clean EDF | placeholder patient/recording fields and anonymised date | no high finding |
| Participant key | `participant_name_key.xlsx` | `SUBJECT_KEY_FILE` |
| Unexpected backup | `.bak`, `.old`, `.zip` or temporary export | `UNEXPECTED_FILE` |
| External symlink | symlink points outside dataset root | `EXTERNAL_SYMLINK`; target not followed |
| Symlink loop | symlink resolves to itself | `UNRESOLVED_SYMLINK`; scan continues |
| Oversized text | text exceeds configured byte limit | `TEXT_FILE_TOO_LARGE`; file listed as skipped |
| Malformed EDF | shorter than the common 256-byte header | `MALFORMED_HEADER`; scan continues |
| Unreadable directory | one nested directory raises a read error | visible review finding; other files still scanned |
| Determinism | scan same tree twice | identical JSON |
| Source integrity | hash fixtures before and after scan | unchanged |
| Offline operation | scan with network unavailable | identical result |
