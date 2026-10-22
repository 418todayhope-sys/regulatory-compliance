# Stage 04 evidence reconciliation

Run from the repository root:

```sh
python3 regulatory-change-impact-brief/scripts/reconcile.py
```

The offline command reads Stage 03 and verifies the exact hash/ID/run chain back
through the selected Stage 02 and Stage 01, keeping the assigned 26 August 2026 review date.
It exclusively creates `deliverables/snapshots/04-evidence-reconciliation.json`.
`--authority` selects an alternate Stage 03; `--output` must be a fresh path.
No business sources are fetched or mutated, and no previous outputs are replaced.

Before reconciling, recheck raw and derived register hashes, reproduce extracted
rows from the raw bytes, and rerun header/count/ID/join/HTML–CSV agreement checks.
Corrupt evidence, altered source artifacts, unknown joins or inconsistent lineage
fail before output creation. Do not repair an earlier snapshot in this command.

All source records are retained without rewriting field values. The saved capture-004
case has eight SYSTEMS, ten EVIDENCE and eight CALENDAR records; EVIDENCE counts
are variable, while the eight-system/eight-action case contracts remain validated.
CSV provides canonical values only after
agreement with HTML; both provenances are retained, not counted as independent
evidence. Every row carries its original record ID, supplied row version (or null
if absent), source table/attempt IDs, workbook/tab/gid, row/column locator, retrieval
time and raw/derived hashes. Joins use exact `system_id`. CALENDAR `ALL` remains a
global source action; it is not a ninth system or silently duplicated per system.

The schema collections distinguish source facts (`system_facts`,
`incident_evidence`), supplemental manual policy context (`policy_controls`),
reported conflicts and unresolved evidence gaps. Additional collections retain
calendar source rows, inferred join/scoped observations and approval observations.
Missing, stale, conflicting, partial, unverified and not-applicable remain distinct.
`unknown` is classified as unverified without changing the raw value;
`not_applicable` is classified as not-applicable for that specific source field,
never as a global no-impact finding. `complete` describes a source-reported field,
not corroborated facts or legal compliance. No stale-date threshold is invented.

REC-003 and REC-008 remain conflicts; SYSTEMS' complete field for AI-003 does not
erase the REC-003 conflict. REC-005 stays stale. REC-009's visible-label report
and unchecked machine-readable provenance are separate facets. REC-010 remains a
draft exception request without authenticated Legal approval or supplied expiry.
Source calendar due dates/statuses remain unchanged and are not adopted deadlines,
approvals, new proposed actions or incident-closure decisions.

The user-supplied manual POLICY file is hash-checked and included as exact Markdown
sections with one-based inclusive line locators, claimed versions and original
manual provenance. Its acquisition time/retriever remain unknown. Supplemental
system paragraphs are referenced separately from register facts; they do not
overwrite notices, refresh stale evidence, settle conflicts or authorize an
exception. Later authoring dates do not change the assigned observation date.
The file is not labeled a live Notion success or enacted law.

The result stays blocked with all upstream unresolved observations retained,
including Legal applicability/timing questions and POLICY-access limits. Actual
underlying artifact verification and version-bound decisions remain with system
owners, Operations and Legal. Stage 05 uses the separate
[draft impact command](impact.md), followed by Stage 06's [actions command](actions.md).
Stage 07 uses [draft publication validation](publication.md); complete runs use
[workflow orchestration](workflow.md).
