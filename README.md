# NeuroData Release Security Audit

A local, read-only check for privacy and metadata leaks in EEG datasets prepared for sharing.

The first version focuses on BIDS text metadata, BrainVision files, and EDF/BDF headers. It looks for clear release risks such as direct contact details, dates of birth, unshifted recording dates, local computer paths, participant-key files, and obvious credentials.

The scanner does not change the dataset and does not upload anything. Findings are masked in reports.

Reports retain relative filenames so a researcher can locate a problem. A filename can itself be sensitive, so reports should be reviewed before they are shared.

## Current status

Local MVP. It has structured JSON/TSV/CSV checks, BrainVision and EDF/BDF header checks, deterministic masked reports, 19 synthetic tests, and an initial calibration on six public BIDS examples. It has not been published or independently validated yet.

## Run locally

From the repository root:

```bash
PYTHONPATH=src python3 -m neurodata_security_audit scan /path/to/dataset
```

To save machine-readable and review reports:

```bash
PYTHONPATH=src python3 -m neurodata_security_audit scan /path/to/dataset \
  --json reports/audit.json \
  --markdown reports/audit.md
```

The command exits with status `1` when it finds at least one high-severity item, `0` otherwise, and `2` when the scan cannot run.

## What this is not

This tool does not certify that a dataset is anonymous or compliant with GDPR, HIPAA, an ethics approval, or an institutional policy. It does not assess whether the EEG signal itself could identify a participant. It is an additional pre-release check, not a replacement for BIDS validation, format-specific anonymisation, or human review.

The current threat model is accidental release by an honest curator. It does not cover malicious concurrent modification of a dataset during a scan, encrypted archives, malware, or adversarial files designed to exploit the parser.

The design scope is recorded in [docs/mvp_spec.md](docs/mvp_spec.md). The first public-example calibration is documented in [docs/calibration.md](docs/calibration.md).
