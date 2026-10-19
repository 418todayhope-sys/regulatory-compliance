# Portable review evidence

This directory records actual local validation of the preserved Project B package.
No test in this exercise retrieves live sources or supplies human feedback.

- `preservation-before.json`: SHA-256 inventory recorded before this change for all
  existing deliverables, captures, interview/manual references, assignment, README
  and supplied schema. These protected files must remain unchanged.
- `commands.json`: actual commands, UTC start/end times, exit codes and log paths.
- `environment.json`: observed Python/dependency versions, platform and base Git
  revision; the new implementation is still an untracked working tree.
- `targeted.log`, `regression.log`, `relocated-cli.log`, `schema.log`, `skill.log`:
  captured command output. Regression tests use controlled fixture transports;
  portability tests use temporary copies and verify no file changes.
- `targeted-final.log`, `relocated-cli-final.log`, `regression-final.log`:
  final checks after fixing relocated Python module-path handling. The initial
  relocated CLI failure is preserved in `relocated-cli.log`, not concealed.
- `inventory.json`: proposed review files with sizes/hashes and protected-file check.
  The evidence directory itself is excluded to avoid a circular inventory.

Logs are observations, not signatures or proof of live source accessibility. The
saved package predates this portability change; its source limitations and pending
approvals remain. The facilitator must separately verify interview/session capture
and the authorized submission destination. Actual-feedback ingestion is still absent.

Proposed Git contents: original assignment, README/schema and existing starter
metadata; original `interviews/`; complete `regulatory-change-impact-brief/` including
tests/dependencies; `references/manual/`; every file in `deliverables/` including old
attempts and ledgers; and this `review-evidence/` directory. Exclude Python caches.
Review `.codex/` and `.entire/` separately with the session-capture guide/facilitator:
configuration, local logs and temporary hook payloads are not interchangeable with
verified assessed capture. Do not blindly add all untracked files. Nothing here
stages, commits, pushes or submits the package.

See the [portable command](../../regulatory-change-impact-brief/references/portable-review.md)
for the six recorded predecessor paths and the explicit read-only prefix mapping.
