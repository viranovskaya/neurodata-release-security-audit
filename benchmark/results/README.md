# Benchmark result status

- `SUMMARY.md` is the short evidence matrix for the complete benchmark.
- `development.*` is regenerated while the evaluator and development labels
  are being refined.
- `locked_v1.*` is preserved as a rejected historical result. Its matcher
  allowed partial locations and an under-specified filename label, so the
  reported score is not a valid strict holdout result.
- `locked_v2.*` is the first strict result. Its exact matcher, frozen case hash
  and generated artifacts passed independent engineering review.
- `challenge_v1.*` is the immutable first run of a precommitted robustness
  challenge. It matched 23/25 findings and remains a no-pass result because
  structured JSON secret aliases were missed.
- `challenge_v1_successor.*` is the first correction attempt. It matches the
  25 listed targets, but remains a no-pass result because non-placeholder
  credential values shorter than eight characters were still missed.
- `challenge_v1_successor_v2.*` reruns the locked manifest after removing that
  length boundary. It matches 25/25 findings, keeps 6/6 hard-negative controls
  clean and records the pinned case hash in the JSON. This is regression
  evidence, not a second blind run.
- `public_formats.*` preserves the first reader check on two hash-pinned
  OpenNeuro files. MFF was still unscored in that version.
- `public_formats_v2.*` adds a hash-pinned EGI MFF directory from MNE's public
  testing-data repository. All three fixtures pass their reader, coverage and
  integrity checks. This is format evidence, not a labelled privacy score. The
  source files are not stored in this repository.

None of these reports proves that a dataset is anonymous or legally compliant.
