# Narrow workflow comparison: MNE anonymization plus release review

Protocol recorded before input generation in the retained first run on
2026-09-12; this is local procedural evidence, not independent registration.
The runner records this file's SHA-256 before creating any input or result. Any subsequent
protocol change requires a separately named run; do not overwrite old runs.

## Question and baseline

For a small native FIF sharing package, what information does a read-only
release audit add after MNE's standard recording-metadata anonymization?
The baseline is **MNE 1.12.1 `Raw.anonymize(daysback=3650, keep_his=False)`**, save,
reopen and inspect the resulting `Info`. The augmented workflow uses the exact
same transformed files and adds NeuroData. It is not an end-to-end test of a
human curator, BIDS validation, MNE-BIDS, BIDSonym or repository infrastructure.

MNE is deliberately credited for changing sensitive FIF metadata. Arbitrary
sidecars are outside `Raw.anonymize`'s scope; leaving them unchanged is **not an
MNE defect or a false negative**. NeuroData is a warning/reporting tool, not an
anonymizer. Comparing their own finding codes or aggregate accuracy is invalid.

References: [MNE anonymization API](https://mne.tools/1.12/generated/mne.io.Raw.html#mne.io.Raw.anonymize),
[MNE-BIDS whole-dataset anonymization](https://mne.tools/mne-bids/stable/generated/mne_bids.anonymize_dataset.html).
BIDS Validator and BIDSonym address related but different scopes; this small
experiment cannot rank them or establish novelty over them.

## Fixed inputs

Three developer-authored, entirely synthetic FIF packages (one zero-valued EEG
channel, 10 samples, 100 Hz) with generic filenames:

1. `recording_only`: seeded first/last name, birthday and recording date in FIF.
2. `recording_and_sidecar`: the same FIF and `participants.tsv` with a seeded
   participant-contact email under an explicit `email` column.
3. `control`: no seeded participant identity or date; the sidecar contains only
   the pseudonymous BIDS-style identifier `sub-01` and `email=n/a`.

The inputs are not BIDS datasets and are not presented as real participants.
Exact bytes and file hashes are retained. The baseline output becomes a fixed
input to both repeated NeuroData runs. MNE file serialization can contain
generated identifiers, so cross-invocation byte identity of newly generated
FIF files is not an endpoint.

## Predefined semantic endpoints

| Endpoint | Applicable scope | Evidence, not tool-specific labels |
|---|---|---|
| FIF identity remediation | MNE baseline | Reopened first/last name differs from the seeded values; birthday no longer equals the seed; recording date shifts by exactly 3650 days |
| Signal preservation | MNE baseline | Samples, channel names and sampling rate remain equal before/after anonymization |
| Sidecar scope | Both, different roles | Byte hashes show that MNE leaves the sidecar untouched; NeuroData's report locates a populated participant contact in the same file and column, with masked value |
| Clean-control behaviour | NeuroData | No participant-contact alert for `email=n/a`; do not require the whole report to be empty, because other bounded review notices may be legitimate |
| Report safety | NeuroData | The seeded strings are absent after the corrected per-format masking checks; no release approval is inferred |
| Read-only integrity | NeuroData | Both report integrity gates pass and independent input hashes remain unchanged |

For interpretation, list semantic observations and report evidence, not a
single winner/accuracy number. Keep all findings for inspection. Unexpected
notices are not automatically false positives. Do not select a different
baseline or change inputs/criteria after seeing the outcomes without recording
a new exploratory protocol.

## Limits

This is a small developer-run integration example on synthetic inputs, not a
blind benchmark, an independent human evaluation, a real-world prevalence
estimate, a comparison of curator speed, or proof that remaining metadata is
safe. Placeholder/shifted values may still require review. Manual metadata and
sidecar inspection could discover the same issues; this experiment does not
measure that effort. Machine tests do not replace human validation.

## Replay

From a source checkout installed with the pinned calibration readers:

```bash
PYTHONPATH=.:src python -m benchmark.run_workflow_comparison \
  --output reports/workflow-comparison-new
```

The destination must not exist. The runner saves protocol identity, inputs,
baseline copies, structured observations and two sets of masked reports. It
fails on input modification, seeded report leakage, failed integrity or
non-reproducible report bytes. Semantic results remain visible even when a
baseline observation differs from expectation; the script is not a superiority
test.
