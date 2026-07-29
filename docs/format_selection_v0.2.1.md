# Format selection for v0.2.1

Format work for this candidate is chosen from the fixed 50-dataset OpenNeuro
calibration, not from a list of formats that might be useful later.

## What the calibration showed

All 50 dataset slices completed and passed both integrity rechecks. No entry was
left as an unsupported filesystem object or an untraversed directory. Optional
readers were available throughout the final run.

The remaining format-specific limits were:

| Finding | Datasets | Meaning |
|---|---:|---|
| `EEGLAB_METADATA_COVERAGE_LIMIT` | 3 | the `.set` file used a legacy nested MATLAB structure that the metadata-only pass could not separate safely from signal data |
| `EEGLAB_METADATA_UNREADABLE` | 1 | the safe EEGLAB metadata reader raised `NotImplementedError` |
| `NIFTI_EXTENSION_PRESENT` | 2 | an extension was found and reported for review; voxel data was not opened |

Eight signal or image payloads were deliberately not opened. This is the
documented audit boundary, not a missing reader.

## Decision

No new general-purpose format reader is added for v0.2.1.

The repeated gap is legacy nested EEGLAB metadata. Loading those files through
MNE would also load or depend on the signal representation, which would break
the metadata-only promise of this audit. The safer behaviour is already in
place:

- report the exact `.set` path;
- emit `EEGLAB_METADATA_COVERAGE_LIMIT`;
- keep the file in the skipped-coverage section;
- require manual review with EEGLAB or another tested format-aware workflow;
- rerun the audit after remediation.

The unreadable EEGLAB case likewise remains a visible review item instead of
being treated as clean. NIfTI extensions stay visible without opening voxel
data.

## What would justify a later reader change

A later change needs all of the following:

1. at least one hash-pinned public fixture for the affected layout;
2. a metadata-only parser path that does not load signal samples, voxels or
   pixels;
3. explicit tests for malformed, external-reference and nested structures;
4. before-and-after integrity checks;
5. a redacted deterministic report;
6. independent review of the exact frozen candidate.

Until then, a clear coverage warning is more honest than a broader reader claim.
