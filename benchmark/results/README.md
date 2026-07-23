# Benchmark result status

- `development.*` is regenerated while the evaluator and development labels
  are being refined.
- `locked_v1.*` is preserved as a rejected historical result. Its matcher
  allowed partial locations and an under-specified filename label, so the
  reported score is not a valid strict holdout result.
- `locked_v2.*` is the first result that may be used after its exact matcher,
  frozen case hash and generated artifacts pass independent review.

None of these reports proves that a dataset is anonymous or legally compliant.
