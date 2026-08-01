# Project plan

## Goal

Build a local, read-only pre-release check that makes accidental personal and
technical leakage visible without claiming that a dataset is anonymous.

## v0.1 — EEG release check

Completed privately:

- deterministic findings and masked reports;
- release-tree, text, BIDS, BrainVision and EDF/BDF checks;
- optional FIF, EEGLAB and MFF metadata readers;
- synthetic, public BIDS and real-format calibration;
- clean wheel and deterministic report checks;
- independent review of the exact frozen v0.1 snapshot.

The v0.1 review does not carry forward to later commits.

## v0.2 — full release accounting

### M1 — inventory and integrity

Status: implemented.

- one coverage status for every encountered entry;
- SHA-256 manifest for every readable regular file;
- file and release-tree rechecks after metadata inspection;
- explicit signal, unsupported and unparsed states.

### M2 — NIfTI

Status: implemented.

- metadata-only nibabel reader;
- text-bearing header checks;
- no voxel access;
- visible NIfTI extension boundary.

### M3 — DICOM

Status: implemented.

- metadata before Pixel Data;
- nested sequences and file metadata;
- patient, date, site, device, UID and free-text checks;
- private tags and encapsulated documents reported without opening their values;
- no pixel access.

### M4 — archives and links

Status: implemented.

- ZIP and TAR member inventory without extraction;
- encryption, traversal, links, nested archives and collision checks;
- BrainVision, EEGLAB and BIDS reference resolution;
- release filename collision checks.

### M5 — integrated beta candidate

Status: implemented. The current public-beta candidate is frozen on a private
branch until its exact successor review and final release approval are complete.

- update CLI, schema, documentation and version;
- run the full suite in base, EEG-format and imaging environments;
- run Python 3.10 and the newest supported Python;
- validate JSON against the published schema;
- reproduce wheel and report bytes;
- recalibrate on synthetic and public datasets;
- scan public files for private values and local paths;
- freeze one clean local commit and reviewer package.

### M6 — independent review and public beta

Status: the technical review passed for the first `0.2.0b1` candidate, but its
public documentation required correction. The corrected successor needs a new
exact-snapshot PASS before merge, tag or visibility change.

The reviewer receives one exact commit and package with hashes, test evidence,
claim boundaries and known limitations. A previous PASS is not reused.

The review of one exact snapshot does not authorize a later push, pull request,
merge, tag, release or public publication.

## Next decisions

After the corrected successor review:

- publish a clearly labelled GitHub beta only after final approval;
- collect feedback from at least five researchers or data curators using their
  own local release copies;
- decide from that evidence whether the project should remain a small utility or
  be extended;
- consider a software paper only if later use and validation support it;
- keep statistical disclosure analysis, MRI defacing and signal-based
  re-identification as separate workflows.
