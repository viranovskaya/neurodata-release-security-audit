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

## Administrator and participant files

The installed wheel is an administrator tool. It contains the validated private
specification and scoring code. Do not give the wheel, `spec.json` or the source
checkout to a reviewer.

Build a new participant bundle in an explicit directory:

```bash
neurodata-usability-build-bundle \
  --output-dir ./participant-bundle
```

Give the reviewer only:

- `participant-bundle/reports/`;
- `participant-bundle/reviewer_packet.md`;
- a fresh copy of `participant-bundle/response_template.json`.

The command refuses to reuse an existing directory. It never writes into the
installed package. Returned paths are resolved absolute paths, so macOS
`/var` and `/private/var` aliases do not create two identities for one output.
The bundle is checked for the private answer-key serialization and fingerprint
before the command returns.

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

Each critical task also has its own opaque report. Noncritical file, field and
remediation questions use separate report copies, so later prompts cannot reveal
the answer to an earlier critical task. The validator rejects any overlap.

Score complete response files:

```bash
neurodata-usability-score \
  responses/reviewer-01.json \
  responses/reviewer-02.json \
  --json results/result.json \
  --markdown results/result.md
```

The scorer always uses the packaged frozen specification; the public CLI has no
specification override. It rejects outputs inside the installed package and
refuses to replace either output. Both files are created using same-directory
temporary files and no-overwrite links.

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
