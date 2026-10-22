# Stage 06 actions and approvals

From the repository root:

```sh
python3 regulatory-change-impact-brief/scripts/actions.py
```

The offline command exclusively creates `deliverables/snapshots/06-actions-and-approvals.json`.
Use `--impact` to select Stage 05 and a new `--output` for another draft attempt.
It verifies Stage 05's exact predecessor/run bindings and reproduces its analysis
from the validated Stage 01–04 chain, raw/derived register data, legal citations
and manual-context sections. Existing snapshots/evidence are never replaced.
This command generates neither Stage 07 nor the final CSV/brief/calendar package.

ACT-001–ACT-008 retain their exact original source values, including action IDs,
owners, due dates, approval requirements, statuses and source versions. ACT-008
remains one ALL-scoped action. New `PROP-*` records have separate stable IDs,
proposed routing to recorded owners, no source action/version, and null dates.
No date is borrowed from a related source action or statutory transition.
Changed action identities/meanings or invalid dates fail before output; do not
guess that an old action profile still describes a newly worded business task.
Reordered input rows and legitimate date/owner/version changes are preserved.

Each proposal contains acceptance criteria, underlying impact/policy finding IDs,
legal citations, policy-rule IDs and source evidence references. The source action
title is retained alongside proposed review scope, without implying that it was
executed. All material supported/unresolved/conflicting findings require a targeted
system-specific proposal; the global review alone cannot hide an uncovered gap.
Source rows with complete evidence do not establish independent corroboration.

The saved capture-004 case yields eight source-dated and nine undated proposals;
changed facts can add undated proposals and review requests. Additional
work verifies AI-001/AI-006 facts, AI-003/AI-008 release/market entry, AI-004/AI-007
product interfaces/output scope, AI-008 disclosure and exception support, and live
POLICY access/manual provenance. Existing ACT-005 covers current AI-005 role,
release, biometric, output and market-entry facts without treating stale proof or
human review as resolution. ACT-007 stays owned by Legal; factual support for its
exception is proposed separately to Communications.

Approval boundaries remain distinct:

- Legal: actor/rule/use interpretation, authority/timing questions and exceptions.
- Operations: policy activation and operational dates/scheduling; automation closes no incident.
- System owners: scoped factual corrections and supporting artifacts.

Original `approval_required` values are copied, not overwritten by inferred review
gates. Additional Operations date review is explicitly separate from a source
action's Legal-review requirement. Factual requests give owners no authority to
approve statutory interpretations or deadlines. The global factual review names
the recorded system-owner roles, coordinated by the source Operations action.

All proposals and review requests stay pending: no actual version-bound feedback
is supplied/applied. `planned`, `open`, `blocked`, `scheduled` or even an isolated
source `approved` status is not an authenticated approval response. Every request
has an ID, subject system/action/impact, run/source versions, evidence, question,
required reviewer and the exact Stage 05 input hash/path. Delivery is `not-sent`;
feedback is null. No request is claimed to have reached a reviewer.

The review-input version context records captured source hashes/versions separately
from final-artifact review bindings. Those final paths/hashes are explicitly
`pending-stage-07`; there are no invented deliverables or self-referential hashes.
Future feedback would require the facilitator's verified channel and matching
identity/role/request/subject/version/time/outcome/reasons before application.
Feedback ingestion is not implemented by this request-preparation command.

Source dates remain unapproved proposals, evaluated in the fixed 26 August 2026
review context. Actual execution/retrieval time does not make them new deadlines or
automatically mark them overdue. All approved-operational-deadline values remain
null. Undated work requires Operations authorization before a date can be adopted.
Prior conflicts, gaps and authority/access questions remain in the unresolved
chain, with explicit owner/Legal/Operations escalation. Stage 07 uses [draft validation](publication.md); full runs use [workflow orchestration](workflow.md).
