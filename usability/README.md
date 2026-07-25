# Report usability pilot

This pilot asks whether a curator can use the report without help from the
developer. It does not test leak detection again.

The task set covers five practical questions:

- can this copy be released;
- which file and field need attention;
- what is the safe next step;
- which coverage gap still needs manual review;
- does an integrity failure make the finding list provisional.

The large-report case adds 124 review items. It checks whether one distinct
item can still be found among repeated rows.

One inventory task checks that the summary count is understood correctly:
files and folders accounted for is the number of filesystem entries in the
release tree, while the SHA-256 manifest contains regular files only.

## Administrator and participant files

The installed wheel is an administrator tool. It contains the validated private
specification and scoring code. Do not give the wheel, `spec.json` or the source
checkout to a reviewer.

Build a separate participant bundle for each reviewer:

```bash
neurodata-usability-build-bundle \
  --output-dir ./participant-bundle-01
```

Give the reviewer that complete folder. It contains only:

- `reports/`;
- `reviewer_packet.md`.

The command refuses to reuse an existing directory. It never writes into the
installed package. Returned paths are resolved absolute paths, so macOS
`/var` and `/private/var` aliases do not create two identities for one output.
The bundle is checked for the private answer-key serialization and fingerprint
before the command returns.

Ask the reviewer to mark the Markdown packet and return that file. Do not ask
them to edit JSON. After the packet is returned, create the administrator
response file:

```bash
neurodata-usability-build-response \
  --participant-id reviewer-01 \
  --output responses/reviewer-01.json
```

Transcribe only the selected answer, elapsed seconds and confidence from 1 to
5. Do not collect names, emails or free-text personal details. The scorer
rejects other ID formats and any extra response fields.

Keep the task order fixed. Every report file is different, but some related
questions use the same report. Elapsed time is descriptive only: later answers
may be faster because the reviewer has already seen the report. The pass gate
uses accuracy, not time.

## Reviewer group

Use at least five independent reviewers who did not develop the report. The
intended group is research-data staff, neurodata curators or researchers who
have prepared EEG, MEG, MRI or related research data for sharing. They should
be comfortable opening local HTML files and editing the supplied `.md`
checklist in a plain-text editor.

Use a current desktop or laptop version of Chrome, Firefox or Safari. Mobile is
not part of this pilot. Use a Markdown-capable editor that keeps relative links
clickable. Before handing over the folder, confirm that every report link opens.
Record the browser and editor versions with the administrative study notes.

Tell reviewers not to move or rename `reviewer_packet.md`. Do not guide them
while they complete the tasks; collect questions after they return the packet.

The report and task names are deliberately opaque. Every critical task belongs
to a balanced choice group: the same prompt and choices are reused across
reports, and every choice is correct for at least one report. The specification
validator rejects an unbalanced critical group before any responses are
collected. Task order is also deliberately different from answer order. These
checks prevent the packet structure from revealing which critical answer is
expected.

Each critical task also has its own opaque report. Noncritical questions may
share a report with one another, but they never reuse a critical report, so a
later prompt cannot reveal an earlier critical answer. The validator rejects
any overlap.

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
