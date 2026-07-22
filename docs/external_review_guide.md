# External review guide

This review is about whether the tool is understandable and useful before an EEG dataset is shared. It is not a legal, privacy or security certification.

The first part uses synthetic files from the repository. The second part is optional and can use a public, synthetic or private local dataset. No data are uploaded.

## 1. Install

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install .
```

## 2. Run the synthetic demo

```bash
neurodata-security-audit scan examples/reviewer_demo \
  --sensitive-terms examples/demo_sensitive_terms.txt \
  --json reports/reviewer_demo.json \
  --markdown reports/reviewer_demo.md
```

The demo contains only invented values. The expected terminal summary is:

```text
inspected=5 skipped=2 high=6 review=4 info=0
```

Exit status `1` is expected because the demo deliberately contains high-severity findings.

Open `reports/reviewer_demo.md`. The report should identify:

- a contact email;
- a local computer path;
- two values from the private term list;
- an unexpected participant-key spreadsheet;
- a BrainVision source filename;
- a BrainVision recording timestamp.

The invented email, name, subject code, local path and timestamp should not be reproduced in full.

## 3. Optional check on another dataset

Run the same command on a dataset you already understand. A public or synthetic dataset is enough. If you use private data, keep the dataset, term list and reports on your own computer.

The useful question is not whether the report is empty. It is whether the tool points to the right files, explains why they need review and makes skipped coverage clear.

Do not send the dataset or a full report back for this review. A filename that was not matched by a rule may still be sensitive.

## 4. Feedback

Please return only these answers:

```text
Environment and Python version:

Did installation and the demo command work?

Was the terminal summary clear?

Which finding, message or severity was unclear or unhelpful?

Did the scanner miss something you expected it to flag?

Were skipped files easy to understand?

Would you use this as a final check before sharing an EEG dataset? Why or why not?
```

Please do not include participant information, private paths or unredacted report content in the response.
