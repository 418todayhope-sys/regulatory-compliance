# Stage 03 authority and timing

From the repository root:

```sh
python3 regulatory-change-impact-brief/scripts/authority.py --capture deliverables/snapshots/02-source-capture-attempt-004.json
```

This offline command exclusively creates `deliverables/snapshots/03-authority-and-timing.json`.
It preserves the existing run ID, hashes the actual selected Stage 02 snapshot,
verifies its Stage 01 binding and review date, and checks the six legal-source raw
hashes, identities and document versions. It never refreshes or edits captures.
Use a new `--output` path for another attempt; existing files are refused.

The saved draft uses capture-004; complete runs select their fresh capture explicitly.
Interpretation is bounded to the supported case and verified document identities. Changed
or missing text must produce explicit source/locator blockers rather than guessed
citations. This is not a general legal interpretation engine. No system facts,
compliance findings, approvals, operational deadlines or actions are generated.

Authority hierarchy: original and amending enacted acts provide the legal text;
the dated consolidated version cross-checks their relationship and disclaims legal
effect. LAW is the official explorer, TIME implementation guidance, FAQ explanatory
material. Internal policy is a separate internal-control basis; its manual reference
does not establish live access, statutory authority or Legal approval.

`source-statement`, `supported-interpretation`, `unresolved-applicability` and
`source-conflict` are separate record categories. Legal approval remains pending.
Entry into force, general application and the conditional Article 111(4) transition
are distinct. The December transition covers qualifying provider obligations under
Article 50(2), not every Article 50 duty. Later Chapter III dates do not establish
a general Article 50 delay. System eligibility is left unresolved.

The fixed review date remains 2026-08-26, represented by the existing UTC date anchor.
Actual retrieval timestamps are copied separately from Stage 02. Later retrieval
does not prove the historical state of mutable guidance; displayed update/version
claims and HTTP modification times are not interchangeable.

Each citation binds the original raw response path/hash and a semantic section to
an exact excerpt. `normalized-visible-text-v1` runs the existing HTML Page parser,
excludes script/style data, joins visible text nodes with a space, then collapses
whitespace using `re.sub(r"\s+", " ", ...)`. Locators are Unicode character offsets
in that deterministic text: start inclusive, end exclusive. Excerpt and normalized
text SHA-256 values make the spans reproducible without invented HTML anchors.
These are source-text locators, not assertions of signed-PDF authentication.

Known retained questions include the FAQ's direct-interaction cross-reference to
50(2) versus enacted 50(1), historical guidance suitability, conditional system
eligibility, policy access, and absent version-bound Legal approval. Stage 03 stays
blocked for those review questions even where document-level dates are supported.
Stage 02 unresolved records are retained unchanged as upstream observations; this
stage annotates authority without rewriting earlier snapshots.
