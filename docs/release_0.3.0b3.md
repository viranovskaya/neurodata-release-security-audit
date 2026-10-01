# v0.3.0b3 — archive, metadata and Windows fixes

I have tightened bounded metadata inspection and fixed report generation on
Windows. Researchers can continue auditing their own datasets locally using
the command-line tool or local browser interface.

- ZIP member counts and directory sizes are checked before loading the member
  table. Over-budget archives receive an explicit manual-review coverage item.
  TAR inspection retains bounded header summaries; overlong member names make
  collision coverage explicitly partial.
- Nested DICOM sequence items are traversed within the element and depth
  budgets. XLSX inline-string cells are included in the bounded text pass;
  numeric cells and formula results remain outside that pass.
- Windows report writing skips unsupported directory fsync while retaining
  file fsync, atomic no-clobber publication and rollback.
- The report label now says “Masked evidence seen once” to describe the actual
  grouping and avoid implying that the original unmasked values are unique.
- The researcher beta server fails closed if rate limiting is unavailable,
  uses separate per-client download and confirmation buckets, and rejects
  symlinks when building the installation kit. Its development dependencies
  include the patched sharp and undici versions.

CI checks source tests, exact installed wheels, and report generation on Linux,
macOS and Windows. These are engineering regression checks. This beta does not
establish anonymity, infer consent, inspect every payload or approve a dataset
for publication. Review findings and coverage gaps before sharing data.

The public site distributes the installation kit. Dataset files and reports
stay on the researcher's own computer.
