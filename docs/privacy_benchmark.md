# Leak-detection benchmark

The 50-dataset OpenNeuro calibration answers a practical question: does the
scanner complete consistently on varied real neurodata? It does not provide
complete ground truth, so it cannot estimate precision or recall.

This benchmark is a separate labelled evaluation.

## Unit of evaluation

Each case is a small synthetic release with:

- one or more seeded findings;
- the expected code, severity, file and field location;
- every seeded value that must be absent from the reports;
- a declared development or locked split.

A finding is correct only when the code, severity, file and location match. The
label uses the report-safe `Finding.path` and `Finding.location`, after dynamic
keys and sensitive path fragments have been masked. It does not use the raw
source key when that key is intentionally hidden from the report. A masked value
in the wrong field does not count as a true positive. Findings that are not in
the case label count as unexpected. Multiple rows with the same code, severity,
file and location count as one detected target plus a separate duplicate alert;
they do not create extra ground-truth leaks.

## Metrics

The development suite reports:

- target recall;
- labelled precision;
- specificity across clean controls;
- duplicate alerts for the same code, severity, file and location;
- results split by file format and finding class;
- cross-file reference, archive-member and coverage-state checks;
- masking failures across JSON, Markdown and HTML;
- release-integrity failures.

Coverage errors will be reported separately from missed findings: a format that
the scanner explicitly leaves for manual review is not the same as a format it
claims to inspect but misses.

The current development set includes 40 cases and 71 labelled findings. It
builds small EDF, BDF, BrainVision, FIF, NIfTI and DICOM files and opens them
through the same metadata readers as a normal audit. It also covers structured
text, release paths, archives and cross-file references. Three cases assemble
these pieces into complete synthetic sleep, imaging and clean BrainVision
release folders. The first realistic sleep case exposed a missed
`emergency_phone` column alias; that gap was fixed and kept as a regression
test. These cases were used while building the evaluator, so their scores are a
development check rather than an independent validation result.

Reproducible reports are stored in `benchmark/results/`. The development result
is regenerated whenever the evaluator or development labels change.

The first locked result is retained only as a historical artifact. Independent
review found that its matcher allowed partial locations and labels without a
file path, even though the method required exact identities. It is not a valid
holdout score and must not be quoted. `locked-v2` uses strict labels with exactly
`code`, `severity`, `path` and `location`.

The first strict `locked-v2` run matches 21 of 21 labels across 10 cases, with
zero unexpected findings, masking failures or integrity failures. This result is
stored for reproducibility but remains subject to independent review. Even
after review, it is a small visible holdout rather than a blind validation.

`challenge-v1` was then committed before its first run. It adds field-name
variations and hard-negative controls without optional binary readers. The
frozen first run matched 23 of 25 labels and kept all 6 controls clean. Both
misses were structured JSON credentials: `clientSecret` and `refreshToken`.
The result remains a no-pass artifact. The labels and case hash are not changed
when the detector is corrected.

An independently authored hidden-v1 set later matched 30 of 31 exact labels. The
only mismatch had the correct code, severity and file but used a raw XML field
path where the report intentionally emitted a masked location. The frozen hidden
result remains a no-pass result; the case was not relabelled after the run. This
ambiguity led to the explicit report-safe location rule above.

After that rule was documented, the reviewer changed only the disputed hidden
location label and reran the same cases as hidden-v2. The adjudicated result
matched 31 of 31 labels. It confirms the clarified scoring rule, but it is not a
second blind test and should not be reported as one.

## Public format smoke checks

Two hash-pinned OpenNeuro files provide a separate reader check:

- an EEGLAB `.set` file from `ds004745`;
- a KIT/Yokogawa `.con` file from `ds004738`.

The runner verifies each source hash, copies the file into a temporary release,
runs the normal scanner, checks the copy and original again, and requires
header-or-structure-only coverage with both integrity rechecks passing. The
result records finding codes, not values or evidence.

This is not part of the labelled privacy score. It shows that the installed
readers can inspect these two real files without preloading signal data. It does
not establish whether every finding is a true privacy leak. EGI MFF remains
unscored because no independent hash-pinned public fixture is included.

## Splits

The initial cases are a development pilot. They are used to check the evaluator
and refine the labels.

The rejected first split remains unchanged in
`benchmark/cases/locked_v1.json`. Its successor is stored in
`benchmark/cases/locked_v2.json`, with its SHA-256 pinned in
`benchmark/locked_v2.json`. The runner stops if the file changes. A locked split
must not be edited after its first committed version. A later independent
review should add a small hidden set; a repository-visible split is locked, but
it is not genuinely blind to the developer.

## Scope

The full benchmark should cover:

- JSON, TSV, CSV, XML and free text;
- release paths and known private terms;
- BrainVision, EDF/BDF, FIF, EEGLAB and MFF metadata;
- NIfTI and DICOM metadata boundaries;
- ZIP and TAR member names;
- BIDS and format-specific cross-file references;
- clean lookalikes, public-contact metadata and ordinary BIDS identifiers.

It will not use real participant information. Strong benchmark results still do
not prove that an arbitrary dataset is anonymous, ethically shareable or legally
compliant.

## Run the development suite

Install the current package with both reader extras, then run:

```bash
python -m pip install -e '.[formats,imaging]'
python -m benchmark.run_benchmark \
  --json reports/benchmark.json \
  --markdown reports/benchmark.md
```

Run the locked split separately:

```bash
python -m benchmark.run_benchmark \
  --cases benchmark/locked_v2.json \
  --json reports/benchmark-locked-v2.json \
  --markdown reports/benchmark-locked-v2.md
```

Run the public format smoke checks against a local copy of the pinned files:

```bash
python -m benchmark.run_public_formats \
  --fixtures-root /path/to/public/files \
  --json reports/public-formats.json \
  --markdown reports/public-formats.md
```

The expected paths, hashes and provenance are listed in
`benchmark/public_format_fixtures.json`. The public files are not distributed
with this repository.
