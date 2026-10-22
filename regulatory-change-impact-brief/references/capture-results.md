# Live capture observations

The four retained attempts reuse Stage 01 run `run-fa0eba75-1dbf-4eac-9d23-830540ca5777`.
No earlier evidence or snapshots were replaced. The first two attempts described
below did not verify legal authority, operational facts, document versions or approval;
later document-identity and register-extraction checks are described separately.

The first attempt is retained at `deliverables/snapshots/02-source-capture.json`
with evidence under `deliverables/sources/capture-001/sources/`. It received HTTP
200 from all ten routes. Its classifier incorrectly appended SVG icon titles to
the document title, causing EUR-Lex navigation text "Log in" to mark OJ, AMEND
and CONSOLIDATED invalid. Those three classifications are a known technical
failure, not evidence that the original responses were login pages. The actual
bytes remain available. No conclusions should be based on that classification.

The title parser was corrected to retain only the first title and a regression
test added. The fresh follow-up attempt is retained at
`deliverables/snapshots/02-source-capture-attempt-002.json`, with evidence under
`deliverables/sources/capture-002/sources/`. All ten routes were attempted again.
OJ, AMEND and CONSOLIDATED returned HTTP 202 with no body and are invalid document
reads, with null content hashes/references. POLICY returned HTTP 200 with the
generic title "Notion" and is an invalid landing-shell response. LAW, TIME, FAQ,
SYSTEMS, EVIDENCE and CALENDAR returned HTTP 200 with plausible titles but remain
unverified. This follow-up was the capture result before the Stage 02 fallback
improvement; the first is retained
for provenance and potentially useful response bytes only.

Next owner: the source access operator must establish suitable legislative and
policy access through the disclosed routes; Legal must verify authority and
review-date suitability before dependent conclusions. Reattempting requires fresh
capture/output paths. Do not overwrite either recorded attempt.

## Original-first identity verification (capture-003)

The identity-verification implementation's result before register extraction is
`deliverables/snapshots/02-source-capture-attempt-003.json`, with fresh captures
and ledgers under `deliverables/sources/capture-003/sources/`. All ten original
routes were attempted. OJ, AMEND and CONSOLIDATED returned HTTP 200 with matching
visible identifiers and publication/consolidation versions, so no fallback was
needed in this live attempt. Controlled tests exercise failed originals followed
by successful official HTML alternatives and preservation of both attempts.

POLICY again returned a generic Notion shell (HTTP 200, invalid document read).
The user-disclosed manual reference is separately recorded with its hash and
claimed policy/context versions. Its original acquisition time/retriever are
unknown; it is not a live Notion success and does not clear the access blocker.
LAW, TIME, FAQ and the three company sheets remain unverified HTTP 200 responses.
Legal applicability remains blocked even though the three legislative document
identity/version checks now pass. All earlier captures remain unchanged.

## Register extraction and CSV capture (capture-004)

The current Stage 02 result is
`deliverables/snapshots/02-source-capture-attempt-004.json`, with fresh raw HTML,
CSV, attempt ledgers and six derived table artifacts under
`deliverables/sources/capture-004/sources/`. Each original disclosed URL was read
before its per-tab export. All three gid=0 CSV exports returned HTTP 200.

HTML-grid and CSV extractions agree: SYSTEMS has eight records AI-001–AI-008;
EVIDENCE has ten records REC-001–REC-010; CALENDAR has eight records ACT-001–ACT-008.
Required headers, unique IDs, diagnosed row counts and system_id relationships
passed. CALENDAR's ALL action remains an explicit workbook-wide source value.
Missing, stale, conflicting, partial and draft-exception states are preserved.
This verifies extraction and consistency, not independent corroboration or approval.
Only the exposed/configured gid=0 tabs are established; hidden-tab completeness
remains unknown. POLICY access and legal applicability remain blocked.

The snapshot passed the unchanged schema, predecessor/run/reference checks and
raw/derived hash checks. All 64 previously recorded captures and protected inputs
were verified unchanged against a pre-change hash baseline. No prior snapshots
or evidence were replaced.
