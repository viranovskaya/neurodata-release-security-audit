# Prolific pilot 1 results

I ran a small web pilot to check whether the report communicated the intended
release decision and made the supporting evidence easy to find.

## What was tested

- 5 complete participants
- 10 reports built from synthetic metadata
- 13 fixed-choice questions per participant
- 65 answers in total

The analysis used a private pseudonymous export. It contained numbered study
slots, answers, confidence and task time, but no Prolific IDs, session IDs or
stored identifier hashes. Row-level responses are not published.

## Main result

Participants answered 55 of 65 questions correctly: **84.6%**.

| Task | Report | Correct | Result |
|---|---|---:|---:|
| 01 | C | 1/5 | 20% |
| 02 | A | 4/5 | 80% |
| 03 | D | 3/5 | 60% |
| 04 | B | 4/5 | 80% |
| 05 | E | 5/5 | 100% |
| 06 | E | 5/5 | 100% |
| 07 | E | 5/5 | 100% |
| 08 | F | 4/5 | 80% |
| 09 | H | 5/5 | 100% |
| 10 | G | 5/5 | 100% |
| 11 | I | 5/5 | 100% |
| 12 | I | 5/5 | 100% |
| 13 | J | 4/5 | 80% |

Seven tasks reached 5/5. Four reached 4/5. The two clear problems were Report C
and, to a lesser extent, Report D.

## Gate result

**Pilot 1 did not pass the precommitted engineering gate.**

The overall score was above 80%, but the critical release and integrity
decisions were not unanimous. Report C reached 1/5 and Report D reached 3/5.
The gate does not allow a good average on other tasks to compensate for a wrong
decision that could release a blocked copy or treat provisional findings as
stable.

## What the pilot found

Report C was the main usability failure. The generated copy shown in the first
pilot did not say clearly enough that the release should remain on hold while an
unsupported entry was reviewed. Only one participant selected the intended
decision.

Report D also needed clearer wording around an integrity failure. Three of five
participants identified that its findings were provisional.

The more concrete evidence-location and correction tasks worked well. This
suggests that people could usually find a named file, field or next action once
the report stated the release status clearly.

One participant completed the tasks in under 15 minutes. Excluding that
participant gave 43/52 correct answers (**82.7%**), so the conclusion did not
change. The study did not monitor external tool use, so speed alone is not
treated as evidence of AI use or invalid participation.

## Changes made after pilot 1

- regenerated all reports from the current audit code;
- made Report C explicitly say that the release remains on hold;
- made Report D explicitly say not to rely on provisional findings;
- added one short-answer question asking why Report C remains on hold;
- separated that explanation from the fixed-choice accuracy gate;
- added server-side question order, safe retry and completion recovery checks;
- added a repeatable local integration test with a fresh temporary database.

The corrected reports and study flow have passed the local test suite and a
separate read-only review. They have **not** yet been tested with a second
participant sample.

## Limits

This was a five-person usability pilot, not an efficacy study. Multiple-choice
answers can overestimate unaided understanding, and the sample is too small for
population-level inference. The result supports report revision and a second
pilot; it does not establish anonymity, legal compliance, scientific validity
or security certification.
