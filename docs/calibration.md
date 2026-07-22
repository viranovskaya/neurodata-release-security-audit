# Initial public-example calibration

The local MVP was run against six EEG examples from a local checkout of `bids-standard/bids-examples` on 22 July 2026. This is a usability and false-positive check, not a privacy benchmark.

| Example | Inspected | Skipped | High | Review | Info | Main result |
|---|---:|---:|---:|---:|---:|---|
| `eeg_cbm` | 104 | 0 | 0 | 0 | 20 | Empty EDF fixtures reported as informational placeholders |
| `eeg_rishikesh` | 166 | 15 | 0 | 0 | 40 | Empty EDF fixtures reported as informational placeholders |
| `eeg_ds000117` | 150 | 659 | 0 | 0 | 0 | No finding in the formats inspected by the MVP |
| `eeg_face13` | 155 | 471 | 0 | 0 | 90 | Empty BDF fixtures reported as informational placeholders |
| `eeg_rest_fmri` | 21 | 33 | 1 | 6 | 0 | One contact email and six BrainVision timestamps require a curator decision |
| `eeg_ds003645s_hed_demo` | 99 | 391 | 0 | 3 | 0 | Three BrainVision references retain a different source basename |

The first run treated empty EDF/BDF repository fixtures as malformed headers. The reader was changed to report zero-byte fixtures and Git LFS pointers as informational coverage notes instead. A genuinely truncated non-empty EDF/BDF header still produces `MALFORMED_HEADER`.

The remaining findings are intentionally not auto-suppressed. A public contact email can be deliberate, and an exact recording timestamp or older BrainVision basename can be acceptable in a specific release. The tool reports them so the curator makes that decision explicitly.

Large skipped counts show the current boundary clearly: the MVP does not inspect every neuroimaging format or EEG signal payload. Those files remain visible in the report rather than silently counted as clean.
