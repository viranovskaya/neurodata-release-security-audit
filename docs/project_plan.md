# Project plan

## Goal

Build a small, explainable pre-release security check for EEG datasets. The scanner should catch clear privacy and metadata leaks without altering the source data or claiming legal compliance.

## Phase 1 — Core contract

- Define finding codes, severities and masking rules.
- Define deterministic JSON and readable Markdown reports.
- Implement safe directory traversal with no external symlink following.
- Cover direct email, labelled phone, local path and obvious secret patterns.

**Gate:** synthetic leaks are detected and never reproduced in full in a report.

## Phase 2 — EEG formats

- Inspect BrainVision `.vhdr` and `.vmrk` text metadata.
- Inspect the fixed header section of EDF and BDF without loading samples.
- Report dates of birth, populated patient-name fields and recording dates.

**Gate:** clean and leaky synthetic fixtures behave as expected; malformed headers fail visibly and safely.

## Phase 3 — Release-tree checks

- Flag likely participant-key spreadsheets and backup files.
- Flag symlinks and files that the scanner cannot inspect.
- Record every inspected, skipped and unreadable file.

**Gate:** the audit has no silent coverage gaps.

## Phase 4 — Local v0.1 review

- Run the full test matrix.
- Confirm deterministic output and unchanged source files.
- Review false positives on BIDS examples and synthetic cases.
- Perform a separate security review of traversal, decoding and report masking.

**Gate:** implementation and documentation agree; no public claims exceed the evidence.

**Current checkpoint:** 42 tests pass. Six public EEG BIDS examples were used for initial false-positive review, and four real Sleep-EDF files were checked without copying them into the repository. A clean package installation and the installed command were also checked.

## Phase 5 — External validation

- Ask BIDS/MNE and neurodata privacy researchers whether the scope fills a real gap.
- Add formats or policies only in response to concrete use cases.
- Handle any credible public-dataset privacy finding through private responsible disclosure.

**Gate:** at least one independent reviewer can run and understand the tool.

**Current checkpoint:** a synthetic reviewer demo, expected result and short feedback guide are ready. No external review has been requested or completed yet.

## Phase 6 — Publication decision

- Decide whether the result is best maintained as a small utility, contributed upstream, or developed into a software paper.
- Create a public repository, release metadata and citation files only after the local review.
