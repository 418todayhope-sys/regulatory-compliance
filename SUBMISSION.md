# Omega Attempt 1 submission layout

`STAGING-ALLOWLIST.txt` lists exact repository-relative files proposed for staging;
it is an inventory, not an instruction to stage or publish. The three starter files
already tracked are retained. Private originals remain locally preserved and are
not authorized for publication by this document.

Required root paths are present: original `interviews/*.md`, the implementation,
references, dependencies and tests under `regulatory-change-impact-brief/`, and
`deliverables/impact-register.csv`, `deliverables/compliance-brief.md`,
`deliverables/action-calendar.ics`, `deliverables/snapshots/`, and
`deliverables/sources/`. The supplied `snapshot.schema.json` is unchanged.

The selected chain in `deliverables/snapshots/` is:
`01-scope.json` → **`02-source-capture-attempt-004.json`** →
`03-authority-and-timing.json` → `04-evidence-reconciliation.json` →
`05-impact-analysis.json` → `06-actions-and-approvals.json` →
`07-publication-validation.json`. Stage 03 explicitly selects attempt 004.
Canonical `02-source-capture.json` and attempts 002/003 are historical attempts.
No snapshot, historical hash or predecessor reference has been rewritten.

Twelve sensitive Google Sheets HTML responses are excluded from the allowlist.
Unchanged claim extracts are under
`deliverables/sources/public-claim-extracts-omega-attempt-1-v1/`.
Its `provenance.json` maps each copied extract/hash to the versioned export,
original response path/hash, attempt ledger, snapshot and extraction method.
Extracts are source-reported claims, **not original response bytes**. Their hashes
must never replace original response hashes. These new copies do not make strict
raw-evidence validation pass and are not automatically substituted by that validator.

## Offline validation

Use Python 3.10+ with the declared `jsonschema` dependency already installed.
From the repository root:

```sh
cd assessment/omega-attempt-1-v1
PYTHONDONTWRITEBYTECODE=1 python3 -B regulatory-change-impact-brief/scripts/public_evidence.py --validate . --expected-manifest-sha256 sha256:432ba633d74fd653c403f9860516d43b10a2877d0f6a874434a58ea2e71d1f88
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s regulatory-change-impact-brief/tests -p test_public_evidence.py -v
```

The immutable export is the public validation boundary. It checks retained file
hashes, selected snapshot bindings, claim provenance, reconstructed drafts and 43
pending unsent review bindings without private raw HTML or live requests. Tests
use temporary copies; one original-only test is skipped. Root duplicate artifacts
and copied extracts should match their export counterparts byte-for-byte; the
root extract map binds those copies separately. Do not add root extras to the
versioned export or rebaseline its manifest.

Full root regression tests, `portable.py`, strict stage validators and
`workflow.py --validate-run` need the twelve private originals and are not public
checkout validation commands. The implementation's end-to-end command, setup and
trade-offs are documented in the Skill and workflow reference; `workflow.py
--reason ...` and `--retry-run ...` retrieve live sources and write new outputs.
Do not use those commands for offline assessment.

## Preserved limitations and publication boundaries

Publication remains blocked. Original omitted HTML bytes cannot be verified from
extracts; three older configuration versions are unavailable. Historical retries
reuse a run ID. Manual-policy provenance, historical guidance suitability,
underlying corroboration, hidden tabs, human approvals, session-capture acceptance
and evaluator acceptance of extracts remain unresolved. The manifest is unsigned;
its trusted digest must be retained independently. Packaging does not repair these
historical limitations or claim new retrieval, approval or submission.

Exclude the twelve mapped original HTML paths, earlier assessment exports,
root `review-evidence/`, `.codex/`, `.entire/`, Python caches and private backups
from proposed staging. Keep all Entire refs private: the local Entire branch
contains sensitive captures. No all-branch or mirror publication is appropriate.
The Omega revision is committed locally; it has not been pushed or submitted.
the grading branch/revision and facilitator access still need confirmation.
