# Synthetic usability stress test

## Why I ran it

The first five-person pilot showed that the release decision was not always
clear, especially when a report had no automated finding but still contained
an unsupported file. My own walkthrough then showed a second problem: some
answer choices used internal wording that was harder to understand than the
report itself.

Before paying for another participant sample, I used a bounded synthetic check
to find obvious wording problems. This was a development tool, not a substitute
for human usability testing.

## Method

The check used separate low-reasoning model sessions with deliberately
inexperienced reading profiles. Each session received only:

- the participant-facing task text;
- the HTML reports shown in the study;
- a response format without the scoring key.

The sessions could not read the specification, tests, scoring code, previous
responses, aggregate results or Git history. They did not simulate real
scrolling, fatigue, accessibility needs or completion time.

The work had three bounded rounds:

1. an initial 30-session check of all 13 fixed-choice tasks;
2. a 10-session targeted check of the four weakest tasks, split evenly between
   `gpt-5.6-terra` and `gpt-5.6-sol`;
3. a fresh 10-session targeted check after the overlapping answer choices were
   rewritten, again split evenly between the two model families.

All sessions used the lowest available reasoning setting.

## Initial result

The first round produced:

- 371/390 correct fixed-choice answers (95.1%);
- 167/180 correct critical answers (92.8%);
- 23/30 sessions with all 13 fixed-choice answers correct.

The weakest tasks were:

| Task | Result | Main distinction |
|---|---:|---|
| task 1 | 26/30 | unsupported file versus general format review |
| task 3 | 27/30 | high finding versus invalid scan |
| task 10 | 27/30 | usable finding list versus release clearance |
| task 13 | 27/30 | filesystem entries versus inspected files |

The overall score was high, but the error pattern was useful. It showed that
the top of the report mixed three different questions:

- can the dataset be shared;
- did the dataset remain unchanged during the scan;
- can the finding list be used for the next review step.

## Changes

I changed the report so these decisions are shown separately.

- A coverage hold now says that a listed item still needs manual review.
- An integrity failure now says that the report is unreliable and must not be
  used for a release decision.
- The report states separately whether the finding list can be used for the
  next review step, and says that this is not permission to share.
- The inventory card now explains counts directly, for example:
  `3 total entries = 1 regular file + 2 folders`.

The first targeted retest still found overlap in the answer choices. For
example, both the clean-report option and the coverage-hold option could be
read as “continue reviewing.” I therefore rewrote the choices so that each one
describes one distinct reason:

- no listed file needs action, but general limits still need review;
- a listed high-priority finding needs correction;
- a listed file needs manual review;
- the scan is unreliable because the dataset changed.

## Final targeted result

| Measure | Before distinct choices | Final wording |
|---|---:|---:|
| Correct targeted answers | 31/40 (77.5%) | 37/40 (92.5%) |
| Sessions with all four answers correct | 7/10 | 9/10 |
| task 1 | 7/10 | 9/10 |
| task 3 | 7/10 | 9/10 |
| task 10 | 8/10 | 9/10 |
| task 13 | 9/10 | 10/10 |

In the final round, the only remaining errors came from the deliberately
negation-confused profile, which also marked the same three tasks as unclear.
The other nine sessions answered all four targeted tasks correctly.

## What this result means

The synthetic check found and helped remove overlapping wording. It supports
moving to the next human pilot without another round of model-based editing.

It does **not** show that:

- people will achieve the same accuracy;
- the interface is accessible;
- the task timing is realistic;
- the report has passed the precommitted human usability gate;
- the underlying audit proves anonymity, compliance or release safety.

Raw synthetic responses remain outside Git. They are not combined with
Prolific responses or expert-review evidence.

## Verification

The revised report generator and study specification are bound to commit
`656b848`. Its complete local test suite passed with 211 tests and three
expected optional-reader skips.

The web-pilot report hashes, task text, lint, local session flow and production
build were checked against the same source before this summary was added.

The next useful step is the second five-person human pilot with a fresh sample.
