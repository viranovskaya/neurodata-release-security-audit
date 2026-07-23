# Public format fixture checks

These checks confirm reader execution and coverage on hash-pinned public files. They do not provide privacy ground truth.

- Fixtures: 2
- Passed: 2
- Failed: 0
- Unscored formats: 1

| Fixture | Dataset | Format | Coverage | Finding codes | Result |
|---|---|---|---|---|---|
| openneuro-ds004745-eeglab | ds004745 | EEGLAB SET | header_or_structure_only | FREE_TEXT_METADATA, LINKED_SOURCE_ID | pass |
| openneuro-ds004738-kit | ds004738 | KIT/Yokogawa CON | header_or_structure_only | EXACT_RECORDING_DATE, FREE_TEXT_METADATA | pass |

## Unscored formats

- **EGI MFF** — No independent hash-pinned MFF fixture is included in this package.
