# v0.3.0b4 — metadata boundary and robustness fixes

I fixed six masking, provenance and robustness issues found while auditing
the previous beta. The workflow is unchanged: audit a local dataset and review
the report before sharing it. Dataset files and reports are not uploaded.

- Arbitrary identifying prefixes in phone-field names no longer appear in
  finding locations. Phone detection still works; the location uses a safe
  placeholder when the key is not a recognised public field name.
- Selected MATLAB and EEGLAB HDF5 readers refuse virtual datasets, external
  storage and unsafe soft links. Unreadable EEGLAB text metadata does not
  trigger an MNE fallback. Unsupported content is left for manual review.
- Email matching no longer retries inside long percent-containing local-part
  runs. Valid percent-containing addresses remain supported.
- Office ZIP member and directory-size budgets are checked before loading the
  member table. The check counts actual directory headers instead of trusting
  a potentially forged member count, and accepts valid bounded ZIP64 files.
- Failed or refused JSON, table and XML parsing leaves an explicit coverage
  gap even when the raw text pass completed.
- The website's pinned development/build dependencies are updated, and CI
  checks npm advisories. This is a dated dependency check, not a guarantee
  against unknown vulnerabilities.

The audit adds eight regression tests covering these failure paths and their
positive controls. The local checks include source and exact installed-wheel
tests on Python 3.10 and 3.13, paired synthetic benchmark runs, saved-report
masking and integrity checks, and the website's Worker/D1 tests. GitHub CI also
checks clean installs on Linux, macOS and Windows.

This remains a public beta, not privacy certification or proof of complete
de-identification. Unsupported layouts and coverage gaps still need manual
review. Keep reports private until their paths and metadata have been reviewed.
Use this version instead of the earlier wheel for the corrected boundaries.
