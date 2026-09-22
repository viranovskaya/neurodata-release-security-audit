# Evidence reconciliation — 2026-09-13 strict-review corrections

This document describes the **historical local engineering snapshot of 2026-09-13**,
not the current release candidate. Its counts and hashes below are retained as
historical evidence; see [the v0.3.0b2 changes](release_0.3.0b2.md) for later work.
At the time it was uncommitted, not a release, a new
human validation or a claim of security certification. The scanner runtime is
unchanged from the base; this work fixes its source-only evaluator and adds
reproducible, explicitly limited evidence. Historical artifacts remain intact.

## Identity and replay

- Base: `2a5a6a00be23d15b81065ceeea3945c90ea09b66`.
- Branch: `fix/masking-evidence` (local only).
- Runtime/evaluator/test input fingerprint:
  `40df0ab426884a0f8c452a3c80670a6ef34b45a407ad421453cf963c91d9adf1`.
- Python 3.13.7; MNE 1.12.1; nibabel 5.4.2; pydicom 3.0.2;
  defusedxml 0.7.1. The bundle records every installed distribution version.
- Both controlled wheel builds:
  `864cd56474d4f1524947102f54d4bf4f6ed02e094f419b18ab087fda08cdab27`.
  Built with setuptools 84.0.0 and the base commit's `SOURCE_DATE_EPOCH`.
  The internal version remains `0.3.0b1`; this does **not** overwrite, replace or
  claim byte identity to a historical release asset.

The fingerprint covers runtime, evaluator/builders, test source, source-only
usability code/spec, tool source, package metadata and reader constraints. It
does not pretend that untracked additions belong to the base Git commit. The
final bundle's source ZIP and manifest additionally bind the exact documents
and uncommitted files. The evaluator is **not** shipped in the scanner wheel.

Replay from a checkout **or an extracted source ZIP** into a new destination
(the runners reject an existing destination). No `git init` is required. With
no project-owned `.git`, the runner records `git_head: null` and snapshot mode;
it does not borrow the HEAD of a parent repository. Source hashes remain the
primary identity. These commands pin direct readers, not the entire transitive
environment; the full package-version list helps reconstruction but does not
make this a hermetic build.

The benchmark runner also checks the actually imported scanner package against
the source Python-module inventory before creating its output directory. It
records a normalized runtime origin and module hashes, rejects foreign loaded
scanner modules, and repeats the runtime check after the paired benchmarks.
An installed scanner with different source bytes cannot be attributed to this
snapshot. This is a normal-environment provenance check, not protection against
a compromised interpreter or malicious in-memory monkeypatching.

```bash
python -m pip install -c .github/constraints/calibration-readers.txt '.[formats,imaging]'
PYTHONDONTWRITEBYTECODE=1 python tools/run_verified_tests.py --origin source --output reports/source-tests-new
PYTHONPATH=.:src python -m benchmark.run_evidence --output reports/evidence-new
PYTHONPATH=.:src python -m benchmark.run_workflow_comparison --output reports/workflow-new
```

`run_evidence` optionally accepts `--hidden-archives /path/to/review-packages`.
These historical local ZIPs are not required for the current public source
benchmark. This work does not authorize their publication.

Verify the packaged artifact without extracting it, Git or installed readers:

```bash
python tools/verify_evidence.py /path/to/neurodata-evidence-strict-fixes-2026-09-13.zip \
  --sha256 HASH_FROM_A_TRUSTED_HANDOFF
```

Without `--sha256`, this checks internal consistency only, not authenticity.
The verifier checks exact ZIP inventories, all manifest hashes, the source ZIP,
wheel RECORD and source/wheel Python-module equality. It does not rerun tests or
validate scientific conclusions. The historical `freeze.py` is a one-time local
packaging recipe tied to its checkout, not the portable verifier.

## Corrected masking evaluator and historical results

The previous oracle looked for raw seeded substrings in concatenated rendered
outputs. An injected value containing backslashes and ampersands escaped that
check even though JSON decoding recovered it. This was an **evaluator defect**;
the injected report is not evidence that the production scanner emitted a real
participant identifier. The corrected check inspects each format separately,
including JSON keys and nested strings, HTML entities and the renderer's
Markdown escaping. Tests cover real-renderer fault injection, isolated format
faults and masked controls. No claim is made about arbitrary reconstruction.

| Historical synthetic suite | Cases | Matched labels | Clean controls | Duplicate alerts | Paired JSON/Markdown bytes |
|---|---:|---:|---:|---:|---|
| Development | 50 | 103/103 | 12/12 | 1 | Identical |
| Locked v2 | 10 | 21/21 | 2/2 | 0 | Identical |
| Challenge v1 replay | 14 | 25/25 | 6/6 | 0 | Identical |
| Adversarial development | 10 | 32/32 | 2/2 | 0 | Identical |

All four have zero unexpected findings and zero seeded masking/integrity
failures. Development also matches 10/10 references, 4/4 archive members and
22/22 coverage targets; locked v2 matches 2/2, 1/1 and 8/8 respectively. The
adversarial layer is part of development, so these rows **must not be summed
into an independent sample size**. The visible locked and challenge sets are
regression evidence, not newly blind validation.

The strict-fixes source and installed-wheel suites each pass 265 tests with all
optional readers and no skips. The wrapper records interpreter identity,
normalized import origin, module hashes and post-test runtime integrity in the
same process as unittest. Each run retains before/after records and its log.
Absolute home paths are not needed for these identity checks. The old 251-test
logs remain in the original bundle; they lack this same-process binding and
are not retroactively upgraded. A source test alone is not package evidence.
The 258-test predecessor bundle is also retained without modification. Seven
additional regressions cover runtime identity and exact saved-report checking.
This turn does not rerun the cross-platform CI matrix or claim current Linux,
Windows or Python 3.10/3.12 results.

## Historical hidden evidence recovered, not relabelled

The original complete ZIP hashes and archived member hashes were verified without
modifying the archives:

- hidden v1 ZIP: `ee798ac258daa8d32e15d1eefc34626898941c10ea005abfbacde7303f80d24d`;
  historical result 30/31, one unexpected finding, **no pass**;
- hidden v2 ZIP: `4d6a0bd3bf3c32902faf0c331311a7e326cfa8dbe02499257bb6d8f8cabcf496`;
  historical result 31/31 after the one documented XML-location adjudication.

A structural comparison confirms that the case definitions differ only at that
one report-safe location. All case inputs and other labels are unchanged. The
historical v2 JSON has a literal backslash-n trailer; the recovery checks that
exact known trailer and preserves the original bytes. The old wheel was not
rerun, the archived A/B claim was not independently repeated, and the old
zero-masking counts used the former evaluator. This is recovered provenance of
a historical machine review, not a second blind test or human validation.

## Narrow MNE workflow comparison

The historical [protocol](workflow_comparison_protocol.md) was hash-recorded
before input generation in the retained first run
(`87bc9cfcae5f0d2a54ce43048fd3ff8520aa444d219a7b55d0d3520ece01b577`).
This is local procedural evidence, not independent registration proving that no
earlier exploration occurred. The successor wording clarifies this distinction;
the original protocol bytes remain in each historical run directory.
Three synthetic native-FIF packages were processed with MNE's `Raw.anonymize`,
then audited twice on the same transformed bytes. The complete process was
also replayed from newly generated inputs. No competing tool's own codes were
used as shared ground truth.

| Predefined endpoint | Observation | Interpretation |
|---|---|---|
| FIF identity remediation | MNE replaced both seeded names and shifted birthday/recording date; recording shift was 3650 days | Baseline succeeds at its specified metadata transformation |
| Signal preservation | Samples, channel names and sampling rate unchanged in all three cases | No signal alteration in this tiny example; not a general numerical-validation claim |
| Sidecar scope | Sidecar bytes unchanged by MNE; NeuroData flags the seeded email at `participants.tsv`, line 2 | Complementary scope, **not an MNE miss**; column-level endpoint only partially met because the column name is absent |
| Clean participant-contact control | No email alert for `n/a` | This one targeted hard-negative passes; not general specificity |
| Masking and read-only integrity | No seeded strings recovered in the three output formats; input hashes unchanged; both integrity gates pass | Bounded mechanical checks, not an anonymity verdict |
| Repeatability | Within each fixed-input run, both sets of JSON/Markdown/HTML reports are byte-identical | Reproducible reports on fixed bytes; not a claim about fresh FIF serialization |

This workflow masking check covers the listed original identity seeds and the
sidecar email. It does not separately test the recording-date seed or transformed
dates. Most original FIF seeds have already been removed by MNE, so their absence
provides little additional evidence of masking. No actual report leak was
observed in the independent review; that observation does not fill this coverage
gap. The general evaluator regression tests remain a separate evidence layer.

The 2026-09-13 correction renders each report format once, saves those exact
UTF-8 bytes and checks the captured text for seeded values. The gate no longer
checks a second rendering that could differ from the saved file. An alternating
fault-injection renderer is covered by a regression test. Fresh workflow runs
live alongside, not in place of, the historical runs. They remain developer
replays and do not turn the original protocol into independent registration.

The augmented workflow also has a cost: on the anonymized seeded FIF it emits
two high-priority name-field warnings on MNE's standard replacement values, a
high-priority warning on the shifted birthday, and review notices for generated
metadata. The control receives three review notices but no participant-contact
alert. These are **not additional confirmed leaks**. The name placeholders are
known in this synthetic experiment, while the privacy implications of shifted
dates require context. The tool cannot infer safe anonymization solely from
field population, and ignoring all dates or trusting an anonymizer label would
be unsafe. No superiority, first-tool, time-saving or curator-performance claim
is justified by this example.

Reasonable follow-up candidates (not silently implemented in this snapshot):

1. Preserve TSV column provenance in direct-pattern findings without exposing
   sensitive column names or duplicating existing alerts.
2. Evaluate context-aware wording for known anonymizer placeholders; keep
   review and uncertainty instead of declaring a file safe or suppressing all
   populated date fields.

Both require new regression cases and review before changing scanner behaviour.

## Human evidence and remaining claims

The historical web pilot has eight paid general-adult completions, not a
verified curator sample: 99/104 fixed choices and 45/48 critical decisions.
Three critical errors remain. The recovered web follow-up plan uses a
ten-person target with C/D and integrity subtargets; it also contains later
stale 5/5 wording. It is not interchangeable with current source
`usability/spec.json`, and its present file state does not prove the exact
launch-time preregistration. The [pilot result](../usability/prolific_pilot2_results.md)
and [source-workflow status](../usability/results/README.md) now make those
boundaries explicit. No row-level participant data was opened or republished.

Safe claims: a local metadata/release-audit tool with masked reports and
hash-bound regression evidence; a small example showing complementary sidecar
review after MNE anonymization, including its observed limitations. Not safe:
security/privacy certified, comprehensive leak detection, validated expert
usability, repository adoption, novelty over all existing tools, or general
superiority. This package improves evidence traceability; it does not close
those scientific and human-evaluation gaps.

## Local artifact policy

`reports/strict-fixes-2026-09-13` holds the current corrected runs and a separate
deliberately malformed synthetic dataset smoke. That smoke has four files:
truncated JSON, a BrainVision header with two absent references, a synthetic
participant table, and a README. Two real CLI runs produced HOLD (exit 1), not
a crash: three high findings (name, email, birthday) and five review findings
(malformed JSON, two missing references, two source-name notices). All four
files remained byte-identical, and all three report formats matched between
runs without exposing the four synthetic identity seeds. This is a targeted
robustness check, not a new representative dataset study or extra blind sample.

`reports/evidence-successor-full` contains the successor paired results and
full-hash-pinned recovered ZIPs. `reports/evidence-final` preserves the original
paired results and recovered ZIPs;
`reports/workflow-comparison-first` and `reports/workflow-comparison-replay`
retain inputs and outputs; `reports/verification` holds test/package checks.
`reports/frozen-evidence` remains the original immutable-by-convention handoff.
`reports/frozen-evidence-successor` contains the corrected handoff with the
portable verifier, same-process test records and archive replay evidence.
Its source ZIP represents a
dirty local snapshot, not `git archive HEAD`. Older and partial attempts are
left in place and explicitly excluded from the final artifact manifest. Nothing
has been committed, pushed, deployed, released or sent externally by this task.
