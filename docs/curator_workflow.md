# Curator review workflow

The audit remains read-only. This workflow helps a curator record decisions and
check a corrected release without changing research data.

## Checklist

Create a checklist from one JSON audit report:

```bash
neurodata-security-audit checklist reports/audit.json \
  --tsv review/audit-checklist.tsv
```

The checklist contains:

- every high- and review-severity finding;
- every unsupported or untraversed release entry;
- the relative file path and field or coverage location;
- the required next action;
- blank columns for the curator decision, notes, tool used, scientific check and
  completion status.

The checklist does not repeat detected evidence. Its stable item ID is calculated
from the already masked report record, and every row records the canonical
SHA-256 of the source report. Spreadsheet formula prefixes in report text are
neutralised. The command refuses to replace an existing checklist so a completed
review cannot be overwritten accidentally.

Use `curator_decision` for a short controlled decision such as `remove`,
`retain_with_justification` or `not_applicable`. Record the reason in
`decision_note`, the application and version in `tool_used`, the scientific
comparison in `scientific_check`, and set `completed` to `yes` only when that
review item is finished.

The checklist is a working record, not release clearance. A curator still needs
to review the original report and the corrected dataset with format-aware tools.

## Compare two audits

After making corrections on a private copy, scan the complete candidate again.
Then compare the baseline and current JSON reports:

```bash
neurodata-security-audit compare \
  reports/baseline.json reports/current.json \
  --confirm-same-dataset \
  --json review/comparison.json \
  --markdown review/comparison.md
```

Each review item is classified as:

- `new`: present only in the current report;
- `remaining`: unchanged between the two reports;
- `resolved`: present only in the baseline report.

Coverage gaps are compared alongside findings. The comparison runs only when
both reports passed their manifest and release-tree integrity rechecks. It also
refuses reports with different schema versions, empty release inventories or no
shared release paths. The shared-path check is not proof of dataset identity:
ordinary BIDS datasets often have the same filenames. The command therefore
requires `--confirm-same-dataset` as an explicit curator assertion. Check the
project or accession record before using it. The output records that assertion,
the path overlap, the canonical SHA-256 and scanner version of both reports, and
keeps the current release state visible.

A resolved item means that the scanner no longer reports the same masked record.
It does not prove that the correction preserved scientific content or that the
dataset is anonymous, compliant or ready to share.

Both commands refuse to replace an existing file. The comparison writes JSON
before Markdown. If the second write fails, the JSON file is left in place
rather than risking deletion of a file that another process may have replaced.
Inspect and remove that partial output yourself before retrying.
