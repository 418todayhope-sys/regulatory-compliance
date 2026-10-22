"""Stage 03: bounded, evidence-linked authority/timing draft from selected captures."""
import argparse
import copy
from datetime import date, timedelta
import json
from pathlib import Path
import re
from uuid import uuid4
from urllib.parse import urlsplit

from capture import Page, digest, legal_identity, now
from scope import ROOT, validate

LEGAL = ("LAW", "OJ", "AMEND", "CONSOLIDATED", "TIME", "FAQ")
KINDS = {"OJ": "enacted-original", "AMEND": "enacted-amendment", "CONSOLIDATED": "consolidated-reference",
         "LAW": "official-explorer", "TIME": "implementation-guidance", "FAQ": "faq-explanation"}


def visible_text(raw):
    """Locator algorithm normalized-visible-text-v1; Unicode character offsets."""
    page = Page()
    page.feed(raw.decode("utf-8"))
    return re.sub(r"\s+", " ", " ".join(page.text)), page


def build(stage02, root=ROOT):
    raw = stage02.read_bytes()
    previous = json.loads(raw)
    validate(previous, root)
    if previous["stage"] != "source-capture" or previous["sequence"] != 2:
        raise ValueError("Select the Stage 02 capture snapshot explicitly")
    parent = Path(previous["predecessor"]["path"])
    scope_raw = parent.read_bytes()
    scope = json.loads(scope_raw)
    validate(scope, root)
    if (digest(scope_raw) != previous["predecessor"]["sha256"] or
        scope["snapshot_id"] != previous["predecessor"]["snapshot_id"] or
        scope["run_id"] != previous["run_id"] or scope["stage"] != "scope"):
        raise ValueError("Invalid Stage 01/02 predecessor or run binding")
    if scope["state"]["as_of"] != "2026-08-26T00:00:00Z" or previous["state"]["as_of"] != scope["state"]["as_of"]:
        raise ValueError("Assigned review date must remain 26 August 2026")
    documents, texts, citations, blockers = {}, {}, [], []

    def block(key, summary, evidence_ids, resolution):
        record = {"id": key, "summary": summary, "evidence_ids": evidence_ids, "owner": "Legal",
                  "category": "unresolved-applicability", "resolution_need": resolution}
        blockers.append(record)
        return record

    for name in LEGAL:
        candidates = [r for r in previous["state"]["sources"] if r["source_name"] == name]
        chosen_id = previous["state"].get("selected_verified_documents", {}).get(name)
        source = next((r for r in candidates if r["id"] == chosen_id), candidates[-1] if candidates else None)
        try:
            if not source or source["retrieval_status"] in {"invalid", "unavailable", "stale"} or not source["local_reference"]:
                raise ValueError("No usable captured response")
            body = Path(source["local_reference"]).read_bytes()
            if digest(body) != source["content_hash"]:
                raise ValueError("Raw capture hash mismatch")
            text, page = visible_text(body)
            if name in {"OJ", "AMEND", "CONSOLIDATED"}:
                identity = legal_identity(name, page, source["final_url"])
                if not identity:
                    raise ValueError("Legal document identity/version mismatch")
                expected_id = source["version_metadata"].get("document_id")
                if expected_id != identity["document_id"]:
                    raise ValueError("Capture metadata disagrees with document identity")
                if source["version_metadata"].get("document_version") != identity["document_version"]:
                    raise ValueError("Capture metadata disagrees with document version")
            else:
                expected_title = {"LAW": "Article 50: Transparency obligations", "TIME": "Timeline for the Implementation", "FAQ": "Transparency obligations under Article 50"}[name]
                if expected_title not in page.title:
                    raise ValueError("Guidance document title mismatch")
                host = "digital-strategy.ec.europa.eu" if name == "FAQ" else "ai-act-service-desk.ec.europa.eu"
                if urlsplit(source["final_url"]).hostname != host or urlsplit(source["final_url"]).scheme != "https":
                    raise ValueError("Guidance origin mismatch")
                identity = {"document_version": None, "effective_date": None}
            texts[name] = text
            documents[name] = {"source_id": source["id"], "kind": KINDS[name], "identity": identity,
                               "title": page.title, "url": source["final_url"], "path": source["local_reference"],
                               "sha256": source["content_hash"], "retrieved_at": source["retrieved_at"],
                               "normalized_text_sha256": digest(text.encode("utf-8")),
                               "authority": "binding" if name in {"OJ", "AMEND"} else "reference-only" if name == "CONSOLIDATED" else "advisory"}
        except (OSError, ValueError, UnicodeError) as error:
            block("u-authority-source-" + name.lower(), f"{name}: {error}; dependent statements withheld.",
                  [source["id"]] if source else [], "Repair/verify this captured source before dependent legal interpretation.")

    def cite(name, section, start, end=None, occurrence="unique", length=None):
        if name not in texts:
            return None
        text = texts[name]
        matches = [m.start() for m in re.finditer(re.escape(start), text)]
        if not matches or (occurrence == "unique" and len(matches) != 1):
            block(f"u-locator-{len(blockers)}", f"{name}: absent or ambiguous exact locator for {section}; claim withheld.",
                  [documents[name]["source_id"]], "Review source changes and establish an exact locator; do not guess.")
            return None
        left = matches[-1] if occurrence == "last" else matches[0]
        right = left + (length or len(start))
        if end:
            right = text.find(end, left + len(start))
            if right < 0:
                block(f"u-locator-{len(blockers)}", f"{name}: end locator missing for {section}; claim withheld.",
                      [documents[name]["source_id"]], "Review source boundary.")
                return None
        quote = text[left:right]
        record = {"id": f"cite-{len(citations)+1:03}", "summary": f"{name}: {section}",
                  "evidence_ids": [documents[name]["source_id"]], "source_name": name,
                  "category": "source-statement",
                  "source_id": documents[name]["source_id"], "path": documents[name]["path"],
                  "raw_sha256": documents[name]["sha256"], "section": section,
                  "locator": {"algorithm": "normalized-visible-text-v1", "start": left, "end": right,
                              "units": "Unicode characters; start inclusive, end exclusive"},
                  "excerpt": quote, "excerpt_sha256": digest(quote.encode("utf-8"))}
        citations.append(record)
        return record["id"]

    def statement(collection, key, summary, refs, category="source-statement", **fields):
        if refs and all(refs):
            collection.append({"id": key, "summary": summary, "evidence_ids": refs, "category": category,
                               "legal_approval": "pending", **fields})

    binding, timing, guidance, relationships, interpretations, conflicts = [], [], [], [], [], []
    # Exact paragraph boundaries in the original enacted Article 50; paragraph 7 is superseded below.
    descriptions = {
        1: "Provider direct-interaction disclosure, with the obviousness and law-enforcement qualifications in the text.",
        2: "Provider machine-readable marking/detectability for synthetic content; technical-feasibility and specified editing/law-enforcement qualifications apply.",
        3: "Deployer information duties for emotion recognition/biometric categorisation; data-protection and specified law-enforcement qualifications remain.",
        4: "Deployer deepfake disclosure and public-interest text disclosure have distinct triggers and exceptions; artistic works and human/editorial review qualifications are limited as stated.",
        5: "Information under paragraphs 1–4 must be clear, distinguishable, accessible and provided no later than first interaction/exposure.",
        6: "Article 50 does not displace Chapter III or other Union/national transparency duties.",
    }
    if "OJ" in texts:
        article_start = texts["OJ"].rfind("Article 50 Transparency obligations")
        article_end = texts["OJ"].find("Article 51", article_start)
        section = texts["OJ"][article_start:article_end]
        marks = list(re.finditer(r" ([1-7])\. ", section))
        for paragraph, description in descriptions.items():
            marker = next((m for m in marks if int(m.group(1)) == paragraph), None)
            following = next((m for m in marks if int(m.group(1)) == paragraph+1), None)
            if marker and following:
                quote = section[marker.start()+1:following.start()]
                ref = cite("OJ", f"Article 50({paragraph})", quote)
                statement(binding, f"rule-50-{paragraph}", description, [ref], rule_ref=f"Article 50({paragraph})",
                          authority="binding", system_applicability="unresolved")
            else:
                block(f"u-article-50-{paragraph}", f"Article 50({paragraph}) boundary not found; no rule fabricated.",
                      [documents["OJ"]["source_id"]], "Review captured Article 50 structure.")
    for number, following, label in [(3,4,"provider"),(4,5,"deployer"),(60,61,"deep fake")]:
        needle = f"({number}) ‘{label}’ means"
        ref = cite("OJ", f"Article 3({number})", needle, f"({following})")
        definition_summary = {3: "Provider definition includes development/commissioning and placing on the market or putting into service under one's own name or trademark.",
                              4: "Deployer definition concerns use under one's authority, excluding personal non-professional activity.",
                              60: "Deep fake definition concerns generated/manipulated image, audio or video resembling existing subjects and falsely appearing authentic or truthful."}[number]
        statement(binding, f"definition-3-{number}", definition_summary, [ref], rule_ref=f"Article 3({number})", authority="binding")

    amendment7 = cite("AMEND", "Article 1(20), replacing Article 50(7)", "(20) in Article 50, paragraph 7 is replaced", "(21) in Article 56")
    statement(binding, "rule-50-7-amended", "Amended Article 50(7) concerns codes of practice and Commission assessment/common rules.", [amendment7], rule_ref="Article 50(7), as amended", authority="binding")
    original7 = cite("OJ", "Original Article 50(7), superseded", "7. The AI Office shall encourage", "CHAPTER V")
    consolidated7 = cite("CONSOLIDATED", "Consolidated Article 50(7)", "7. The Commission shall encourage", "CHAPTER V")
    relation = cite("CONSOLIDATED", "Version header and amending-act table", "02024R1689 — EN — 27.07.2026 — 001.001", "Article 1 Subject")
    statement(relationships, "relationship-2026-amendment", "Original 2024/1689 text is amended by 2026/1744; the 27 July 2026 consolidation integrates the amendment. Original Article 50(7) is not the current paragraph.", [original7, amendment7, consolidated7, relation], category="supported-interpretation")

    general = cite("OJ", "Article 113, general application", "It shall apply from 2 August 2026.", occurrence="last")
    amended_general = cite("CONSOLIDATED", "Article 113, unchanged general application date", "It shall apply from 2 August 2026.", occurrence="last")
    statement(timing, "timing-general", "Article 113 states the general application date as 2 August 2026.", [general, amended_general], date="2026-08-02", date_type="general-application")
    original_entry = cite("OJ", "Article 113, entry into force", "This Regulation shall enter into force on the twentieth day following", ". It shall apply", occurrence="last")
    amendment_entry = cite("AMEND", "Article 4, entry into force", "Article 4 Entry into force and application This Regulation shall enter into force on the third day following", "This Regulation shall be binding", occurrence="last")
    if "OJ" in documents:
        publication = documents["OJ"]["identity"]["publication_date"]
        statement(timing, "timing-original-entry", "Entry into force calculated from the original publication plus twenty days; distinct from application.", [original_entry], "supported-interpretation", date=(date.fromisoformat(publication)+timedelta(days=20)).isoformat(), publication_date=publication, date_type="entry-into-force")
    if "AMEND" in documents:
        publication = documents["AMEND"]["identity"]["publication_date"]
        statement(timing, "timing-amendment-entry", "Amendment entry into force calculated as the third day following its publication, before the assigned review date.", [amendment_entry], "supported-interpretation", date=(date.fromisoformat(publication)+timedelta(days=3)).isoformat(), publication_date=publication, date_type="entry-into-force")
    transition_text = "Providers of AI systems, including general-purpose AI systems, generating synthetic audio, image, video or text content, that have been placed on the market before 2 August 2026 shall take the necessary steps in order to comply with Article 50(2) by 2 December 2026."
    transition = cite("AMEND", "Article 1(39)(b), adding Article 111(4)", transition_text)
    transition_c = cite("CONSOLIDATED", "Article 111(4)", transition_text)
    statement(timing, "timing-50-2-transition", "Limited provider transition for Article 50(2): qualifying synthetic-content systems placed on the market before 2 August 2026 must comply by 2 December 2026.", [transition, transition_c], date="2026-12-02", date_type="conditional-statutory-transition", conditions={"role": "provider", "obligation": "Article 50(2)", "system_placed_on_market_before": "2026-08-02"}, system_eligibility="unresolved")
    highrisk = cite("AMEND", "Article 1(40)(b), replacing Article 113 third paragraph (c)", "Chapter III, Sections 1, 2, and 3, with the exception of Article 6(5), shall apply from:", ";’", occurrence="unique")
    statement(timing, "timing-highrisk-separate", "Amendment provides separate Chapter III application dates; these do not constitute a general Article 50 postponement.", [highrisk, general], category="supported-interpretation", date_type="other-chapter-conditional-application", dates={"Article 6(2)/Annex III": "2027-12-02", "Article 6(1)/Annex I": "2028-08-02"}, system_eligibility="unresolved")
    statement(interpretations, "interpretation-no-blanket-delay", "At 26 August 2026 the general start date has passed, while the specific Article 50(2) transition date is future. Neither establishes a blanket deferral for other Article 50 duties or any company's eligibility.", [general, transition, transition_c], category="supported-interpretation", as_of="2026-08-26", legal_approval_status="pending")

    law_version = cite("LAW", "About this text", "The text displayed here is based on the EUR-Lex consolidated version of the AI Act as at 27 July 2026")
    statement(guidance, "context-law", "LAW is an official explorer based on the 27 July consolidation; its explanations do not supersede enacted text.", [law_version], authority="advisory", reported_version="2026-07-27")
    timeline = cite("TIME", "2 August and 2 December 2026 milestones", "02 Aug 2026 The majority of rules", "02 Aug 2027")
    statement(guidance, "context-timeline", "Timeline states the Article 50 general start and limited Article 50(2) transition; its broad heading 'come into force' must not collapse entry into force and application.", [timeline, general, transition], authority="advisory", published_version=None)
    faq_timing = cite("FAQ", "When does Article 50 ... start to apply and is there a grace period?", "When does Article 50 of the AI Act start to apply and is there a grace period?", "Who will oversee the enforcement")
    faq_update = cite("FAQ", "Displayed last update", "Last update 24 July 2026")
    faq_start = cite("FAQ", "General Article 50 application sentence", "Article 50 of the AI Act applies as from", ". From that date")
    statement(guidance, "context-faq", "FAQ discusses the general start and limited grace period; its retroactive-labelling explanation is advisory, not a separate enacted exemption established here. Any timing discrepancy is retained separately.", [faq_timing, faq_update, faq_start], authority="advisory", displayed_update="2026-07-24")
    if faq_start:
        observed = next(c["excerpt"] for c in citations if c["id"] == faq_start)
        if not observed.endswith("2 August 2026"):
            conflict = block("u-faq-timing-conflict", "FAQ general application date differs from enacted Article 113; guidance cannot override enacted timing.", [faq_start] + ([general] if general else []), "Legal to reconcile the captured timing discrepancy; retain both source statements.")
            conflict["category"] = "source-conflict"
            conflicts.append(conflict)
    faq_error = cite("FAQ", "Provider-answer paragraph citing Article 50(2) for direct interaction", "According to Article 50(2) of the AI Act, providers must design and develop AI systems that interact directly", occurrence="unique", length=300)
    rule1 = next((r["evidence_ids"][0] for r in binding if r["id"] == "rule-50-1"), None)
    if faq_error and rule1:
        block("u-faq-cross-reference", "FAQ cites Article 50(2) for direct-interaction disclosure; enacted Article 50(1) is the corresponding provision. Preserve this numbering discrepancy, not a new duty.", [faq_error, rule1], "Legal to confirm treatment of the FAQ cross-reference; use enacted provision numbering.")
    block("u-system-applicability", "No system-level role, scope, exception, transition eligibility or compliance determination is made in Stage 03.", [r["id"] for r in binding+timing], "Legal and system owners must establish the relevant facts and apply the supported rule bases in later authorized stages.")
    block("u-historical-guidance", "Guidance was retrieved after the review date; HTTP timestamps do not prove the precise guidance content available on 26 August 2026.", [c for c in [law_version,timeline,faq_update] if c], "Legal to assess historical suitability; retain displayed versions separately from retrieval times.")
    block("u-policy-and-approval", "Internal policy is a separate internal-control basis; live POLICY access remains unresolved and no Legal approval has been supplied.", [r["id"] for r in previous["state"].get("manual_references", [])], "Obtain legitimate policy provenance/access and actual version-bound Legal feedback; manual text is not enacted law or approval.")
    decisions = [{"id": "d-authority-hierarchy", "summary": "Use enacted original plus amendments for legal authority, consolidation for cross-checking, guidance for explanation only.",
                  "evidence_ids": [c for c in [relation,amendment7,general,transition] if c], "concern": "Keep authority, source statements, interpretation and approval distinct.",
                  "options": ["Reconcile enacted acts with a dated consolidation", "Treat current web explanations as binding and approved"],
                  "chosen_behavior": "Preserve dated source statements and conditional draft interpretations; withhold system findings and approvals.",
                  "rationale": "The consolidation disclaims legal effect and the assignment reserves final interpretation to Legal.",
                  "tradeoffs": ["An explicit unresolved chain remains even where document-level timing is supported."],
                  "downstream_effect": "Later stages must resolve facts and Legal questions before relying on system-specific conclusions."}]
    state = {"as_of": scope["state"]["as_of"], "as_of_convention": scope["state"]["as_of_convention"],
             "source_documents": documents, "citations": citations, "binding_rules": binding, "timing_rules": timing,
             "authority_hierarchy": {"enacted-original-and-amendment": "Binding text; reconcile amendments chronologically", "consolidated-reference": "Documentation aid, not an independently authentic enactment", "official-explorer-and-guidance-and-faq": "Advisory explanations; cannot amend enacted duties", "internal-policy": "Separate internal-control basis, not statutory text or Legal approval"},
             "guidance_context": guidance, "authority_blockers": blockers, "version_relationships": relationships,
             "supported_interpretations": interpretations, "legal_approval": "pending", "system_findings": [],
             "timing_conflicts": conflicts, "timing_uncertainty": "Conditional eligibility and historical guidance remain unresolved; no blanket grace period or operational deadline is inferred."}
    records = citations+binding+timing+guidance+blockers+relationships+interpretations+decisions
    result = {"schema_version": previous["schema_version"], "snapshot_id": "snapshot-"+str(uuid4()), "run_id": previous["run_id"],
              "stage": "authority-and-timing", "sequence": 3, "created_at": now(), "status": "blocked",
              "predecessor": {"snapshot_id": previous["snapshot_id"], "path": str(stage02), "sha256": digest(raw)},
              "consumed_record_ids": previous["produced_record_ids"], "produced_record_ids": [r["id"] for r in records],
              "state": state, "unresolved": copy.deepcopy(previous["unresolved"])+blockers, "decisions": decisions}
    validate(result, root)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, default=ROOT / "deliverables/snapshots/02-source-capture-attempt-004.json")
    parser.add_argument("--output", type=Path, default=ROOT / "deliverables/snapshots/03-authority-and-timing.json")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = build(args.capture.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(result, output, indent=2, ensure_ascii=False)
        output.write("\n")
    print(f"Stage 03 schema-valid, Legal review blocked/pending: {args.output}")


if __name__ == "__main__":
    main()
