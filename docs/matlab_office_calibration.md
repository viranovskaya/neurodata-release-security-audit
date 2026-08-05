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

- Scanner source commit: `5393b4953d68aba4317abff6370df930c26d7c22`
- Package version: `0.2.1b1`
- Python: `3.13.7`
- SciPy: `1.18.0`
- h5py: `3.16.0`
- Office reader: Python standard-library ZIP and XML parsing
- Deterministic wheel SHA-256:
  `e64e6ef711305c2ea35fc25c136cbaa2eac18218d7a50d915d8c159139d088aa`

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

- JSON: `e7665f4eb32a5a83eeb37ec6b98c0619d4eafde3d149476e46c8e1e19d8db410`
- Markdown: `3066259ad2c39e568243b4ce266daf1a6f7b42ae1d719e6dc80da2791a8f317b`
- HTML: `74ed560b50884d2f357ad6cee9b8159e1397324e24b96d54a51f5eac156212c0`

The Markdown hash is unchanged from the earlier reader calibration. JSON and
HTML changed only because the scanner version is now `0.2.1b1`; two fresh runs
of the release wheel produced all three reports byte-for-byte identically.

## Boundary

This run shows that the selected real files complete deterministically and that
unsupported nested MATLAB content remains visible. It does not show that the
dataset is anonymous, that arbitrary MATLAB or Office variants are covered, or
that uninspected numeric arrays and embedded objects are safe to release.
