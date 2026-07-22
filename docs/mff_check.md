# Check on a real MFF fixture

Date: 23 July 2026

The full MFF reader was checked with `EGI/test_egi.mff` from the public `mne-tools/mne-testing-data` repository. The fixture is used by MNE-Python's own EGI reader tests and was downloaded only to a temporary local directory. It is not stored in this repository.

The first run found a packaging gap. MNE 1.12.1 needs `defusedxml` to read MFF XML, but the project's `formats` extra installed only `mne[hdf5]`. The extra now declares `defusedxml>=0.7.1` directly.

The same run found a rule problem in `subject.xml`. MFF stores custom patient fields as a label in `<name>` and its value in `<data>`. The first XML pass treated every populated field label as a participant name. The reader now uses the label to classify the paired value instead. In this fixture, the populated patient ID is a review finding while empty first-name and last-name fields are not findings.

The final run checks that:

- MNE opens the recording with `preload=False`;
- the scanner records the MFF directory as inspected;
- its bounded XML and text files remain part of the normal release-tree scan;
- two repeated reports are identical;
- hashes of every source file are unchanged.

The final summary was:

```text
inspected=11 skipped=5 high=0 review=6 info=0
```

The review findings were three recording dates, one populated patient ID, one local path in a log and one unreadable macOS resource-fork XML file. The MFF directory itself was inspected successfully and was not listed as skipped.

This is an integration check, not a privacy assessment of the MNE fixture. Finding counts are used only to confirm stable scanner behaviour and masking.
