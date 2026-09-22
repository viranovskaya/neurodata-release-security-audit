# v0.3.0b2 — bounded metadata reading and evidence checks

I have extended the classic MATLAB/EEGLAB metadata checks while keeping scans
local and read-only. This is a beta update, not a privacy certification.

## Scanner changes

- Selected text in classic MAT5 structs and cells can now be inspected without
  loading numeric signal arrays as arrays. Unsupported or budget-limited content
  remains explicitly partial; a successful scan does not imply full coverage.
- Traversal has cumulative text, node, depth and compressed-byte budgets. Empty
  matrices with very large zero-product dimensions cannot amplify output into
  millions of empty records. Corrupt encodings and lengths still fail closed.
- Compressed blocks may need bounded decompression even when numeric samples
  are skipped. Header enumeration and whole-file hashing remain outside these
  traversal budgets; this is not a whole-process memory or time sandbox.
- Flat sibling metadata findings survive a partial nested read.
- Exact `Anonymous` and numeric `sub-` name placeholders consistently require
  review instead of an automatic high-priority name finding. They are not
  treated as proof of de-identification. Names merely starting with those
  strings remain flagged; birth-date uncertainty remains visible.
- Three exact identity-field aliases are recognized. Overlapping secret
  patterns no longer duplicate the same span; distinct occurrences remain.

## Evidence tooling

The source-only evaluator now checks decoded JSON, HTML and Markdown separately
for seeded values. Evidence runners bind saved reports to source/import hashes,
and a standalone verifier checks archive inventories and wheel contents.
Historical pilot and benchmark documents distinguish regression evidence from
human validation. No participant-level data is included in this release.

The preceding local parser snapshot passed 292 source and 292 installed-wheel
tests with optional readers, 75 paired synthetic cases, 500 malformed mutations
and paired replays of 50 cached public dataset slices. These are bounded
engineering checks, not sensitivity estimates or confirmed privacy breaches.
Its 750 saved reports remained byte-identical after the empty-matrix repair.
The release build is separately checked and identified in the release assets;
historical candidate wheels labelled 0.3.0b1 are not reused or overwritten.

New MAT5 fixture tests explicitly skip when SciPy is absent. The pure malformed
empty-array test still runs with the base installation. This changes test
selection, not scanner behaviour.

## Remaining limits

This tool does not inspect every payload, infer consent, establish anonymity,
or approve dataset publication. Review every finding and coverage gap. The
public website provides an installation kit: personal datasets are audited
on the researcher's own machine, not uploaded to Cloudflare.
