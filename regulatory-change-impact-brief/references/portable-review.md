# Portable review of the saved legacy package

From any relocated repository root, with Python 3.10+ and the Skill requirements installed:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 regulatory-change-impact-brief/scripts/portable.py --original-root /home/maxg/regulatory-compliance
```

This command performs no retrieval and writes no files. `--root` selects a checkout
explicitly; `--package` defaults to the repository-relative `deliverables` directory.
The original-root value is the recorded prefix, not a directory that must exist.
All reads are confined to the selected checkout, including when the original workspace
still exists. Missing or tampered local evidence fails; there is no fallback to it.

The six saved predecessor paths share that prefix:

| Snapshot | Recorded predecessor suffix |
| --- | --- |
| 02-source-capture-attempt-004.json | deliverables/snapshots/01-scope.json |
| 03-authority-and-timing.json | deliverables/snapshots/02-source-capture-attempt-004.json |
| 04-evidence-reconciliation.json | deliverables/snapshots/03-authority-and-timing.json |
| 05-impact-analysis.json | deliverables/snapshots/04-evidence-reconciliation.json |
| 06-actions-and-approvals.json | deliverables/snapshots/05-impact-analysis.json |
| 07-publication-validation.json | deliverables/snapshots/06-actions-and-approvals.json |

Source, manual-reference and artifact paths have the same relocation issue. Mapping
only the six predecessor paths would be insufficient. The validator applies one
explicit prefix mapping to all reads, preserving logical paths for deterministic
reconstruction and hash comparisons. It calls the existing complete-package verifier:
schema, chain IDs/hashes, source bytes, extracted rows/joins, legal citation spans,
recomputed findings/actions, deterministic final drafts and detached request bindings.
It does not rewrite any saved JSON, rehash/rebind changed content, certify legal
authenticity, authenticate feedback or establish approval. Publication stays blocked.

The mapping is scoped to single-threaded validation modules, restored after errors,
and rejects outside-root references, traversal, escaping symlinks and write opens.
Run it as a standalone command, not concurrently inside another Python workflow.
Fresh workflow runs already use repository-relative paths and should use the normal
`workflow.py --validate-run deliverables/runs/<run-id>` command instead.

Durable command logs, inventory and preservation checks are under
[review evidence](../../assessment/omega-attempt-1-v1/review-evidence/portable-review/README.md). These logs document
controlled tests, not fresh live retrieval or facilitator verification.
