# Usability study security boundary

The usability workflow has two roles.

## Administrator side

The installed wheel contains:

- the validated scoring and bundle-building code;
- the private `spec.json`, including expected answers and thresholds;
- a short administrator README.

The administrator keeps these files private. The scorer accepts only
administrator-assigned `reviewer-XX` identifiers and fixed answer, timing and
confidence fields. It rejects names, emails, free text, extra fields, non-finite
timing values and incomplete response sets. The public scorer CLI always uses
the packaged frozen specification and has no answer-key or threshold override.
Both output paths must be outside the installed package.

## Participant side

`neurodata-usability-build-bundle --output-dir PATH` creates a new external
directory containing only:

- ten synthetic HTML reports;
- `reviewer_packet.md`.

The destination must not already exist and must be outside the installed
package. The builder returns resolved absolute paths; this is intentional on
macOS, where `/var` and `/private/var` can identify the same directory.

The bundle contains no private specification, expected-answer field, serialized
answer map or answer-map SHA-256 fingerprint. The participant returns only a
completed Markdown packet. The administrator creates a separate pseudonymous
JSON response with `neurodata-usability-build-response`. Generated reports,
reviewer responses and scored results are not wheel package data.
The installed package is treated as read-only and is hashed before and after
the CLI integration test.

Scored JSON and Markdown files use no-overwrite links. If the second output
fails, rollback removes the first output only while it still shares a private
hard link retained by that invocation. The ownership link also prevents the
original inode from being recycled during a path substitution. A malicious
same-user process that can inspect and alter the private link remains outside
this tool's threat model.

## Remaining limits

These controls prevent accidental answer-key and personal-response leakage
through the packaged workflow. They do not stop a reviewer who receives the
administrator wheel or source checkout, and they do not turn the pilot into a
validated psychometric instrument. The minimum-five-participant and
critical-error gates remain engineering thresholds for this exact report and
task version.
