# Stage 07: local draft validation

Run `python3 regulatory-change-impact-brief/scripts/publication.py` from the repository
root after Stage 06. It creates exactly three drafts and the Stage 07 snapshot.
Every target must be absent. `--destination /tmp/new-review-directory` permits isolated
generation. Use `--validate-only` to inspect actual existing bytes and every predecessor,
source evidence hash, reconstructed finding/action and detached request binding without
writing. A failure exits nonzero; it never silently repairs or rebinds damaged output.

The isolated command continues its selected run offline; it does not claim new live
source access. Complete [workflow orchestration](workflow.md) passes its freshly captured
run explicitly instead of selecting a historical capture. The assigned review date remains 2026-08-26. Draft bytes are deterministic
for the same validated input snapshots. Snapshot UUID and actual validation time are
fresh. Calendar DTSTAMP is the actual Stage 06 creation time in UTC, representing the
proposal version, rather than the historical assigned review date. Date-only proposals
are all-day DTSTART values; no DTEND or delivery-related calendar fields are emitted.
UIDs derive deterministically from organization/skill/action identity and stay stable
when an action's date changes. All events remain TENTATIVE and UNAPPROVED.

The CSV has exactly the ten requested columns and 64 Stage 05 findings. Semicolons
separate evidence IDs; the original state, reason and distinct rule/actor remain visible.
System-specific action links determine the owner/action/date fields. Multiple linked
actions have no single CSV date: their IDs/dates are disclosed in the reason and brief.
A single undated action also stays blank. Findings without a local action retain the
system owner and explain the pending Legal/global review. ACT-008 is not assigned as
an individual finding deadline. The brief lists every action and pending unsent
review request. The saved case has 17 actions (nine undated) and 43 requests;
changed-input review blockers can add undated actions and requests dynamically.

Final files are read back, inspected and hashed after writing. Every request's detached
binding in Stage 07 includes all three actual artifact paths/hashes, request/run/subject,
required reviewer, source versions and the exact Stage 06 basis. The brief references
these binding IDs, never its own hash. Revalidation compares bindings and source-derived
bytes, catching tampering even if an artifact hash alone is edited to match. A detached
hash manifest is an integrity check, not a signature or proof of approval. Later feedback
handling and authenticated delivery remain outside this command. History/supersession
and complete-run recovery are handled by [workflow orchestration](workflow.md). No feedback is fabricated or applied.

Technical file validation can pass while publication remains **blocked**. FAQ numbering,
historical guidance, POLICY live access/manual provenance and unresolved system evidence
still need human review. This stage creates a bounded review-ready DRAFT only: it sends
nothing, approves nothing, sets no operational deadline and activates no policy.

Focused tests: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s regulatory-change-impact-brief/tests -p test_publication.py`.
The calendar writer/parser supports the emitted RFC 5545 subset, not arbitrary imported
calendars: UTF-8, CRLF, 75-octet folding, escaped TEXT, UTC DTSTAMP, date-only DTSTART,
unique UIDs and required event properties. Tests cover empty calendars and multibyte text.
