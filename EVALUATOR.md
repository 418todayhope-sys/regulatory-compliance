# Project B: offline evaluator entry point

For the repository-root submission layout and precise staging inventory, read
[SUBMISSION.md](SUBMISSION.md). From the repository root, first change directory
to `assessment/omega-attempt-1-v1/` before executing the commands below. The
versioned export retains its own unchanged evaluator guide.

Run the commands below from the **exported package root**, where
`public-evidence.json` is located. This is a retained-evidence view of an existing
blocked draft, not a fresh source retrieval or approved compliance determination.

Use Python 3.10+ with `jsonschema>=4.10.3,<5` already installed (see
`regulatory-change-impact-brief/requirements.txt`). Dependency installation needs
an available package source; it is not part of offline validation.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B regulatory-change-impact-brief/scripts/public_evidence.py --validate .
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s regulatory-change-impact-brief/tests -p test_public_evidence.py -v
```

The first command verifies the manifest inventory, retained hashes, schema,
selected snapshot chain, extracts, reconstructed drafts and detached review
bindings without network access or writes. The tests use temporary fixture copies;
original-only validation is skipped when omitted HTML is unavailable. To bind the
manifest to an independently supplied digest, append
`--expected-manifest-sha256 sha256:<trusted-digest>` to the first command.

The selected chain is under `deliverables/snapshots/`:

1. `01-scope.json`
2. **`02-source-capture-attempt-004.json`**
3. `03-authority-and-timing.json`
4. `04-evidence-reconciliation.json`
5. `05-impact-analysis.json`
6. `06-actions-and-approvals.json`
7. `07-publication-validation.json`

Stage 03's predecessor identifies attempt 004. The canonical
`02-source-capture.json` and attempts 002/003 are preserved earlier attempts, not
the input to this downstream chain. Absolute references beginning with
`/home/maxg/regulatory-compliance` are historical logical paths; the public
validator maps them into this package without consulting the original workspace.

Required drafts are `deliverables/impact-register.csv` (64 findings),
`deliverables/compliance-brief.md`, and `deliverables/action-calendar.ics` (eight
tentative events). Original interview Markdown is under `interviews/`; the supplied
schema and assignment are at the root. Sources, attempt ledgers and tables are
under `deliverables/sources/`, permitted claim extracts under
`deliverables/public-extracts/`, and 43 pending, unsent review-request bindings in
Stage 07. Earlier local test evidence is under `review-evidence/portable-review/`.

## Evidence limits and commands for other environments

- Twelve Google Sheets HTML responses are omitted because they contain browser
  configuration with key-shaped strings. Their manifest-bound claim extracts are
  retained. Original HTML hashes are commitments, not independently recomputed
  verification; CSV, legal responses and other retained bytes are hash-checked.
- Three historical Stage 02 configuration versions are unavailable. The selected
  attempt-004 configuration verifies. Historical retries reuse one run ID; this
  export preserves that defect rather than rewriting evidence.
- Manual policy/context provenance, historical guidance suitability, underlying
  evidence, hidden-tab completeness, human approvals and session-capture acceptance
  remain unresolved. Publication stays **blocked** even when validation passes.
- The manifest is unsigned. Evaluator acceptance of this extract representation
  remains unverified. The complete original regression suite is not included;
  eleven raw-fixture test modules are listed as excluded in the manifest.
- `portable.py`, strict stage validators, and `workflow.py --validate-run` require
  omitted original HTML and are **not public-package validation commands**.
  `public_evidence.py --export` also requires the original workspace.
- `workflow.py --reason ...` and `--retry-run ...` make **live requests** and create
  new outputs. Do not use them to assess this offline package. The exported runner
  includes the metadata-recovery fixes, but this does not amend historical runs.

See `regulatory-change-impact-brief/references/public-evidence.md` for the public
validation model and `Project_B_Learner_Assignment_Codex.md` for requirements.
