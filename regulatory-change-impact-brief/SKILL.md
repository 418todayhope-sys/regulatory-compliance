---
name: regulatory-change-impact-brief
description: Prepare scope, captures, authority, reconciled evidence, draft impacts and pending action/review requests for Quillhaven Academy's Article 50 review. Generate local review-ready drafts with detached version bindings; keep publication blocked while authority questions remain.
---

Read the repository assignment, original interview export, README and unchanged
snapshot.schema.json before running. Preserve those inputs. This implementation
supports Stages 01–07; it does not produce final compliance determinations.

Use Python 3.10+ and install dependencies with
`python3 -m pip install -r regulatory-change-impact-brief/requirements.txt`.
For a complete new run, read [workflow and recovery](references/workflow.md), then run
from the repository root:

```sh
python3 regulatory-change-impact-brief/scripts/workflow.py --reason "Refresh the review from current disclosed sources"
```

This command makes fresh live requests to all ten disclosed sources and runs all
seven stages against the newly generated Stage 02 snapshot. It preserves the prior
package under `deliverables/history/<old-run-id>/` and exclusively creates new snapshots,
source captures, frozen inputs and drafts under `deliverables/runs/<new-run-id>/`.
Previous files are never replaced. New repository-relative paths support relocation;
legacy absolute-reference snapshots remain byte-for-byte unchanged. Technical completion
is not publication or approval. Requests remain pending/unsent and blockers remain visible.

For review of the saved legacy package after relocation, use the separate read-only
[portable validation mechanism](references/portable-review.md). It maps recorded paths
to this checkout without editing snapshots or reaching into the old workspace.

For an offline assessment view that omits Google browser configuration, use
[public evidence export and validation](references/public-evidence.md). This is a
separate retained-extract mode; it never reports omitted original bytes as verified.
The original local package and strict validator remain unchanged.

For a failed/interrupted attempt, repair its reported cause and run:

```sh
python3 regulatory-change-impact-brief/scripts/workflow.py --retry-run run-<actual-failed-id> --reason "Describe the verified repair"
```

Each retry uses fresh IDs and source requests, preserves diagnostics/history and records
supersession in Stage 01. It never resumes partial files or substitutes old captures.
For a read-only integrity check use
`python3 regulatory-change-impact-brief/scripts/workflow.py --validate-run deliverables/runs/run-<actual-id>`.
The workflow reference documents locking, incomplete/corrupt evidence and failure limits.

Read [changed-input review](references/adaptability.md) before interpreting revised
register/context facts. EVIDENCE has no fixed row count; unreviewed operating changes
produce explicit blockers and undated review actions rather than stale conclusions.

Stage-specific commands remain available for isolated inspection/development; their
legacy defaults are not the complete-run entry point. Read the relevant conventions:
[scope](references/scope.md), [capture](references/capture.md),
[registers](references/registers.md), [authority](references/authority.md),
[reconciliation](references/reconciliation.md), [impacts](references/impact.md),
[actions](references/actions.md), [draft validation](references/publication.md).
Preserve role-specific draft reasoning and the limited Article 50(2) transition;
never turn source calendar dates into approved deadlines.

Full regression tests use controlled offline transports but require the private
original source fixtures, including the twelve omitted Google Sheets HTML responses.
Only in the complete private workspace, run from the repository root:
`PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s regulatory-change-impact-brief/tests`.
The public submission cannot reproduce that full suite from claim extracts.

For reproducible public offline checks, follow [SUBMISSION.md](../SUBMISSION.md).
From the repository root, change to the versioned export root and run:

```sh
cd assessment/omega-attempt-1-v1
PYTHONDONTWRITEBYTECODE=1 python3 -B regulatory-change-impact-brief/scripts/public_evidence.py --validate .
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s regulatory-change-impact-brief/tests -p test_public_evidence.py -v
```

These commands validate retained public evidence and run the public test suite;
the original-only test is skipped. They do not verify omitted original HTML bytes
or establish full-suite reproducibility. Tests use temporary copies, without live retrieval.

Keep business sources read-only. Do not run or script the stakeholder interview,
fabricate facts or approvals, activate policy, change approved deadlines, close
incidents, send official responses, or write to a production calendar. Legal and
Operations retain their decisions. Report scope as partial and capture as blocked,
never a completed review or approved publication.
