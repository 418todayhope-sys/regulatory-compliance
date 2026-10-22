# Stage 05 draft impact analysis

Run from the repository root:

```sh
python3 regulatory-change-impact-brief/scripts/impact.py
```

The offline command exclusively creates `deliverables/snapshots/05-impact-analysis.json`.
`--reconciliation` selects Stage 04; `--output` must be fresh. It verifies the full
Stage 01–04 hash/ID/run chain, reproduces Stage 04 from captured raw/derived register
evidence and manual POLICY sections, and verifies Stage 03's exact legal citation
spans/hashes. Prior snapshots and evidence are never rewritten or refreshed here.

This is a bounded interpretation of the supplied training case, not a generic legal
classifier. Read [changed-input review](adaptability.md): current material facts are
validated against explicit frozen reviewed configuration. New facts, unknown prose,
missing context and conflicts produce scoped unresolved review blockers and propagate
to actions and final drafts; they are not silently assigned the prior interpretation.
Missing legal rules and invalid source structure still stop processing. Recognized
product market-entry date changes recompute conditional timing separately from use.

The output evaluates eight scoped questions for each of eight systems: company
provider duties under 50(1)/(2); deployer biometric, deepfake and public-interest
text duties; consequential 50(5) conditions; and product-provider interaction and
marking scope. Company and upstream provider subjects are explicit. Inventory names
do not establish provider status. Seven recorded licensing/commissioning/branding
profiles support a draft non-provider role for Quillhaven; AI-005 remains unresolved.
Professional use supports the draft deployer role without settling other duties.

`draft_applicability` is distinct from the public schema's `state`:

| Draft applicability | Meaning |
| --- | --- |
| supported-draft-applicability | Recorded operating facts support this specific actor/rule/use trigger, subject to Legal review |
| supported-draft-non-applicability | The particular trigger/actor is excluded by the recorded use; never a system-wide exemption |
| conditional-applicability | A known trigger/exception/interface qualification still needs facts or interpretation |
| unresolved | Current release/role/content facts do not support settling this scoped question |

Schema states describe draft review impacts, not final compliance: supported-impact
means a supported scoped review impact, supported-no-impact is scoped
non-applicability, and conflicting/unresolved preserve evidence limits. Conditional
applicability with unproven conditions stays unresolved (or conflicting), rather
than being promoted to supported-impact.
Every statutory finding cites Stage 03 legal citation IDs plus Stage 04 system,
incident and authored-context IDs. Exact raw/row/section locators remain available
through those records. Policy expectations and observed evidence/approval limits
are separate collections; no missing evidence is converted to noncompliance.

The recorded AI-003/AI-008 product entry date is 1 June 2026. Those facts support
draft Article 111(4) eligibility for the relevant product providers' Article 50(2)
obligation, with independent proof and Legal review still pending. The exclusive
market cutoff is 2 August 2026; the statutory transition date is 2 December 2026.
This does not defer provider interaction, deployer disclosure, related 50(5) duties
or internal policy expectations. It does not establish a company operational date.
AI-005's role, release, biometric-use and market-entry facts remain unresolved.

Staff are natural persons too. Lack of applicant/public interaction is not enough
to exclude every supplier interface under 50(1). Likewise private text use alone
is not an enacted blanket provider-marking exemption. Fictional illustrations and
stylized graphics are distinguished from misleading real-presenter recordings;
an obviously fictional graphic does not prove the AI conversation itself is obvious.
Human review alone does not decide all transparency exceptions or biometric scope.

REC-003 metadata and REC-008 notice conflicts, REC-005 staleness, REC-009 partial
provenance and REC-010's unapproved/undated exception are retained unchanged.
The draft deepfake trigger for AI-008 does not assert that its existing label is
sufficient or insufficient. An internal Legal-approved exception, if later supplied,
would not automatically establish a statutory exemption.

The assigned observation date stays 26 August 2026, separately from source retrieval
times and the manual context's later authoring clarification. Authored case facts
can support bounded draft reasoning while their manual provenance and underlying
artifact verification remain limited. The result stays blocked for Legal review,
policy access and evidence resolution. No final compliance/noncompliance, approvals,
actions or operational deadlines are created by Stage 05. Stage 06 uses the separate
[actions command](actions.md); Stage 07 uses [draft validation](publication.md); full runs use [workflow orchestration](workflow.md).
