# Report contract

The JSON report is deterministic. It deliberately omits a generation timestamp and the absolute dataset path.

```json
{
  "schema_version": "1",
  "scanner_version": "0.1.0.dev0",
  "summary": {
    "files_inspected": 3,
    "files_skipped": 1,
    "findings_high": 1,
    "findings_review": 0,
    "findings_info": 0
  },
  "files_inspected": [
    "dataset_description.json",
    "sub-01/eeg/sub-01_task-rest_eeg.vhdr",
    "sub-01/eeg/sub-01_task-rest_eeg.vmrk"
  ],
  "skipped_files": [
    {
      "path": "sub-01/eeg/sub-01_task-rest_eeg.eeg",
      "reason": "EEG signal payload is outside the MVP scope"
    }
  ],
  "findings": [
    {
      "code": "DIRECT_EMAIL",
      "severity": "high",
      "path": "notes.txt",
      "location": "line 2",
      "evidence": "<redacted:email,length=22>",
      "message": "Confirm this email is intentionally public; otherwise remove it."
    }
  ]
}
```

Finding order is `severity`, `path`, `location`, then `code`. File lists are sorted by relative POSIX path.

Relative filenames are retained for remediation. Known terms, contact details, direct
IDs, labelled dates, obvious credentials and detected local or network paths are
masked in release paths. Structured locations use stable placeholders for arbitrary
keys. Other identifying filename text may remain, so a report is not automatically
safe to publish.
