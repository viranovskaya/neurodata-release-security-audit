# Final local gate

Date: 22 July 2026

Version checked: `0.1.0.dev0`

This gate checks the private v0.1 candidate before an independent reviewer receives it. It is not an external validation or a claim that the scanner proves anonymity.

## Result

The local gate passed.

| Check | Result |
|---|---|
| Unit tests | 68 passed on Python 3.10 and 3.13 after installing the wheel in clean environments |
| Wheel reproducibility | two clean builds were byte-identical |
| Wheel SHA-256 | `63004791b55f4017182d27524b2c2c5e267a321f97aa0246d3dbe128cdbb06bc` |
| Reviewer demo | repeated installed runs produced `5 inspected / 2 skipped / 6 high / 4 review / 0 info` |
| Report reproducibility | JSON and Markdown reports were identical across repeated runs and both Python versions |
| Real format integration | FIF and two continuous EEGLAB layouts passed with MNE 1.12.1 |
| EEGLAB safety boundaries | nested MATLAB, MATLAB 7.3 and escaping data-reference fixtures stopped before the MNE reader |
| Source integrity | all real-format fixture hashes were unchanged after scanning |
| Public calibration | all six BIDS example summaries matched the documented counts |
| Real EDF calibration | four Sleep-EDF headers remained at `0 high / 12 review` |
| Repository hygiene | no private Daria contact values, local project paths or automated-writing markers were found in tracked files |

## Real-format result

The installed wheel inspected one FIF file, one EEGLAB file with an external `.fdt` payload and one EEGLAB file with embedded continuous data.

```text
inspected=3 skipped=1 high=5 review=12 info=0
```

The `.fdt` signal payload was listed as skipped. FIF and EEGLAB metadata were inspected with signal preloading disabled. Seeded names, dates of birth, source IDs, staff names, device identifiers, local paths and email addresses were absent from the generated reports.

## Remaining boundary

A complete small EGI MFF recording was not available for the same real-file integration run. The MFF reader call and preload guard are covered by a controlled test, while bounded MFF XML fields are covered by synthetic fixtures. A reviewer with an MFF dataset should therefore treat full-recording MFF support as a specific validation question.

Legacy EEGLAB files that keep metadata and signal inside one nested MATLAB structure remain a visible coverage limit. The scanner reports the gap rather than loading the full structure or labelling it clean.

A separate boundary run used nested MATLAB, MATLAB 7.3 and external-reference fixtures. All four files were reported as partially inspected and skipped for the full MNE pass. The source hashes stayed unchanged and no external reference was followed.

## Next gate

Prepare a fresh private review package and ask one independent EEG researcher or data manager to run the documented synthetic demo. Do not make the repository public or publish a release before that feedback is reviewed.
