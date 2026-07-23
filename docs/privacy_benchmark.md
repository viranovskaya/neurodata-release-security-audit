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
are not in the case label count as unexpected.

## Metrics

The first pilot reports:

- target recall;
- labelled precision;
- specificity across clean controls;
- masking failures across JSON, Markdown and HTML;
- release-integrity failures.

Later format-level reports will stratify results by leak class and file format.
Coverage errors will be reported separately from missed findings: a format that
the scanner explicitly leaves for manual review is not the same as a format it
claims to inspect but misses.

## Splits

The initial cases are a development pilot. They are used to check the evaluator
and refine the labels.

Before detector tuning, a separate locked split will be versioned and hashed. A
later independent review should add a small hidden set; a repository-visible
split is locked, but it is not genuinely blind to the developer.

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

## Run the pilot

Install the current package, then run:

```bash
python -m benchmark.run_benchmark \
  --json reports/benchmark.json \
  --markdown reports/benchmark.md
```
