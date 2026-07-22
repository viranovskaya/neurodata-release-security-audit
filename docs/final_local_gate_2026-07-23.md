# Final local gate

Date: 23 July 2026

Version checked: `0.1.0.dev0`

This gate checks the private v0.1 candidate before an independent reviewer receives it. It is not an external validation or a claim that the scanner proves anonymity.

## Result

The local gate passed.

| Check | Result |
|---|---|
| Unit tests | 90 passed on Python 3.10 and 3.13 after installing the wheel in clean environments |
| Wheel reproducibility | two clean builds were byte-identical |
| Wheel SHA-256 | `7638781dc23a0cdb2adae52263550ca9f7c27c2e822dd3ed2ba5c39af16029c0` |
| Reviewer demo | repeated installed runs produced `5 inspected / 2 skipped / 6 high / 4 review / 0 info` |
| Report reproducibility | JSON and Markdown reports were identical across repeated runs and both Python versions |
| Real format integration | FIF and two continuous EEGLAB layouts passed with MNE 1.12.1 |
| Real MFF integration | official MNE `test_egi.mff` passed with `preload=False` and unchanged source hashes |
| EEGLAB safety boundaries | nested MATLAB, MATLAB 7.3 and escaping data-reference fixtures stopped before the MNE reader |
| Source integrity | all real-format fixture hashes were unchanged after scanning |
| Public calibration | all six BIDS example summaries matched the documented counts |
| Real EDF calibration | four Sleep-EDF headers remained at `0 high / 12 review` |
| Finding branch coverage | every emitted finding code has an explicit test path |
| Report path safety | seeded identifiers, dates, credentials and detected machine paths are absent from reports |
| Repository hygiene | no private Daria contact values, local project paths, complete synthetic credentials or automated-writing markers were found in tracked files |

## Real-format result

The installed wheel inspected one FIF file, one EEGLAB file with an external `.fdt` payload and one EEGLAB file with embedded continuous data.

```text
inspected=3 skipped=1 high=5 review=16 info=0
```

The `.fdt` signal payload was listed as skipped. FIF and EEGLAB metadata were
inspected with signal preloading disabled. Seeded names, dates of birth, source IDs,
staff names, device identifiers, local paths and email addresses were absent from the
generated reports. The four additional review findings come from checking both EEGLAB
comments and history fields in each layout.

## Format integration and remaining boundary

The complete MFF path was checked with the official MNE testing fixture. This run exposed a missing optional dependency: MNE requires `defusedxml` to read MFF XML. The `formats` extra now installs it explicitly.

After the XML field-label fix, the MFF scan produced `11 inspected / 5 skipped / 0 high / 6 review / 0 info`. The populated patient ID remained visible as a review finding, while empty name fields and their labels were not reported as participant names.

Legacy EEGLAB files that keep metadata and signal inside one nested MATLAB structure remain a visible coverage limit. The scanner reports the gap rather than loading the full structure or labelling it clean.

A separate boundary run used nested MATLAB, MATLAB 7.3 and external-reference fixtures. All four files were reported as partially inspected and skipped for the full MNE pass. The source hashes stayed unchanged and no external reference was followed.

The final personal and technical leak pass added case-insensitive release remnants,
private configuration directories, more direct-ID and credential aliases, empty
directory checks and safer report locations. Six public BIDS example summaries and
the four Sleep-EDF header results stayed unchanged after these rules were added.

## Next gate

Prepare a fresh private review package and ask one independent EEG researcher or data manager to run the documented synthetic demo. Do not make the repository public or publish a release before that feedback is reviewed.
