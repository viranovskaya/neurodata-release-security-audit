# Benchmark result status

- `development.*` is regenerated while the evaluator and development labels
  are being refined.
- `locked_v1.*` is preserved as a rejected historical result. Its matcher
  allowed partial locations and an under-specified filename label, so the
  reported score is not a valid strict holdout result.
- `locked_v2.*` is the first strict result. Its exact matcher, frozen case hash
  and generated artifacts passed independent engineering review.
- `public_formats.*` records reader and integrity checks on two hash-pinned
  OpenNeuro files. It is format evidence, not a labelled privacy score. The
  source files are not stored in this repository.

None of these reports proves that a dataset is anonymous or legally compliant.
