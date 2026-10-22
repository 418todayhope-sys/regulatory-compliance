# Complete workflow and recovery

Use Python 3.10+ on a POSIX system with `fcntl`, HTTPS access to the ten disclosed
routes, and `python3 -m pip install -r regulatory-change-impact-brief/requirements.txt`.
The operator command, from the repository root, is:

```sh
python3 regulatory-change-impact-brief/scripts/workflow.py --reason "Refresh the review from current disclosed sources"
```

This command **does access the network**. It is not a validation shortcut. Setup
requires the original assignment, unchanged schema, README and complete interview,
plus the runtime source configuration. The configuration extracts the ten original
URLs from that interview, identifies explicit register tabs and separately discloses
any manual policy/context reference. No credentials are supplied or bypassed. The
production CLI has no offline replay or local-source fallback option. Test transports
exist only in the Python test API and are identified in the run's `started.json`.

The command takes a repository lock, generates a fresh run ID and exclusively writes
`deliverables/runs/<new-run-id>/`. It archives the prior available package, freezes
local input bytes/configuration, writes Stage 01, attempts all ten sources in Stage 02,
then runs Stages 03–07 against the newly written immediate predecessor. It never selects
capture-004 implicitly. Every dependent stage and the three DRAFT files are recomputed,
even if the returned source bytes happen to be unchanged. Returned register/calendar
versions and proposal dates remain source values, not approvals. No prior approval is
carried over to a new draft; new review requests are pending and unsent.

All new evidence paths are repository-relative, resolved from the selected repository
root. Inputs are frozen under the new run so later edits to the interview, manual
reference, configuration or README cannot silently change old evidence. Explicitly
retained manual context remains manual/unverified, never a successful live POLICY read.
The three drafts and canonical seven snapshot filenames are inside the run directory;
legacy top-level drafts are left untouched. The final console message identifies the
new directory. No mutable "current" pointer or top-level replacement can make a failed
attempt appear successful. `result.json` is a final immutable outcome record. The newest
completed outcome identifies the previous package for a subsequent run; technical
completion can coexist with blocked publication and pending human approval.

Before a new run, the previous package is copied byte-for-byte into
`deliverables/history/<old-run-id>/`. Requests, approvals, all captured bytes, extra
files, snapshots and final drafts are preserved together. Available repository-local
manual/context/interview/configuration files referenced outside a legacy bundle are
also copied under `supplemental-inputs/`, without rewriting the original snapshots. `preservation.json` lists
exact copied paths/hashes, old/new run IDs and observed missing/corrupt references.
An already verified identical archive is reused; changed originals or an interrupted
archive are preserved in a new `occurrences/<new-run-id>/` directory, never overwritten.
If existing archive bytes are corrupt, the command stops for operator review rather
than trusting or replacing them. The legacy package's immutable snapshots may contain
old absolute references: those bytes are not rewritten, which would invalidate hashes.
The preservation manifest maps its available files to their retained copies. Newly
created run packages can be checked after moving the complete repository.
For the unchanged saved top-level legacy package, use the read-only
[portable validation mechanism](portable-review.md) after relocation.

Stage 01 records `supersedes_run_id`, `previous_completed_run_id`, `retry_of_run_id`,
the operator's change/retry reason, frozen inputs, preservation manifest hashes and a
traceable decision. Failed/interrupted attempts remain available; history never invents
missing evidence. A named retry archives both the failed occurrence and the previous
completed package, and supersedes the failed run while retaining that prior-package link.

On a caught failure, all written inputs, attempt ledgers, raw responses and completed
snapshots remain. `result.json` records outcome `failed`, failed stage/output, error
type, available files, next owner and recovery action. Phase-start records survive hard
interruptions that prevent a final diagnostic from being written. No partial directory
is resumed or overwritten. Repair the reported cause and use a new run:

```sh
python3 regulatory-change-impact-brief/scripts/workflow.py --retry-run run-<actual-failed-id> --reason "Describe the verified repair"
```

Every retry receives new run/snapshot IDs and performs fresh retrieval. Unknown retry
IDs and retrying a technically completed run are rejected. Use a normal new run with
an explicit reason to refresh or repair a previously completed package. Missing/corrupt
prior files are recorded and available bytes preserved before recomputation; the archive
is not falsely described as repaired. No automatic repeated network retries occur.
Filesystem permission/storage failures can prevent a diagnostic write; an existing
start/phase record and partial files must then be inspected by the operator.

Read-only verification, without retrieval or a new run:

```sh
python3 regulatory-change-impact-brief/scripts/workflow.py --validate-run deliverables/runs/run-<actual-id>
```

This reads actual snapshots, complete chain and run/record references, raw source/table
and citation evidence, frozen inputs, runtime configuration, history copies, final draft
bytes and every detached request binding. A mismatch exits nonzero; the old bundle is
not presented as a current result. `--root` selects a repository when invoked elsewhere.

This addition supplies orchestration and isolation, not a generic legal classifier:
read [changed-input review](adaptability.md). Operating changes now continue as explicit
review blockers; EVIDENCE has no fixed count. Document identity checks, the eight-system
scope and structural register validation remain strict. Source access or
missing authority may stop downstream analysis with retained blocked stages and a
failed technical outcome. Feedback ingestion/approval authentication remains outside
this command; no source mutation, policy activation, production calendar change,
incident closure, official response or publication occurs. Focused workflow tests use
explicit controlled fixture responses in temporary repositories, never live captures.
