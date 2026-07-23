# Public format fixture checks

These checks confirm reader execution and coverage on hash-pinned public files. They do not provide privacy ground truth.

- Fixtures: 3
- Passed: 3
- Failed: 0
- Unscored formats: 0

| Fixture | Dataset | Format | Coverage | Finding codes | Result |
|---|---|---|---|---|---|
| openneuro-ds004745-eeglab | ds004745 | EEGLAB SET | header_or_structure_only | FREE_TEXT_METADATA, LINKED_SOURCE_ID | pass |
| openneuro-ds004738-kit | ds004738 | KIT/Yokogawa CON | header_or_structure_only | EXACT_RECORDING_DATE, FREE_TEXT_METADATA | pass |
| mne-testing-data-egi-mff | mne-testing-data | EGI MFF | fully_inspected_metadata | EXACT_RECORDING_DATE, LINKED_SOURCE_ID, LOCAL_PATH, MALFORMED_XML | pass |
