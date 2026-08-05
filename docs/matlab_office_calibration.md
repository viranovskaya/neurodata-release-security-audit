# MATLAB and Office calibration

I used one fixed public GIN snapshot to check the bounded MATLAB, XLSX and DOCX
paths on real files. This is a format and reproducibility check, not a privacy
clearance or a representative study of public datasets.

## Fixed source

- Repository: G-Node visual mismatch negativity dataset
- Dataset DOI: <https://doi.gin.g-node.org/10.12751/g-node.ejwq1y/>
- Publication: <https://doi.org/10.1162/jocn_a_02099>
- Source branch and commit: `master`, `be380b9e`
- Download-manifest SHA-256:
  `a67173abec5efe7c431bf4470dbcee84695136e22820029e14aa66bc0240dd21`
- Fixed input: 25 files and 250,506,424 bytes
- Format mix: 20 MAT, one XLSX, one DOCX and three bounded text files

The download manifest contains dataset-relative paths, byte sizes, source URLs
and file SHA-256 values. It remains in the private audit evidence because the
public repository does not need a second file-level copy of the source index.

## Scanner environment

- Scanner source commit: `b508db855212cac631c86cc117e2bb17a787821c`
- Package version: `0.2.1.dev0`
- Python: `3.13.7`
- SciPy: `1.18.0`
- h5py: `3.16.0`
- Office reader: Python standard-library ZIP and XML parsing
- Deterministic wheel SHA-256:
  `0c16d6e212afed3111020bdcdd120b21f77d3eb5180f0bbe5c7f62bbe87ef241`

The source commit includes the bounded MATLAB and Office readers plus the
first-run report wording and HTML legend. The readers prevent Office
relationship and HDF5 variable names from appearing raw in finding locations
and apply the same file-level budget to classic and HDF5 MATLAB text: at most
10,000 total elements and 100 variables are loaded. HDF5 text is additionally
limited to 64 KiB of encoded dataset storage per file.

## Result

Two fresh runs produced identical JSON, Markdown and HTML reports:

- 25 entries and 25 manifest files
- 25 inspected and 0 skipped
- 0 high findings
- 20 review findings
- both integrity rechecks passed

The exact installed wheel passed 210 copied functional tests outside the source
checkout on both Python 3.10 and Python 3.13. Two controlled wheel builds were
byte-identical.

Every review finding was an explicit `MATLAB_METADATA_COVERAGE_LIMIT` for a
nested classic MATLAB structure. The scanner did not load those structures or
their numeric arrays.

Report SHA-256 values:

- JSON: `6868b82eff8e4cbef87ff90cb9f8de5eacfa870f1b3e1d8b958306b3242ac407`
- Markdown: `3066259ad2c39e568243b4ce266daf1a6f7b42ae1d719e6dc80da2791a8f317b`
- HTML: `dafed9e14f91da4dad9c894ba6800cd5dc65aee4fea1ad1d6fe3fb88fbf3817e`

The JSON and Markdown hashes are unchanged from the earlier reader calibration.
The HTML hash changed because this commit changes the shared report renderer;
two fresh runs of the commit produced the new HTML byte-for-byte identically.

## Boundary

This run shows that the selected real files complete deterministically and that
unsupported nested MATLAB content remains visible. It does not show that the
dataset is anonymous, that arbitrary MATLAB or Office variants are covered, or
that uninspected numeric arrays and embedded objects are safe to release.
