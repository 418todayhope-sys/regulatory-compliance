# Project B assessment guide

Prepare an evidence-backed DRAFT review of EU AI Act Article 50 for Legal and
Operations, covering eight systems as of **26 August 2026**. The Agent Skill is
[regulatory-change-impact-brief/SKILL.md](regulatory-change-impact-brief/SKILL.md).
Run the commands below from this repository root.

## Setup

Use Python 3.10+ on POSIX. The dependency is `jsonschema>=4.10.3,<5`, declared in
`regulatory-change-impact-brief/requirements.txt`. Install before offline grading:

```sh
python3 -m pip install -r regulatory-change-impact-brief/requirements.txt
```

Dependency installation needs an available package source or local wheel cache.
The validation and test commands themselves require no network or passwords.

## Offline validation

```sh
PYTHONDONTWRITEBYTECODE=1 python3 regulatory-change-impact-brief/scripts/public_evidence.py --validate .
```

This validates the public manifest, retained extracts, seven-stage chain,
reconstructed findings/actions, three draft files and exact review-request bindings.
It supports a normal Git checkout or worktree. Do not use the strict original-raw
validator for this extract-based assessment view.

## Offline tests

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s regulatory-change-impact-brief/tests -p test_public_evidence.py -v
```

The original-raw-package test is intentionally skipped in this public view.
The linked-worktree test can also skip when no existing Git history is available.
Tests use temporary fixtures, not live source retrieval or new commits.

## Evidence and selected chain

Start from `deliverables/snapshots/07-publication-validation.json` and follow its
predecessor paths and hashes. The selected Stage 02 is
`deliverables/snapshots/02-source-capture-attempt-004.json`.
`02-source-capture.json` is a preserved historical first attempt.

`public-evidence.json` binds twelve omitted Google Sheets HTML responses to safe
claim-bearing extracts under `deliverables/public-extracts/`. Existing table extracts,
CSV responses, attempt ledgers, legal sources and manual-policy provenance remain
available. Original HTML byte verification is **unavailable**, never passed; original
hashes are provenance commitments. Older historical runtime-configuration bytes are
also unavailable as reported by validation. Extracts do not prove original response
authenticity, hidden-tab completeness, independent corroboration or approval.

The three outputs in `deliverables/` are DRAFTS. Publication remains blocked;
Legal/Operations decisions and version-specific approvals remain pending. Source
calendar dates are unapproved proposals. No requests are claimed sent.

## Fresh runs are different

The command in the Skill's workflow instructions performs fresh live retrieval of
all ten disclosed sources and creates a new run. It is not offline validation and
must not be invoked for this offline assessment. This submitted package is an
explicit historical assessment view, not a claim of new retrieval. Consult the
[public-evidence reference](regulatory-change-impact-brief/references/public-evidence.md)
for verification limits and the unsigned manifest's trust boundary.
