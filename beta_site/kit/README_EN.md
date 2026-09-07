# NeuroData Release Security Audit — researcher beta {{VERSION}} · kit {{KIT_REVISION}}

This Python tool with a local browser interface checks neurodata release
structure and bounded metadata for privacy-relevant patterns. It creates reports
locally and does not upload or modify the dataset.

Plan approximately 20 minutes for installation; this is a practical estimate,
not measured timing. A scan of your own dataset may take longer depending on
the number, size, and formats of the files. This beta supports Python 3.10–3.13.
The full test suite runs on Python 3.10 and 3.13, and the installed wheel also
has a dedicated Python 3.12 smoke test.

## 1. Verify the download

Compare the archive SHA-256 with the value on the beta website. Run this
command in the folder containing the downloaded ZIP, or replace the filename
with its full path.

macOS:

```bash
shasum -a 256 {{ARCHIVE}}
```

Linux:

```bash
sha256sum {{ARCHIVE}}
```

Windows PowerShell:

```powershell
Get-FileHash .\{{ARCHIVE}} -Algorithm SHA256
```

Then unpack the ZIP and open a terminal in the unpacked beta folder for Steps
2–5. `SHA256SUMS.txt` provides hashes for every other file in the archive.

## 2. Create a separate Python environment

Open a terminal in the unpacked beta folder. All commands below assume that the
current folder contains `README_EN.md` and the wheel. Check the Python version
before creating the environment:

macOS or Linux:

```bash
python3 --version
```

Windows PowerShell:

```powershell
py --version
```

Use Python 3.10, 3.11, 3.12, or 3.13. The full CI test suite runs on Python
3.10 and 3.13. A separate installed-wheel smoke test runs on Python 3.12.

On macOS or Linux:

```bash
python3 -m venv neurodata-beta-env
source neurodata-beta-env/bin/activate
```

On Windows PowerShell:

```powershell
py -m venv neurodata-beta-env
.\neurodata-beta-env\Scripts\Activate.ps1
```

If PowerShell blocks activation, skip it and use the full environment paths in
the Windows commands below.

## 3. Install the wheel

Use one command that matches the files in your dataset.

On macOS or Linux, or in an activated Windows environment:

```bash
# Base: BIDS JSON/TSV/CSV, BrainVision, EDF/BDF, XLSX/DOCX, ZIP/TAR
python -m pip install ./{{WHEEL}}

# FIF, EEGLAB .set, KIT, MFF, MATLAB
python -m pip install -c CALIBRATION_READERS.txt "./{{WHEEL}}[formats]"

# NIfTI and DICOM
python -m pip install -c CALIBRATION_READERS.txt "./{{WHEEL}}[imaging]"

# Mixed releases
python -m pip install -c CALIBRATION_READERS.txt "./{{WHEEL}}[formats,imaging]"
```

On Windows without activating the environment:

```powershell
# Base: BIDS JSON/TSV/CSV, BrainVision, EDF/BDF, XLSX/DOCX, ZIP/TAR
.\neurodata-beta-env\Scripts\python.exe -m pip install .\{{WHEEL}}

# FIF, EEGLAB .set, KIT, MFF, MATLAB
.\neurodata-beta-env\Scripts\python.exe -m pip install -c .\CALIBRATION_READERS.txt ".\{{WHEEL}}[formats]"

# NIfTI and DICOM
.\neurodata-beta-env\Scripts\python.exe -m pip install -c .\CALIBRATION_READERS.txt ".\{{WHEEL}}[imaging]"

# Mixed releases
.\neurodata-beta-env\Scripts\python.exe -m pip install -c .\CALIBRATION_READERS.txt ".\{{WHEEL}}[formats,imaging]"
```

`CALIBRATION_READERS.txt` selects the direct optional-reader versions used in
CI. Transitive dependency versions may still vary by operating system and
Python version. Optional readers normally require internet access while pip
downloads their dependencies. The later dataset scan runs locally and does not
upload data.

Confirm the installed version on macOS, Linux, or in an activated Windows
environment:

```bash
neurodata-security-audit --version
```

On Windows without activation:

```powershell
.\neurodata-beta-env\Scripts\neurodata-security-audit.exe --version
```

It should print `{{VERSION}}`.

## 4. Scan an authorised dataset

Start the local desktop interface:

```bash
neurodata-security-audit ui
```

On Windows without activation:

```powershell
.\neurodata-beta-env\Scripts\neurodata-security-audit.exe ui
```

The browser opens a temporary page on `127.0.0.1`. Enter the full dataset path
and a separate, new report directory outside the dataset. Close the terminal
process with `Ctrl+C` when finished. On macOS, hold Option while right-clicking a
folder in Finder to copy its pathname. On Windows, Shift-right-click a folder and
choose **Copy as path**, then remove any surrounding quotation marks before
pasting the dataset or report-folder path.

If you maintain a private text file of known names or identifiers, the CLI also
supports `--sensitive-terms`; run `neurodata-security-audit scan --help`. This
option is not exposed in the local browser interface. Keep that file private.

## 5. Optional: run the synthetic demo

Use this smoke check if you do not have a suitable dataset at hand or want to
confirm the installation before scanning your own data. It is not required for
the beta. The included demo contains deliberately synthetic privacy-relevant
metadata and should return `HOLD` with exit status `1`. The command creates the
new `demo-reports` directory.

On macOS or Linux:

```bash
neurodata-security-audit scan examples/reviewer_demo \
  --json demo-reports/audit.json \
  --markdown demo-reports/audit.md \
  --html demo-reports/audit.html
```

On Windows PowerShell with the environment activated:

```powershell
neurodata-security-audit scan .\examples\reviewer_demo --json .\demo-reports\audit.json --markdown .\demo-reports\audit.md --html .\demo-reports\audit.html
```

On Windows without activation:

```powershell
.\neurodata-beta-env\Scripts\neurodata-security-audit.exe scan .\examples\reviewer_demo --json .\demo-reports\audit.json --markdown .\demo-reports\audit.md --html .\demo-reports\audit.html
```

Open `demo-reports/audit.html` in a browser. Do not treat the deliberate finding
as an installation failure. Reports are never overwritten; use a new folder such
as `demo-reports-2` for another run.

## Command exit status and report decision

The command exit status describes execution and high-priority findings. It is
not a release decision.

| Exit | CLI line | Meaning |
|---:|---|---|
| 2 | `STOP` | The scan, integrity check, or report writing failed. Do not use the report as a release decision. |
| 1 | `HOLD` | The scan completed and a high-priority finding requires review before release. |
| 0 | `NOT APPROVED` | The scan completed without a high-priority finding, but findings, coverage gaps, and format limits still require a human decision. |

The HTML report separately summarises the curator decision. It may display
`HOLD` for unresolved review findings or coverage gaps even when the command
exits with status 0. The local interface may describe the same situation as
`Review required`. These labels do not mean the scan failed, and exit status 0
is not approval to publish.

## Feedback and safety

Complete `FEEDBACK_EN.md` and send it to `agafonovadaria97@gmail.com`.

Do not send the dataset. Before sending logs or a report, remove usernames,
home-directory paths, dataset or participant identifiers, private project names,
and any other sensitive context. Share a report only after reviewing it manually.

This beta does not prove anonymity, estimate re-identification risk, approve a
release, or provide privacy, security, ethics, or legal certification.
