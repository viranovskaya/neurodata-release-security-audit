# Check on a real MFF fixture

Date: 23 July 2026

The full MFF reader was checked with `EGI/test_egi.mff` from the public
`mne-tools/mne-testing-data` repository at commit
`33ef2a6f6345a1adf8764f8f63725f0ed9e4bb92`. The fixture is used by
MNE-Python's own EGI reader tests and was downloaded only to a temporary local
directory. It is not stored in this repository.

The v2 public-format manifest pins the complete directory with SHA-256
`3010213f89829b03e811be8e24fda3177fd1abedf59743887b3169fad833d666`.
The directory digest binds every relative path, directory entry, file size and
file hash. A symlink or special entry makes the fixture invalid.

The first run found a packaging gap. MNE 1.12.1 needs `defusedxml` to read MFF XML, but the project's `formats` extra installed only `mne[hdf5]`. The extra now declares `defusedxml>=0.7.1` directly.

The same run found a rule problem in `subject.xml`. MFF stores custom patient fields as a label in `<name>` and its value in `<data>`. The first XML pass treated every populated field label as a participant name. The reader now uses the label to classify the paired value instead. In this fixture, the populated patient ID is a review finding while empty first-name and last-name fields are not findings.

The current public-format run checks that:

- MNE opens the recording with `preload=False`;
- the scanner records the MFF directory as inspected;
- its bounded XML and text files remain part of the normal release-tree scan;
- two repeated reports are identical;
- the copied directory and original source still match the pinned hash.

The complete three-format smoke suite was:

```text
fixtures=3 passed=3 failed=0 unscored=0
```

The MFF finding codes were three recording dates, one populated patient ID, one
local path in a log and one unreadable macOS resource-fork XML file. The MFF
directory itself received `fully_inspected_metadata` coverage.

This is an integration check, not a privacy assessment of the MNE fixture. Finding counts are used only to confirm stable scanner behaviour and masking.

## Repeatability replay

On 3 August 2026, I rebuilt the wheel from commit
`f428bc4f7eede501ee5d0b002365c70d554ad871` and installed it in a fresh
Python 3.13 environment with MNE 1.12.1, nibabel 5.4.2 and pydicom 3.0.2.
The three source hashes matched the v2 manifest before the scan, including the
complete MFF directory hash above.

Two runs produced byte-identical reports and matched the checked-in v2 result:

```text
fixtures=3 passed=3 failed=0 unscored=0
JSON SHA-256: 7672ffe4a913573b0a6c0ed1b782a54230635584ce156787ee508e06921e541a
Markdown SHA-256: 314d2856bdff09ed76a9761b18659081b21816ee4e781b0e946bfeab03c87e5d
```

This replay confirms the pinned reader path and deterministic result. It is not
an independent privacy assessment and does not add privacy ground truth.
