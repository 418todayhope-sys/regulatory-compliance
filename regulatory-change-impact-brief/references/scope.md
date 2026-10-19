# Stage 01 conventions

The assigned review date is 2026-08-26. `as_of` represents that date as
`2026-08-26T00:00:00Z`, a UTC calendar-date anchor, not an assertion that operational
facts were observed at that instant. `created_at` is the actual UTC generation
time. Source retrieval times are not generated in Stage 01.

Assignment scenario/task and interview statements establish the intended scope:
the EU programme team in Dublin, eight expected systems, Legal and Operations
audiences. SYSTEMS has not been read. `systems_in_scope` is therefore a descriptive
scope statement (required nonempty by the public schema), not a list of invented
IDs. `system_ids` remains empty and its verification status explicit.

Evidence records retain repository-relative paths, exact-file SHA-256 hashes and
locators. These are local assignment/interview evidence, not Stage 02 source
captures. Local export completeness and stakeholder statements are not independently
certified. Decisions record options, rationale, trade-offs and downstream effects.

The command requires the original interview filename currently supplied in this
repository. Missing input or invalid schema/output fails before output creation.
UUID4 run/snapshot identifiers are fresh on every invocation. Existing outputs are
never overwritten; full history/recovery is handled by [workflow orchestration](workflow.md). This command emits
Stage 01 only; separate commands support Stages 02–07.
