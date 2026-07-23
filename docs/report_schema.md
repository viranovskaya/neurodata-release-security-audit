# Report contract

The JSON report is deterministic. It deliberately omits a generation timestamp and
the absolute dataset path.

Schema version 2 keeps the original findings and inspected/skipped lists, and adds
four release-wide records:

- `coverage` contains exactly one status for every filesystem entry encountered;
- `manifest` contains the size and SHA-256 digest of every readable regular file;
- `container_members` lists supported archive directory entries without extraction;
- `references` records supported cross-file links and their resolution status.

The scanner calculates the manifest again after metadata inspection. A changed or
unreadable file makes `manifest_recheck_passed` false and produces a review finding.
It also compares the complete release tree before and after the scan. Added, removed
or type-changed entries and changed symlink targets make
`release_tree_recheck_passed` false.
Hashing is a streaming integrity check. It does not parse EEG samples, image voxels
or DICOM pixels.

```json
{
  "schema_version": "2",
  "scanner_version": "0.2.0.dev0",
  "summary": {
    "files_inspected": 1,
    "files_skipped": 1,
    "entries_total": 3,
    "manifest_files": 2,
    "manifest_recheck_passed": true,
    "release_tree_recheck_passed": true,
    "container_members": 0,
    "references_checked": 0,
    "references_valid": 0,
    "fully_inspected_metadata": 1,
    "header_or_structure_only": 1,
    "payload_not_opened": 1,
    "unsupported_manual_review": 0,
    "not_traversed": 0,
    "findings_high": 0,
    "findings_review": 0,
    "findings_info": 0
  },
  "files_inspected": ["dataset_description.json"],
  "skipped_files": [
    {
      "path": "sub-01/eeg/sub-01_task-rest_eeg.eeg",
      "reason": "Signal or image payload is not parsed or loaded"
    }
  ],
  "coverage": [
    {
      "path": "dataset_description.json",
      "entry_type": "file",
      "status": "fully_inspected_metadata",
      "reason": "The complete text or structured metadata file was inspected"
    },
    {
      "path": "sub-01/eeg",
      "entry_type": "directory",
      "status": "header_or_structure_only",
      "reason": "Directory name and release-tree position were inspected"
    },
    {
      "path": "sub-01/eeg/sub-01_task-rest_eeg.eeg",
      "entry_type": "file",
      "status": "payload_not_opened",
      "reason": "Signal payload was hashed but not parsed or loaded"
    }
  ],
  "manifest": [
    {
      "path": "dataset_description.json",
      "size_bytes": 59,
      "sha256": "0000000000000000000000000000000000000000000000000000000000000000"
    },
    {
      "path": "sub-01/eeg/sub-01_task-rest_eeg.eeg",
      "size_bytes": 4096,
      "sha256": "1111111111111111111111111111111111111111111111111111111111111111"
    }
  ],
  "container_members": [],
  "references": [],
  "findings": []
}
```

Finding order is `severity`, `path`, `location`, then `code`. Coverage and manifest
entries are sorted by relative POSIX path.

`container_members` lists ZIP and TAR directory entries without extracting their
payloads. `references` records supported BrainVision, EEGLAB and BIDS JSON links,
including valid internal targets and visible failure states.

Relative filenames are retained for remediation. Known terms, contact details,
direct IDs, labelled dates, obvious credentials and detected local or network paths
are masked in release paths. Structured locations use stable placeholders for
arbitrary keys. Other identifying filename text may remain, so a report is not
automatically safe to publish.

The machine-readable contract is
[`schema/report.schema.json`](../schema/report.schema.json).
