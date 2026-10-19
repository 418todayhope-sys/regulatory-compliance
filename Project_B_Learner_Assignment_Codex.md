# Project B — Regulatory Change Impact & Compliance Actions — Learner assignment

> Faithful formatting copy of the uploaded text; final-deliverables table reconstructed for readability. Original text file is preserved separately.

Skip to content

<#main>
Project B — Regulatory Change Impact & Compliance Actions — Learner
assignment

Get Notion free


  Project B — Regulatory Change Impact & Compliance Actions — Learner assignment


      Scenario

You are an automation specialist at Quillhaven Academy. Its Compliance and Operations Manager needs repeatable help preparing an evidence-backed review of AI use against EU AI Act Article 50 for Legal and Operations. The assigned review date is 26 August 2026; record actual source retrieval times separately.


      Your task

Interview the stakeholder, then build and execute an Agent Skills-compliant skill named regulatory-change-impact-brief
. It must read the current disclosed company sources and obtain the required official online legal sources on every run, producing a consistent review-ready draft package. Discover the business workflow, source meanings, applicable rules and review requirements through the interview and supplied sources. Explain your automation choices and their trade-offs.
Document one end-to-end command, its runtime, dependencies and setup. Use any suitable implementation language or maintained libraries. Keep the work read-only: do not expose credentials, alter sources, give final legal advice, activate policy, change approved deadlines, close incidents, send official responses or write to a production calendar. Legal and Operations retain their decisions.


      Deliverables

Interview records — interviews/*.md
. Include the original Work Sim Markdown export for every interview session, with its session metadata and complete participant-visible messages. Keep one final complete export per session without rewriting or summarizing it. Commit and push these files in the submitted code revision and ensure the facilitator can read them. Coding-session capture remains a separate requirement. If the export is unavailable, contact the facilitator; do not manufacture a replacement.
The starter supplies its entry README and unchanged snapshot.schema.json <https://github.com/GitRollTraining/regulatory-compliance/blob/main/snapshot.schema.json>. Create the Skill and these outputs; the tree describes your completed repository, not supplied implementation:
interviews/
└── <original-export-filename>.md
regulatory-change-impact-brief/
├── SKILL.md
├── scripts/
└── references/
deliverables/
├── sources/
├── snapshots/
│   ├── 01-scope.json
│   ├── 02-source-capture.json
│   ├── 03-authority-and-timing.json
│   ├── 04-evidence-reconciliation.json
│   ├── 05-impact-analysis.json
│   ├── 06-actions-and-approvals.json
│   └── 07-publication-validation.json
├── impact-register.csv
├── compliance-brief.md
└── action-calendar.ics
​
Snapshots and captured sources. Write each snapshot at its corresponding boundary, conforming to the supplied schema. All seven share a run_id
; from stage 02, predecessor
 identifies and hashes the immediately preceding snapshot. Each record has an id
, meaningful summary
, evidence_ids
 and the actual values needed downstream. consumed_record_ids
 resolves to available upstream records; produced_record_ids
 identifies records present in that stage. Keep source, rule, decision and artifact references traceable across the chain.
Stage 02 records every source attempt, including failed and unused attempts: original URL/locator, content type, actual retrieval time, version, retrieval status, local evidence path and content hash. Preserve the bytes or permitted claim-bearing extracts actually used in deliverables/sources/
, with section/paragraph/tab/row locators. Record null content/hash when no content was obtained. A link or hash alone is insufficient; external pages are not fetched during assessment. Verify the returned document's identity, version and suitability for the review date; a login or landing page is not the requested document. Accept interview-disclosed source routes as runtime inputs. Retrieve current company sources and the interview-disclosed official legal routes each run, retaining unsuccessful or unsuitable reads. Do not replace a failed live read with an undisclosed local copy.
Use the schema's states: run complete/partial/blocked/failed
; retrieval retrieved/unavailable/invalid/unverified/stale
; impact supported-impact/supported-no-impact/conflicting/unresolved
; approval pending/approved/rejected/not-required
. Preserve unresolved or conflicting records, their source basis, reason, known owner and resolution need until evidence or an actual decision changes them. Required collections may be empty. Preserve actual field values, source revisions and effective dates separately from retrieval time; do not silently change the assigned review date.
Final drafts. Use stable identifiers and matching source/run references throughout:

| File | Required content and format |
| --- | --- |
| `impact-register.csv` | UTF-8 CSV with a header and one row per distinct system/rule impact or unresolved item. Columns: `impact_id`, `system_id`, `rule_ref`, `state`, `evidence_ids`, `reason`, `owner`, `proposed_action`, `proposed_due_date`, `approval_status`. Evidence IDs may be semicolon-separated; extra columns are allowed. Unknown/inapplicable owner, action or date may be blank with the reason and resolution need disclosed. Known dates use `YYYY-MM-DD`. Keep different rule bases identifiable. |
| `compliance-brief.md` | Run ID, as-of date, recipients, draft/run status, source quality and limitations, supported observations, conflicts/unresolved scope, proposed actions/dates and decisions requested from Legal/Operations. Cite impact/action/evidence IDs and distinguish the scope of each conclusion. |
| `action-calendar.ics` | RFC 5545 VCALENDAR with `VERSION` and `PRODID`. Events require stable action-linked `UID`, `DTSTAMP`, `DTSTART`, `SUMMARY`, and `DESCRIPTION` containing action/system IDs, responsible role, source/decision basis and approval status. Proposed events use `STATUS:TENTATIVE`. Date-only inputs use all-day DATE values; any `DTEND` is exclusive. Omit undated events and explain them in the register/brief. An empty valid calendar is required when no dated proposal is supportable. |

Stage 07 records exact final file paths/hashes and checks cross-file agreement against stage 06 after writing. Its publication state describes draft validation, not a human approval or external publication. A bounded partial draft may be internally consistent; do not label an unresolved authority blocker as normal validated publication. When required legal authority is unavailable or unsuitable, withhold dependent formal conclusions and preserve a blocked/unresolved chain, register and brief with an empty or limited calendar. Explain whether other unsupported inputs require whole-run deferral or permit useful unaffected work, and keep that choice consistent across outputs. Missing facts must remain visible; do not manufacture evidence or approval to complete a package.
Review evidence. Each project decision records its concern, options, source basis, chosen behavior, rationale, trade-offs and downstream effect. Prepare review requests in the brief/stage 06 with request ID, subject system/impact/action, run/source version, evidence, question and required reviewer. Stage 07 binds each request to the reviewed final draft's path and exact hash. Refer to this detached binding from the brief rather than putting the brief's own hash inside it. If actual feedback is supplied through the facilitator's verified channel, retain response identity, role, subject/request/version, time, outcome and reasons/conditions. Validate that binding before applying it; leave unmatched responses unresolved. Do not simulate replies or claim an unsent request reached a reviewer. The endpoint is a review-ready draft.
Changed inputs and recovery. Accept reordered source rows/headers, unrelated extra columns and legitimate newer date/version values while preserving required fields, stable IDs and their disclosed meanings. Report missing/ambiguous required fields, conflicting identities, invalid values or unsuitable responses; do not guess renamed fields or changed business meanings. Format compatibility does not establish legal applicability or change the review date.
Before replacing outputs, retain the previous run, captures and drafts under deliverables/history/<old-run-id>/
. Each retry uses new run/snapshot IDs. Stage 01 records supersedes_run_id
 and the change/retry reason; it may be null/absent on the first run. Keep version relationships explicit and predecessor links within one run. Preserve only history actually available, recording pre-existing missing/corrupt evidence honestly.
Recompute affected work from its earliest changed basis and update all dependent drafts. Even when inputs are unchanged, inspect the actual seven snapshots, record/run/hash bindings, required source evidence and three final files before reporting success. Repair missing, damaged or stale outputs and revalidate them, or return an explicit incomplete/failure result. Retain technical failures with the affected stage/source/output and recovery action or next owner. Retry the documented command with fresh required source attempts after repair; retain the failed occurrence and prior evidence. An old successful bundle cannot stand in for the current result, and recovery cannot invent resolved facts or approvals.


      Interview

Open the Compliance and Operations Manager interview <https://work-sim.catalyte.ai/s/project-b-regulatory-compliance>. Ask concrete business questions and follow up to obtain relevant source routes, field meanings, business criteria, uncertainty and review boundaries. Ordinary business wording is sufficient; you do not need to guess filenames. Report missing required knowledge or source access to the facilitator.
Interview rule. You conduct the stakeholder interview yourself, and the questions are yours. Do not connect a coding agent or any other AI to the interview to run, script, or automate it. The interview transcript is assessed together with the code; a project whose interview was run by an agent is not scored.
Use the existing course setup and session-capture guide. Before assessed work, have the facilitator verify your identity, interview recording/export, coding-session capture, runtime/source access and submission destination. Keep attributable project decisions and expected-versus-observed review in that actual capture. Do not manufacture transcripts or substitute an agent-written account for the recorded work.


      Submit

