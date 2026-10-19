# Public offline assessment view

The assignment permits captured bytes or permitted claim-bearing extracts. Version 1
exports the saved four-capture case and selected capture-004 seven-stage chain. It is
an offline view of an existing run, not a new run, retrieval, approval or publication.
The supplied schema, original snapshots and three final drafts are copied unchanged.

From the original repository root, choose an absent destination:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 regulatory-change-impact-brief/scripts/public_evidence.py --export assessment/public-git
```

The exporter first runs full strict local validation and verifies each omitted
response against its recorded hash. It creates twelve claim extracts directly from
the originals, retains every attempt ledger and snapshot, the six existing HTML/CSV
table extracts, original CSV responses, legal/manual sources, interview and runtime
configuration. It copies the Skill and public offline test suite. The eleven original
raw-fixture test files remain local; their paths/hashes are recorded in the manifest.
Historical portability test logs remain evidence of tests run against the original
package, not instructions to run raw-dependent tests inside the public view.

Only twelve diagnosed Sheets HTML responses are omitted: SYSTEMS, EVIDENCE and
CALENDAR original responses in capture-001 through capture-004. Source IDs, original
hashes, disclosed URLs, response URLs, actual timestamps, original statuses and row
values remain intact. Older attempts have no separately recorded requested URL;
that extract field is null rather than fabricated. Extracts include all exposed
headers/rows, workbook/tab/gid, row numbers and discovery limitations. Missing,
conflicting, stale, partial and unapproved values are not resolved by exporting them.

`public-evidence.json` lists every retained file's actual hash/size and binds each
omitted original's snapshot/attempt/hash to its own extract/hash and method version.
Exports fail closed on unexpected Google key-shaped content or changed source case
structure; this bounded scanner is not a general secret-disclosure certification.
No `.git`, Entire/Codex capture, private configuration or live credentials are copied.
Do not publish the parent working tree: it still contains the preserved originals
and local capture history. This command does not prepare or alter Git history.

From the exported root, without network, passwords or the original workspace:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 regulatory-change-impact-brief/scripts/public_evidence.py --validate .
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s regulatory-change-impact-brief/tests -p test_public_evidence.py -v
```

Validation rejects missing/unexpected files, hashes, symlinks, escaping paths, invalid
extract provenance, IDs, locators and unapproved substitutions. It compares extracted
records with the saved table artifacts and original retained CSV bytes; verifies joins
and HTML/CSV agreement; rechecks full retained legal text; reconstructs authority,
reconciliation, impact analysis, actions and final drafts; and checks the seven-stage
hash chain and all final content/request bindings. No full validator is patched or
relaxed to accept missing sources. `portable.py` and `workflow.py --validate-run` still
require raw HTML and intentionally fail on this public view.

In a normal Git checkout, only the root `.git/` directory (or regular `.git` worktree
pointer file) is administrative metadata outside the assessment inventory. Directory
contents are not traversed and a pointer is never followed. A pointer must have the
`gitdir: <path>` form; that target need not be readable to validate retained evidence.
The root entry cannot be a symlink, and `.git` cannot appear in manifest file paths.
Nested `.git` entries, unexpected ordinary files and all assessment symlinks remain
errors. This exception does not scan or certify Git history, hooks, credentials or
administrative state; audit those separately before publication. The strict original
validator and every source/extract/hash check are unchanged.

The report always says `original_html_byte_verification: unavailable`. Original raw
hashes remain provenance commitments and cannot be recomputed from extracts. Existing
Stage 07 raw-verification statements describe the original local validation; the
separate public result states the narrower current verification. Older historical
runtime configurations were not frozen and their bytes are also reported unavailable;
the selected capture-004 configuration and interview bindings are verified.

An offline grader can verify retained evidence integrity, claim consistency, row
locators, legal text, draft generation and review bindings. It cannot independently
prove extraction fidelity to withheld HTML, historical Google authenticity, hidden-tab
completeness, human approvals or facilitator capture compliance. Original export
fidelity is checked at export time while originals are present. None of this constitutes
source corroboration, signatures, legal approval or proof of original response bytes.

The manifest is unsigned. To detect coordinated rebaselining, retain the printed
manifest digest independently and supply `--expected-manifest-sha256 sha256:<digest>`.
Without an independently trusted digest or reviewed Git revision, an attacker could
replace an entire internally consistent package, just as with other unsigned hashes.
Actual grader acceptance of this permitted-extract representation remains unverified.
