# Stage 02 capture conventions

`--config` names a JSON runtime configuration containing the original interview
path and exactly ten source names mapped to schema role classifications. The
command extracts each exact HTTPS URL from that original Markdown at runtime,
rejecting missing/ambiguous routes or an interview hash different from Stage 01.
It never imports an undisclosed local business-source copy. Role classifications
describe intended use; authority remains unknown pending document verification.

The configuration also declares exactly these official same-document HTML routes:

| Source | Official fallback |
| --- | --- |
| OJ | https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=OJ:L_202401689 |
| AMEND | https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=OJ:L_202601744 |
| CONSOLIDATED | https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:02024R1689-20260727 |

These format alternatives were identified in the retained EUR-Lex pages and the
read-only access investigation. They do not replace the disclosed locators.
Attempt the original first; use the fallback only when its document identity and
version have not been verified. Configuration rejects other fallback routes.
Each attempt has a distinct record ID, numbered response/ledger filenames,
original URL, requested URL, final response URL, HTTP status and timestamps.
`state.sources` contains every attempt, not one summary per source.
`selected_verified_documents` identifies the matching legal response, if any.

Every invocation into a fresh destination attempts all ten routes, bypassing
application caching. No authentication is supplied or bypassed. Exact returned
bytes, including unsuitable error/login responses, are retained under the capture
directory's `sources/`, with an attempt JSON ledger for each route. Network errors
without a complete response have null content hash/reference. Transport captures
are limited to 8 MiB plus one detection byte; oversized responses are invalid and
their retained prefix is explicitly described. All files use exclusive creation.

`retrieved_at` is the actual UTC request-start time; `completed_at` is response or
failure completion. HTTP status, final URL, content type, observed HTML title,
ETag and Last-Modified are recorded when present. HTTP validators are not legal
versions/effective dates. Effective dates remain null. The original review date is inherited.

HTTP 200 alone is `unverified`, never a successful verified document read. Known
login/challenge/landing indicators, non-200, empty or oversized responses are
`invalid`. Unknown landing pages may remain `unverified`. Only OJ, AMEND and
CONSOLIDATED can be marked `retrieved` by the bounded legal identity matcher:
HTTPS EUR-Lex origin, visible regulation heading and Article 1, and the expected
publication/adoption dates (OJ/AMEND) or consolidated identifier/date/version.
Script/style content is excluded from these checks. OJ identifies 32024R1689,
13 June 2024 / 12 July 2024; AMEND identifies 32026R1744, 8 July 2026 / 24 July
2026; CONSOLIDATED identifies 02024R1689-20260727 with its printed version suffix.
These are document-identity checks, not independent legal authentication, full
completeness checks, effective-date interpretation or applicability analysis.
The consolidated reference is not itself an authentic legislative act.
No legal applicability, system facts or approvals are inferred.
Legal authority stays explicitly blocked. Prior Stage 01 uncertainty is preserved.

The user-disclosed `manual_policy_reference` is recorded separately under
`state.manual_references`, never in the live-attempt array or as a successful
Notion retrieval. Preserve its repository path/hash, claimed policy/context
versions and the time provenance was recorded. Original acquisition time and
retriever are unknown and recorded as null, not guessed from business or authoring
dates. The file is neither rewritten nor copied over live evidence. Its contents
are not used to manufacture system facts or approvals. Manual provenance remains
unverified and live POLICY access remains explicitly unresolved.

Default output: `deliverables/snapshots/02-source-capture.json`. The CLI requires
a fresh destination beneath `deliverables/sources/`; it refuses existing snapshots
before network access. Attempt ledgers and captures survive a later validation or
write failure. A failed or interrupted capture is not a completed Stage 02 result.
Full history and full-run retries are outside this command. Stage 03 has a separate
offline [authority command](authority.md), followed by the Stage 04
[reconciliation command](reconciliation.md) and Stage 05 [draft impact command](impact.md);
Stage 06 uses the separate [actions command](actions.md); Stage 07 uses [draft validation](publication.md); full runs use [workflow orchestration](workflow.md).
Review retained responses before using any claims; response
byte locators are transport provenance, not yet section/tab/row claim locators.

Register-specific row/column locators, raw/derived hashes, HTML-grid extraction,
explicit per-tab CSV capture and structural checks are documented in
[register conventions](registers.md). Other source formats still require later
claim-specific extraction before analysis.

See [recorded live results](capture-results.md) for the retained first-attempt
classification defect and the corrected, freshly retrieved follow-up result.
