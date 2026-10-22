# Stage 02 register extraction

Run the existing capture command with fresh destination/output paths, for example:

```sh
python3 regulatory-change-impact-brief/scripts/capture.py --config regulatory-change-impact-brief/references/source-config.json --destination 'deliverables/sources/<new-capture-name>' --output 'deliverables/snapshots/<new-capture-name>.json'
```

Replace the angle-bracket placeholders with unused names; this is a stage-specific
example, not the complete-run command. Original workbook URLs come from the interview. Each original is captured
before the configured read-only CSV exports. Export URLs are derived as
`https://docs.google.com/spreadsheets/d/<workbook-id>/export?format=csv&gid=<gid>`;
the source attempt retains original/requested/final URLs, actual UTC retrieval
time and completion time, content type, HTTP status, exact bytes and SHA-256.
No authentication is bypassed. HTTP or parsing failures retain raw evidence and
remain visible. Existing evidence/output paths are never reused.

The diagnosed exposed tabs are configured explicitly, not assumed from position:

| Register | Tab | gid | Rows in saved capture-004 |
| --- | --- | --- | --- |
| SYSTEMS | AI System Register | 0 | 8 |
| EVIDENCE | Incident Evidence Register | 0 | 10 |
| CALENDAR | Compliance Calendar | 0 | 8 |

`registers.py` extracts only Google HTML tables with the `waffle` class within
identified grid containers, ignoring interface/navigation tables and TH row/column
labels. It records all exposed grid/tab identities, including unexpected grids;
unconfigured grids are retained and flagged for review. Tab discovery is limited
to the exposed HTML and explicit configured gids. Hidden/unexposed tabs and a
complete workbook inventory are not established. Do not guess tab IDs or silently
ignore additional tables. Newly disclosed tabs require configuration/schema review
of their meaning, not blind concatenation into the diagnosed registers.

Each HTML/CSV extraction is retained as its own JSON artifact, bound to the raw
response hash/path, workbook ID, tab name/gid, retrieval URL/time, headers, record
IDs and source rows. Row numbers locate the header/data in the captured grid or
CSV (header row 1); column names locate individual values. The snapshot records
both raw and extracted artifact hashes. CSV tab names are configuration-bound;
the live HTML provides the corresponding observed tab caption when available.

Required headers must exist and be unique. Reordered columns and unrelated extra
columns are supported; field values are not normalized or rewritten. Record IDs
must be present and unique. EVIDENCE counts are variable. SYSTEMS retains the expected
eight-system scope and CALENDAR retains its eight-action contract; scope/count
errors preserve all captured rows and require review. Join checks use SYSTEMS.system_id;
CALENDAR's source-reported `ALL` is a workbook-wide action, not an invented system.
HTML and CSV must agree by record ID/field value; differing versions remain visible.

`state.register_validation` reports structural/relationship checks. Passing those
checks does not corroborate facts, prove approval, establish legal applicability,
or resolve missing/stale/conflicting/partial evidence. Register records and any
exception/approval notes are preserved verbatim. `state.system_ids` can now contain
source-reported identifiers with status `source-reported-unverified`; Stage 01
remains unchanged. Legal, live-policy-access and evidence-verification blockers
remain explicit. Stage 03 uses a separate [authority command](authority.md);
Stage 04 uses the separate [reconciliation command](reconciliation.md).
Stage 05 uses the separate [draft impact command](impact.md).
Stage 06 uses the separate [actions command](actions.md); Stage 07 uses [draft validation](publication.md); full runs use [workflow orchestration](workflow.md).

EVIDENCE row counts are variable, including zero and additional valid records. The
ten rows shown above describe the retained fixture, not a validation limit. See
[changed-input review](adaptability.md) for downstream treatment of additional facts.
