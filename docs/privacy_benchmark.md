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

A finding is correct only when the code, severity, file and location match. A
masked value in the wrong field does not count as a true positive. Findings that
are not in the case label count as unexpected. Multiple rows with the same code,
severity, file and location count as one detected target plus a separate
duplicate alert; they do not create extra ground-truth leaks.

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

The current development set includes 36 cases and 50 labelled findings. It
builds small EDF, BDF, BrainVision, FIF, NIfTI and DICOM files and opens them
through the same metadata readers as a normal audit. It also covers structured
text, release paths, archives and cross-file references. These cases were used
while building the evaluator, so their scores are a development check rather
than an independent validation result.

Reproducible reports are stored in `benchmark/results/`. The development result
is regenerated whenever the evaluator or development labels change.

The first locked result is retained only as a historical artifact. Independent
review found that its matcher allowed partial locations and labels without a
file path, even though the method required exact identities. It is not a valid
holdout score and must not be quoted. `locked-v2` uses strict labels with exactly
`code`, `severity`, `path` and `location`.

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
