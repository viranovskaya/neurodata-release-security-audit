# Benchmark evidence

The benchmark has separate layers because no single dataset answers every
question.

| Layer | Data | Result | What it checks | Main limitation |
|---|---|---|---|---|
| Development | 40 labelled synthetic releases; 71 findings | 71/71 findings; 10/10 clean controls | detector regressions, masking, references, archives and coverage | used while developing the scanner |
| Locked v2 | 10 visible synthetic cases; 21 findings | 21/21 findings; 2/2 clean controls | exact code, severity, file and location matching | repository-visible, not blind |
| Hidden v1 | 13 independently written synthetic cases; 31 findings | 30/31; no pass | independent interpretation of the label contract | one raw-versus-masked XML location disagreement |
| Hidden v2 | the same hidden cases after one authorised location adjudication | 31/31 | the clarified report-safe location rule | adjudicated, not a second blind test |
| Public formats | one EEGLAB SET and one KIT/Yokogawa CON file | 2/2 reader checks | real reader execution, `preload=False`, source hashes and integrity gates | no privacy ground truth; MFF unscored |

## Current development result

- Findings: 71/71
- Unexpected findings: 0
- Clean controls: 10/10
- Cross-file references: 10/10
- Archive members: 4/4
- Coverage targets: 22/22
- Masking failures: 0
- Integrity failures: 0

The realistic release cases combine metadata and binary-format fixtures into a
sleep release, an imaging release and a clean BrainVision release. The first
sleep run exposed a missed `emergency_phone` alias. The detector was fixed and
the case remains in the suite as a regression test.

## Reproducibility hashes

| Artifact | SHA-256 |
|---|---|
| Development suite manifest | `6d0497e427e0c1214ba211e0db509e25930579cde38d4e66e2e85e0b45545536` |
| Realistic release cases | `7da1a51e5f85c18826166edba4ce487b5719734f9e8eb6d1a5776de73d529257` |
| Development JSON result | `8870247be31759255b5ebc4e762601d1402f119c2646c3403ef92804342634e8` |
| Development Markdown result | `518451627484500880038eb2d7ee5914cd98a9e5be1dd25cfe7aeb0e8a1ba405` |
| Locked-v2 cases | `8cf46acc992ee7b01426e6f3560f0e3e488eff135f2cbcda597e6568ad62fc42` |
| Locked-v2 JSON result | `87fc214547ed374dc3eb3ffa95dd1d81d40c22a4c785a0685611fa25e9e5df99` |
| Public-format manifest | `28c6335ab4ef0420161c2a499bd6e9e2a731a2f344394c186d9799a59d72f08c` |
| Public-format JSON result | `4570dc9fa6eb7444e6f9ba701db1a19ee57f736ebb43d309242ffdc88d14aa9c` |

## Interpretation

These results support the scanner's engineering and regression claims. They do
not show that an arbitrary dataset is anonymous, legally compliant or free from
all disclosure risk. Statistical re-identification risk, signal-based
identification and malicious local actors remain outside this benchmark.
