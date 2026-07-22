# Initial public-example calibration

The local MVP was run against six EEG examples from a local checkout of `bids-standard/bids-examples` on 22 July 2026. This is a usability and false-positive check, not a privacy benchmark.

| Example | Inspected | Skipped | High | Review | Info | Main result |
|---|---:|---:|---:|---:|---:|---|
| `eeg_cbm` | 104 | 0 | 0 | 20 | 20 | Twenty unshifted BIDS `acq_time` values require review |
| `eeg_rishikesh` | 167 | 14 | 0 | 0 | 40 | Source/config coverage adds one inspected text file; no new finding |
| `eeg_ds000117` | 247 | 562 | 0 | 0 | 96 | Empty optional-format fixtures are now visible coverage notes rather than generic skipped files |
| `eeg_face13` | 171 | 455 | 0 | 3 | 100 | Two local paths in MATLAB code and one `Thumbs.db` file require review |
| `eeg_rest_fmri` | 21 | 33 | 1 | 6 | 0 | One contact email and six BrainVision timestamps require a curator decision |
| `eeg_ds003645s_hed_demo` | 108 | 382 | 0 | 22 | 9 | Nineteen BIDS acquisition times and three BrainVision source references require review |

The first run treated empty EDF/BDF repository fixtures as malformed headers. The reader was changed to report zero-byte fixtures and Git LFS pointers as informational coverage notes instead. A genuinely truncated non-empty EDF/BDF header still produces `MALFORMED_HEADER`.

The expanded run also checks the standard BIDS `acq_time` field and bounded source/config text. This exposed dates from 2005 and 2009, local MATLAB paths and an operating-system metadata file. These are useful review findings rather than test noise.

The final format run recognises empty FIF and EEGLAB placeholders explicitly. This moved 115 entries from the generic skipped count to inspected informational findings across three examples. It did not add a new high-severity finding. The only high finding remains the public contact email already described above.

The remaining findings are intentionally not auto-suppressed. A public contact email can be deliberate, and an exact recording timestamp or older BrainVision basename can be acceptable in a specific release. The tool reports them so the curator makes that decision explicitly.

Large skipped counts show the current boundary clearly: the MVP does not inspect every neuroimaging format or EEG signal payload. Those files remain visible in the report rather than silently counted as clean.
