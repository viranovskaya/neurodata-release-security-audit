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
