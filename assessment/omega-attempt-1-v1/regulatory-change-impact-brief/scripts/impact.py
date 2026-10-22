"""Stage 05: bounded draft impact analysis of the documented Quillhaven case."""
import argparse
import copy
from datetime import date, datetime
import json
from pathlib import Path
from uuid import uuid4
import re

import authority
from capture import digest, now
import reconcile
import operating
from scope import ROOT, validate

APPLIES = "supported-draft-applicability"
NO = "supported-draft-non-applicability"
CONDITIONAL = "conditional-applicability"
UNKNOWN = "unresolved"
SYSTEM_IDS = operating.SYSTEM_IDS


def transition_window(market_entry, review_date, actor_role="provider", synthetic=True):
    """Evaluate only Article 111(4)'s recorded conditions; not a company deadline."""
    result = {"scope": "provider Article 50(2) only", "market_entry_date": market_entry,
              "cutoff_exclusive": "2026-08-02", "statutory_transition_date": "2026-12-02",
              "as_of": review_date, "legal_approval": "pending", "independently_verified": False}
    if actor_role != "provider":
        result.update(assessment="not-applicable-to-this-actor", transition_phase=None)
    elif market_entry is None or synthetic is None:
        result.update(assessment="unresolved", transition_phase=None)
    elif not synthetic or date.fromisoformat(market_entry) >= date(2026,8,2):
        result.update(assessment="supported-draft-ineligible", transition_phase=None)
    else:
        result.update(assessment="supported-draft-eligible", transition_phase="before-general-start" if date.fromisoformat(review_date) < date(2026,8,2)
                      else "transition-active" if date.fromisoformat(review_date) < date(2026,12,2) else "transition-date-reached-or-passed")
    return result


def inputs(stage04, root=ROOT):
    raw = stage04.read_bytes()
    four = json.loads(raw)
    validate(four, root)
    if four["stage"] != "evidence-reconciliation" or four["sequence"] != 4:
        raise ValueError("Expected Stage 04")
    parent = Path(four["predecessor"]["path"])
    if digest(parent.read_bytes()) != four["predecessor"]["sha256"]:
        raise ValueError("Stage 03 hash mismatch")
    chain, _ = reconcile.load_chain(parent, root)
    if four["run_id"] != chain[3]["run_id"] or four["predecessor"]["snapshot_id"] != chain[3]["snapshot_id"]:
        raise ValueError("Stage 04 run/predecessor identity mismatch")
    if four["state"]["as_of"] != chain[1]["state"]["as_of"]:
        raise ValueError("Assigned review date changed")
    tables, checks = reconcile.verified_tables(chain[2])
    reproduced = reconcile.assemble(chain, tables, checks, root)
    if any(four["state"].get(key) != value for key,value in reproduced.items()):
        raise ValueError("Stage 04 reconciliation is not reproduced by its sources")
    verified_texts = {}
    for citation in chain[3]["state"]["citations"]:
        path = citation["path"]
        if path not in verified_texts:
            body = Path(path).read_bytes()
            verified_texts[path] = (digest(body), authority.visible_text(body)[0])
        raw_hash, text = verified_texts[path]
        if raw_hash != citation["raw_sha256"]:
            raise ValueError("Legal citation raw hash mismatch")
        locator = citation["locator"]
        quote = text[locator["start"]:locator["end"]]
        if quote != citation["excerpt"] or digest(quote.encode()) != citation["excerpt_sha256"]:
            raise ValueError("Legal citation locator/hash mismatch")
    return four, chain, raw


def _analyze_reviewed(four, three, review):
    state4 = four["state"]
    sections = state4["policy_controls"]
    facts = {r["system_id"]:r for r in state4["system_facts"]}
    def section(heading):
        current = review['section'](heading)
        if current is not None:
            return current
        # A reference to an available system record, not a manufactured manual excerpt.
        basis = facts.get(heading, next(iter(facts.values())))
        return {'id': basis['id'], 'excerpt': '', 'raw_sha256': None, 'manual_provenance': {}}
    operating_context = section("Operating scope")
    timing_context = section("Product timing and evidence limits")
    context_header = section("Article 50 review — company operating facts")
    policy = section("Learner and public transparency")
    exception_policy = section("Evidence and exceptions")
    market_entry = review['market_date']
    rules = {r["id"]:r for r in three["state"]["binding_rules"]+three["state"]["timing_rules"]}
    def legal(*keys):
        try:
            return list(dict.fromkeys(c for key in keys for c in rules[key]["evidence_ids"]))
        except KeyError as error:
            raise ValueError("Missing supported legal rule: " + str(error)) from error
    impacts, roles, transitions, policy_findings, questions = [], [], [], [], []
    for sid, fact in sorted(facts.items()):
        context = section(sid)
        incidents = [r for r in state4["incident_evidence"] if r["system_id"] == sid]
        fact_ids = list(dict.fromkeys([fact["id"], context["id"], operating_context["id"]]+[r["id"] for r in incidents]))
        role_cites = legal("definition-3-3", "definition-3-4")
        role = {"id":"role-"+sid,"summary":f"{sid}: draft Quillhaven role assessment from operating facts, not inventory naming.",
                "evidence_ids":fact_ids+role_cites,"system_id":sid,"category":"supported-draft-interpretation",
                "provider_assessment":"unresolved" if sid == "AI-005" else "supported-draft-not-provider",
                "deployer_assessment":"supported-draft-deployer", "legal_citation_ids":role_cites,
                "basis":"Professional operation under company authority; for seven uses the context expressly excludes development/commissioning and own-brand placing into service.",
                "upstream_provider_identity":"not supplied/independently verified", "legal_approval":"pending",
                "context_provenance":"Manual authored case facts; not live Notion access or independent corroboration."}
        roles.append(role)

        def finding(key, rule_keys, subject, applicability, reason, impact_state=None, conditional_on=None):
            refs = legal(*rule_keys, "timing-general")
            record = {"id":f"impact-{sid}-{key}","summary":reason,"reason":reason,"system_id":sid,
                      "state":impact_state or ("supported-no-impact" if applicability == NO else "unresolved" if applicability in {UNKNOWN, CONDITIONAL} else "supported-impact"),
                      "evidence_ids":list(dict.fromkeys(fact_ids+[role["id"]]+refs)),"legal_citation_ids":refs,
                      "rule_refs":[rules[k].get("rule_ref", k) for k in rule_keys], "basis_type":"statutory",
                      "subject_actor":subject,"draft_applicability":applicability,"category":"draft-impact-finding",
                      "as_of":"2026-08-26","approval_status":"pending","final_compliance_status":"not-determined",
                      "interpretation_limit":"Supported states concern this scoped draft review impact, never a final compliance/noncompliance determination.",
                      "source_record_ids":[fact["source_record_id"]]+[r["source_record_id"] for r in incidents],
                      "manual_context_ids":[r["id"] for r in (context, operating_context) if r["id"].startswith("policy-supplement-")], "conditional_on":conditional_on or []}
            impacts.append(record)
            return record

        company_provider = UNKNOWN if sid == "AI-005" else NO
        for paragraph in (1,2):
            finding(f"company-50-{paragraph}",[f"rule-50-{paragraph}"],"Quillhaven in provider capacity",company_provider,
                    "Current release development/commissioning/branding facts do not settle whether Quillhaven is also a provider." if sid == "AI-005" else
                    f"The recorded licensed third-party operation does not support a Quillhaven provider duty under Article 50({paragraph}); this does not exclude supplier duties or internal policy expectations.")
        biometric = UNKNOWN if sid == "AI-005" else NO
        finding("deployer-50-3",["rule-50-3","rule-50-5"],"Quillhaven as deployer",biometric,
                "Current-release biometric emotion/intent/category use remains unestablished; human review does not settle the trigger." if sid == "AI-005" else
                "The recorded use does not establish emotion recognition or biometric categorisation; this draft exclusion is limited to Article 50(3) and the documented use.")
        deepfake = UNKNOWN if sid == "AI-005" else APPLIES if sid == "AI-008" else NO
        deep_reason = {
            "AI-003":"Illustrated fictional classroom scenes are not existing subjects presented as authentic recordings; no Article 50(4) deepfake trigger is supported for that recorded content. Metadata conflict remains separate.",
            "AI-007":"The stylized fictional guide graphic does not meet the recorded existing-subject/authenticity deepfake criteria. This does not prove visitors understand they converse with AI.",
            "AI-008":"Translated speech/lip movements make real presenters appear to speak unrecorded words; recorded potential authenticity confusion and non-artistic programme use support draft deployer deepfake disclosure. Visible label, provenance and exception proof remain unresolved.",
        }.get(sid,"Current release/content facts are insufficient to settle Article 50(4) deepfake scope." if sid == "AI-005" else
              "No generated/manipulated existing-subject recording falsely presented as authentic is established in the documented use; draft deepfake non-applicability is narrowly scoped.")
        finding("deployer-50-4-deepfake",["rule-50-4","definition-3-60","rule-50-5"],"Quillhaven as deployer",deepfake,deep_reason,
                impact_state="unresolved" if sid == "AI-008" else None)
        text_app = UNKNOWN if sid == "AI-005" else NO
        finding("deployer-50-4-text",["rule-50-4","rule-50-5"],"Quillhaven as deployer",text_app,
                "Assessment flags for human review do not establish current public-interest text publication; missing release facts prevent a broader determination." if sid == "AI-005" else
                "The documented use does not establish generated text published to inform the public on matters of public interest. Private administrative replies/internal summaries are not that trigger; no blanket human-review exemption is assumed.")
        finding("company-50-5",["rule-50-5"],"Quillhaven as deployer",UNKNOWN if sid == "AI-005" else APPLIES if sid == "AI-008" else NO,
                "First-exposure, clarity and accessibility conditions follow the supported deepfake disclosure trigger; source-reported label verification does not settle complete fulfilment." if sid == "AI-008" else
                "Paragraph 5 follows duties actually triggered for the relevant actor; it is not an independent new duty inferred from an inventory label.", impact_state="unresolved" if sid == "AI-008" else None)
        direct = sid in {"AI-001","AI-004","AI-007"}
        provider_direct = UNKNOWN if sid == "AI-005" else CONDITIONAL
        direct_reason = ("Direct AI conversation is documented, but the Article 50(1) obviousness exception requires its own factual/Legal assessment; a stylized graphic or recorded notice value alone does not decide it." if direct else
                         "The documented workflow does not establish applicant/public direct AI conversation; staff are also natural persons, so the supplier interface/design and obviousness facts must be checked before a broader Article 50(1) exclusion.")
        if sid == "AI-005":
            direct_reason = "Human-reviewed assessment flagging does not settle the current release's direct-interaction design; preserve release uncertainty."
        finding("product-provider-50-1",["rule-50-1","rule-50-5"],"Upstream product provider (identity not independently verified)",provider_direct,direct_reason,
                impact_state="conflicting" if sid == "AI-007" else None,
                conditional_on=["Confirm actor/interface-specific direct-interaction design and the fact-specific obviousness exception"])
        synthetic_app = UNKNOWN if sid in {"AI-004","AI-005","AI-007"} else APPLIES if sid in {"AI-003","AI-008"} else CONDITIONAL
        synthetic_reason = ("Substantive image generation or translated speech/lip manipulation supports draft provider synthetic-content marking scope; product transition is assessed separately and does not settle published-copy provenance." if sid in {"AI-003","AI-008"} else
                            "Generated replies/drafts/summaries require a provider marking-scope check; private staff use alone is not an enacted blanket exclusion, and standard-editing qualifications need specific facts.")
        if synthetic_app == UNKNOWN:
            synthetic_reason = "The current record does not establish the product's synthetic-content generation/marking scope; do not infer it from a conversational or classification inventory label."
        synthetic = finding("product-provider-50-2",["rule-50-2"],"Upstream product provider (identity not independently verified)",synthetic_app,synthetic_reason,
                            impact_state="conflicting" if sid == "AI-003" else "unresolved" if sid == "AI-008" else None)
        entry = market_entry if sid in {"AI-003","AI-008"} else None
        transition = transition_window(entry,"2026-08-26",synthetic=True if entry else None)
        transition.update({"id":"transition-"+sid,"summary":"Evaluate provider Article 50(2) transition using product market entry, not content export/publication or evidence-update dates.",
                           "system_id":sid,"evidence_ids":fact_ids+[timing_context["id"],synthetic["id"]]+legal("timing-50-2-transition"),
                           "legal_citation_ids":legal("timing-50-2-transition"),"category":"conditional-draft-timing-assessment",
                           "subject_actor":"Product provider; not a Quillhaven deployer postponement",
                           "does_not_defer":["Article 50(1)","Article 50(3)","Article 50(4)","Article 50(5) where relevant", "internal policy expectations"],
                           "source_fact_provenance":"Owner-supplied case context; underlying product-release notices not independently verified"})
        transitions.append(transition)
        if entry:
            synthetic["evidence_ids"] += [timing_context["id"]]+legal("timing-50-2-transition")
            synthetic["transition_record_id"] = transition["id"]
        policy_kind = "conflicting" if sid in {"AI-003","AI-007"} else "unresolved" if sid in {"AI-002","AI-004","AI-005","AI-008"} else "source-reported-only"
        policy_findings.append({"id":"policy-review-"+sid,"summary":"Review internal notice/provenance/evidence expectations separately from statutory actor-specific applicability.",
                                "system_id":sid,"basis_type":"internal-policy","category":"draft-policy-observation","evidence_ids":fact_ids+[policy["id"],exception_policy["id"]],
                                "source_reported_evidence_status":fact["values"]["evidence_status"],"review_state":policy_kind,
                                "exception_limit":"A Legal-reviewed internal exception request is not automatically a statutory exemption.",
                                "approval_status":"pending","policy_provenance":"Manual reference, not successful live Notion retrieval", "compliance_status":"not-determined"})
        questions.append({"id":"question-"+sid,"summary":"Legal to review the scoped draft applicability; owners to resolve reported evidence/role questions without inferred approval.",
                          "system_id":sid,"evidence_ids":fact_ids+[role["id"],transition["id"]],"owner":fact["values"]["owner"],
                          "unresolved_source_records":[r["source_record_id"] for r in incidents if r["values"]["evidence_state"] != "complete"],
                          "resolution_need":"Verify facts and underlying artifacts; preserve reported conflicts/staleness/partial proof and obtain version-bound Legal review.",
                          "specific_questions":{
                              "AI-003":["Resolve REC-003 published-copy metadata conflict; source completeness does not prove metadata survival.","Verify underlying product market-entry notice and actor-specific transition basis."],
                              "AI-005":["Refresh development/commissioning/branding and current-release facts for provider role.","Determine current biometric emotion/intent/category use; human review alone does not settle it.","Establish product market entry and synthetic-content scope before transition reasoning."],
                              "AI-007":["Resolve REC-008 owner/banner versus current-capture conflict.","Assess whether the interaction itself is obvious; the stylized fictional avatar alone is insufficient."],
                              "AI-008":["Retain the visible-label report without assuming full statutory disclosure fulfilment.","Verify machine-readable provenance, REC-009 partial proof and REC-010's absent approval/expiry.","An internal-policy exception is not an automatic statutory deepfake exemption; verify provider transition separately."]
                          }.get(sid,["Confirm scoped interface/role and source evidence; no compliance or exemption follows automatically."]),
                          "category":"unresolved-question"})
    return {"impacts":impacts,"unaffected_items":[{"id":"unaffected-"+r["id"],"summary":"Scoped draft non-applicability only; not global no-impact or final compliance.","evidence_ids":[r["id"]],"system_id":r["system_id"],"subject_actor":r["subject_actor"],"rule_refs":r["rule_refs"]} for r in impacts if r["draft_applicability"] == NO],
            "conflicts":copy.deepcopy(state4["conflicts"]),"unresolved_items":questions,
            "role_assessments":roles,"transition_assessments":transitions,"policy_expectations":policy_findings,
            "observed_evidence":copy.deepcopy(state4["evidence_state_observations"]),
            "observed_approval_limits":copy.deepcopy(state4["approval_observations"]),
            "source_context_provenance":{"case_observation_date":review["observed_date"],"authoring_clarification_date":review["authored_date"],
                                         "manual_context_version":context_header["manual_provenance"].get("claimed_context_revision"),
                                         "policy_version":context_header["manual_provenance"].get("claimed_policy_version"),
                                         "evidence_ids":[context_header["id"]],"raw_sha256":context_header["raw_sha256"],"independently_verified":False},
            "scope_limits":{"statutory_review":"Actor/rule/use-specific draft; no final compliance determinations", "other_duties":"Article 50(6) preserves other obligations; codes under amended 50(7) are not company approval",
                            "legal_evidence_ids":legal("rule-50-6","rule-50-7-amended"),"manual_context":"Recorded training-case facts support draft reasoning but do not refresh stale evidence or prove Legal approval"}}


def analyze(four, three):
    review = operating.assess(four)
    state = _analyze_reviewed(four, three, review)
    return operating.apply(state, four, review)


def build(stage04, root=ROOT):
    four, chain, raw = inputs(stage04, root)
    state = analyze(four, chain[3])
    state.update(as_of=four["state"]["as_of"],as_of_convention=four["state"]["as_of_convention"],legal_approval="pending",final_compliance_status="not-determined")
    decisions = [{"id":"d-impact-scope","summary":"Analyze actor/rule/use-specific draft applicability while retaining evidence uncertainty.",
                  "evidence_ids":[r["id"] for r in state["role_assessments"]+state["transition_assessments"]],
                  "concern":"Avoid inventory-label roles, global exemptions, blanket December deferral or invented approval.",
                  "options":["Combine enacted provisions with recorded operating facts and scoped uncertainty", "Treat inventory labels, old questionnaires or human review as settling applicability"],
                  "chosen_behavior":"Separate company and product-provider duties, policy observations, evidence states and conditional timing.",
                  "rationale":"Recorded product market entry and role facts have different meanings from content publication, inventory names or evidence completeness.",
                  "tradeoffs":["Useful scoped draft exclusions and triggers remain subject to manual provenance and Legal review; they are not final compliance findings."],
                  "downstream_effect":"Later actions/approval work must preserve conflicts and resolve the specific reviewer questions without using draft timing as an operational deadline."}]
    own_keys = ("impacts","unaffected_items","unresolved_items","role_assessments","transition_assessments","policy_expectations","review_blockers")
    produced = [r["id"] for k in own_keys for r in state.get(k, [])]+[d["id"] for d in decisions]
    if len(produced) != len(set(produced)):
        raise ValueError("Duplicate impact identifiers")
    legal_ids = chain[3]["produced_record_ids"]
    consumed = list(dict.fromkeys(four["produced_record_ids"]+legal_ids))
    if four["state"].get("analysis_profile"):
        consumed.append(four["state"]["analysis_profile"]["id"])
    result = {"schema_version":four["schema_version"],"snapshot_id":"snapshot-"+str(uuid4()),"run_id":four["run_id"],
              "stage":"impact-analysis","sequence":5,"created_at":now(),"status":"blocked",
              "predecessor":{"snapshot_id":four["snapshot_id"],"path":str(stage04),"sha256":digest(raw)},
              "consumed_record_ids":consumed,"produced_record_ids":produced,"state":state,
              "unresolved":copy.deepcopy(four["unresolved"])+state["unresolved_items"]+state.get("review_blockers", []),"decisions":decisions}
    validate(result, root)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reconciliation",type=Path,default=ROOT/"deliverables/snapshots/04-evidence-reconciliation.json")
    parser.add_argument("--output",type=Path,default=ROOT/"deliverables/snapshots/05-impact-analysis.json")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = build(args.reconciliation.resolve())
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open("x",encoding="utf-8") as output:
        json.dump(result,output,indent=2,ensure_ascii=False)
        output.write("\n")
    print(f"Stage 05 schema-valid; draft impacts remain subject to Legal review: {args.output}")


if __name__ == "__main__":
    main()
