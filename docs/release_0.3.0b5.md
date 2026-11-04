# v0.3.0b5 — bounded HDF5 reads and safer distribution

I tightened the metadata-read boundaries and the checks used to distribute the
beta. The workflow is unchanged: scan an authorised local dataset, keep the
reports private, and review findings and coverage before sharing anything.

- Selected HDF5 text reads now share byte, element and node limits. Variable-length
  strings, object-bearing compound values and unbounded class attributes are
  refused before value reads. Unknown EEGLAB roots, signal groups, soft links and
  reference-bearing signal layouts remain manual review. Known signal aliases
  cannot be read indirectly as text; bounded text-pool references still work.
- Office metadata rejects XML document type declarations before constructing
  the text tree, including UTF-16 declarations that bypassed the old byte check.
  Safe bounded UTF-16 text remains supported; unsupported encodings are manual review.
- Markdown values use the same escaping in audit and curator reports, so an
  archive member name cannot become an active Markdown image.
- Coverage labels match one-to-one, including overlapping partial labels.
  Historical suites retain their declared subset scope; exact-policy cases also
  reject unlabelled coverage rows. Locked case files were not relabelled.
- Kit checks compare the original ZIP without rewriting it. Normal builds refuse
  different bytes at an existing versioned filename. Exact-wheel checks bind the
  tested installation to the named artifact, its RECORD and source module bytes.
- Website fixes check archive digests and release transitions, serialize download
  and confirmation, discard stale sessions after untracked downloads, limit
  public stats reads, and keep optional statistics from blocking successful actions.

Regression checks cover the refusal paths and positive controls. Local source
and exact installed-wheel checks run on Python 3.10 and 3.13; synthetic benchmark
replays, saved-report masking/schema/integrity checks and local Worker/D1 tests
are separate evidence. The website kit is updated only after the exact scanner
wheel is published, so its CI never needs an unpublished asset.

The 50-dataset calibration remains historical scanner 0.2.0.dev0 evidence, not a
new real-data calibration. Tests and checksums do not certify anonymity, complete
metadata coverage or the safety of native parser internals. Review unsupported
layouts manually. This is still a beta and does not approve a dataset release.
