# Report usability pilot

This pilot asks whether a curator can use the report without help from the
developer. It does not test leak detection again.

The task set covers five practical questions:

- can this copy be released;
- which file and field need attention;
- what is the safe next step;
- which coverage gap still needs manual review;
- does an integrity failure make the finding list provisional.

The large-report case adds 121 review items. It checks whether one distinct
item can still be found among repeated rows.

## Run the pilot

Build the synthetic reports from the installed package:

```bash
python usability/build_reports.py
python usability/build_reviewer_packet.py
```

Give the reviewer only:

- `reports/`;
- `reviewer_packet.md`;
- a fresh copy of `response_template.json`.

Record one pseudonymous participant ID, the selected answer, elapsed seconds
and confidence from 1 to 5. Do not collect names, emails or free-text personal
details. The administrator assigns IDs in the form `reviewer-01`; the scorer
rejects other ID formats and any extra response fields.

Keep the task order fixed. Some reports are opened more than once, so elapsed
time is descriptive only: later answers may be faster because the reviewer has
already seen the report. The pass gate uses accuracy, not time.

The report and task names are deliberately opaque. Every critical task belongs
to a balanced choice group: the same prompt and choices are reused across
reports, and every choice is correct for at least one report. The specification
validator rejects an unbalanced critical group before any responses are
collected. Task order is also deliberately different from answer order. These
checks prevent the packet structure from revealing which critical answer is
expected.

Score complete response files:

```bash
python usability/score_responses.py \
  usability/responses/reviewer-01.json \
  usability/responses/reviewer-02.json \
  --json usability/results/result.json \
  --markdown usability/results/result.md
```

## Precommitted engineering gate

The result is complete only with at least five independent reviewers:

- at least 80% correct overall;
- at least 75% correct in every capability group;
- 100% correct on the balanced release and integrity tasks.

One wrong answer that could lead to release of a blocked copy fails the
critical gate. A good average cannot hide it.

These are practical engineering thresholds, not a validated psychometric
instrument. A passing pilot applies only to this report version, task set and
reviewer group. It is not a privacy, legal or usability certification.
