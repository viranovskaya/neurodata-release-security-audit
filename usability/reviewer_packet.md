# NeuroData report review

Please answer from the report alone. Do not inspect the source code, specification or answer key.

For each task:

1. start a timer before opening the report;
2. choose one answer;
3. record elapsed seconds and confidence from 1 to 5;
4. close the report before moving to the next task.

Complete the tasks in the order shown. Some reports are used more than once, so elapsed time is descriptive and is not part of the pass threshold.

This packet contains synthetic metadata only. Do not add your name, email or other personal details.

## Report: [clean](reports/clean.html)

### clean_release_decision

What does this report support?

- [ ] `checked_areas_clear` — No high or review findings were found in the checked areas, but coverage and format limits still need review.
- [ ] `anonymous` — The dataset is anonymous and ready to publish.
- [ ] `blocked` — The dataset must not be released because the integrity check failed.

- Elapsed seconds:
- Confidence (1-5):

## Report: [high](reports/high.html)

### high_release_decision

Can this copy be released now?

- [ ] `do_not_release` — No. Resolve the high-priority finding first.
- [ ] `release_with_note` — Yes, if the README mentions the finding.
- [ ] `report_invalid` — No decision is possible because the integrity check failed.

- Elapsed seconds:
- Confidence (1-5):

### high_file

Which file needs correction?

- [ ] `fif` — sub-01/eeg/sub-01_task-rest_eeg.fif
- [ ] `participants` — participants.tsv
- [ ] `description` — dataset_description.json

- Elapsed seconds:
- Confidence (1-5):

### high_location

Which field is named in the report?

- [ ] `birthday` — subject_info.birthday
- [ ] `name` — subject_info.name
- [ ] `meas_date` — measurement_date

- Elapsed seconds:
- Confidence (1-5):

### high_remediation

What is the safest next step?

- [ ] `private_format_aware` — Edit a private working copy with a format-aware FIF tool, rerun the audit, then verify the scientific properties.
- [ ] `delete_original` — Delete the original file and rebuild it from the report.
- [ ] `open_text_editor` — Open the FIF file in a text editor and remove the matched bytes.

- Elapsed seconds:
- Confidence (1-5):

## Report: [coverage_gap](reports/coverage_gap.html)

### coverage_gap

What still needs manual review?

- [ ] `xyz` — sub-01/eeg/sub-01_task-rest_eeg.xyz because its payload was not parsed.
- [ ] `nothing` — Nothing; zero findings means complete coverage.
- [ ] `manifest` — The SHA-256 manifest because hashes were not generated.

- Elapsed seconds:
- Confidence (1-5):

## Report: [integrity_failure](reports/integrity_failure.html)

### integrity_reliability

Can the individual findings be relied on yet?

- [ ] `provisional` — No. The finding list is provisional until a new scan passes both integrity checks.
- [ ] `yes` — Yes. The high-priority email finding is enough to continue remediation.
- [ ] `ignore_manifest` — Yes. Only the release-tree recheck matters.

- Elapsed seconds:
- Confidence (1-5):

### integrity_next_step

What should happen first?

- [ ] `stabilize_rerun` — Stop writes, restore or stabilize the candidate, and rerun the audit.
- [ ] `remove_email` — Remove the email from participants.tsv before doing anything else.
- [ ] `publish_report` — Publish the report so another person can inspect the email finding.

- Elapsed seconds:
- Confidence (1-5):

## Report: [large_review](reports/large_review.html)

### large_review_count

How many review items need a curator decision?

- [ ] `121` — 121
- [ ] `120` — 120
- [ ] `30` — 30

- Elapsed seconds:
- Confidence (1-5):

### large_review_target

Where is the unique technician-contact item?

- [ ] `sub17` — sub-17/eeg/sub-17_task-rest_eeg.vhdr — Recording.TechnicianContact
- [ ] `sub07` — sub-07/eeg/sub-07_task-rest_eeg.vhdr — experimenter_comment
- [ ] `sub30` — sub-30/eeg/sub-30_task-rest_eeg.vhdr — device.serial_number

- Elapsed seconds:
- Confidence (1-5):

Return the completed packet to the study administrator. The administrator records only the answer code, elapsed seconds and confidence in the pseudonymous response file.
