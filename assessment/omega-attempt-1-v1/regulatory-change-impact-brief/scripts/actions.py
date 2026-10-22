"""Stage 06: reviewable proposals and unsent, version-bound review requests only."""
import argparse
import copy
from datetime import date
import json
from pathlib import Path
from uuid import uuid4

from capture import digest, now
import impact
from scope import ROOT, validate

EXISTING = {
    "ACT-001": ("AI-004", ["product-provider-50-1", "company-50-1"],
                "Document the actual first-interaction notice, interface and provider/deployer responsibilities; prepare any notice change for authorized review, without changing production."),
    "ACT-002": ("AI-007", ["product-provider-50-1", "deployer-50-4-deepfake"],
                "Compare the owner banner report with the current capture using matching page/release/time; retain REC-008 until reconciled. Ask Legal about interaction obviousness separately from the fictional graphic."),
    "ACT-003": ("AI-002", ["deployer-50-4-text", "product-provider-50-1", "product-provider-50-2"],
                "Confirm individual human-mediated email and recipient-disclosure practice with evidence; distinguish internal disclosure expectations from the public-interest publication trigger and supplier duties."),
    "ACT-004": ("AI-003", ["product-provider-50-2", "deployer-50-4-deepfake"],
                "Provide original/exported/published-copy metadata checks and explain REC-003's conflicting reports. A visible label or SYSTEMS complete field must not be used as provenance proof."),
    "ACT-005": ("AI-005", ["company-50-1", "company-50-2", "deployer-50-3", "deployer-50-4-deepfake", "deployer-50-4-text", "company-50-5", "product-provider-50-1", "product-provider-50-2"],
                "Supply current development/commissioning/branding and release records, biometric emotion/intent/category-use facts, synthetic-output scope and product market-entry evidence. Keep REC-005 stale until an actual refresh; human review does not settle these questions."),
    "ACT-006": ("AI-008", ["product-provider-50-2", "deployer-50-4-deepfake"],
                "Provide technical verification of machine-readable provenance through export/publication, retaining REC-009's separate visible-label and unchecked-provenance facets."),
    "ACT-007": ("AI-008", ["deployer-50-4-deepfake", "company-50-5"],
                "Legal must review the exception request's owner, rationale, absent expiry and absent approval; distinguish an internal-policy exception from any actual statutory qualification. Keep REC-010 unapproved until matching authorized feedback exists."),
    "ACT-008": ("ALL", [],
                "Coordinate one global evidence-register review across the eight systems; retain open conflicts and source states, request owner updates, and route interpretation/dates/activation to the authorized roles."),
}
SOURCE_TITLES = {
    "ACT-001":"Add and verify first-interaction AI notice",
    "ACT-002":"Resolve disclosure evidence conflict",
    "ACT-003":"Confirm recipient disclosure practice",
    "ACT-004":"Verify machine-readable provenance after publishing",
    "ACT-005":"Refresh provider-role and release evidence",
    "ACT-006":"Complete provenance test",
    "ACT-007":"Review exception request",
    "ACT-008":"Quarterly AI register evidence review",
}


def inputs(stage05, root=ROOT):
    raw = stage05.read_bytes()
    five = json.loads(raw)
    validate(five, root)
    if five["stage"] != "impact-analysis" or five["sequence"] != 5:
        raise ValueError("Expected Stage 05")
    parent = Path(five["predecessor"]["path"])
    if digest(parent.read_bytes()) != five["predecessor"]["sha256"]:
        raise ValueError("Stage 04 predecessor hash mismatch")
    four, chain, _ = impact.inputs(parent, root)
    if five["predecessor"]["snapshot_id"] != four["snapshot_id"] or five["run_id"] != four["run_id"]:
        raise ValueError("Stage 05 predecessor/run identity mismatch")
    if five["state"]["as_of"] != four["state"]["as_of"]:
        raise ValueError("Assigned review date changed")
    expected = impact.analyze(four, chain[3])
    if any(five["state"].get(key) != value for key,value in expected.items()):
        raise ValueError("Stage 05 findings are not reproduced by their legal and factual basis")
    return five, four, chain, raw


def assemble(five, four, chain, review_basis):
    """Prepare proposals; never read source statuses as approvals or execute work."""
    findings = {r["id"]:r for r in five["state"]["impacts"]}
    facts = {r["system_id"]:r for r in four["state"]["system_facts"]}
    source_actions = {r["source_record_id"]:r for r in four["state"]["calendar_records"]}
    if set(source_actions) != set(EXISTING):
        raise ValueError("Expected ACT-001 through ACT-008; review changed calendar identities")
    policy = {r["heading"]:r for r in four["state"]["policy_controls"]}
    policy_ids = [policy[h]["id"] for h in ("Learner and public transparency", "Evidence and exceptions", "Approval boundary") if h in policy]
    proposals = []

    def propose(action_id, sid, title, owner, keys, acceptance, source=None, policy_only=False):
        scope = sorted(facts) if sid == "ALL" else [sid]
        linked = list(findings.values()) if sid == "ALL" and not policy_only else [findings[f"impact-{sid}-{key}"] for key in keys]
        policy_findings = [r["id"] for r in five["state"]["policy_expectations"] if r["system_id"] in scope]
        citations = list(dict.fromkeys(c for r in linked for c in r["legal_citation_ids"]))
        basis = [r["id"] for r in linked]+policy_findings+policy_ids+citations
        basis += [r["id"] for r in four["state"]["system_facts"]+four["state"]["incident_evidence"] if r["system_id"] in scope]
        basis += [r["id"] for r in five["state"]["transition_assessments"] if r["system_id"] in scope]
        if source:
            basis.append(source["id"])
        values = copy.deepcopy(source["values"]) if source else None
        due = values["due_date"] if values else None
        if due:
            if date.fromisoformat(due).isoformat() != due:
                raise ValueError("Calendar date must be YYYY-MM-DD")
        proposal = {"id":action_id,"action_id":action_id,"summary":title+" — reviewable proposal; not authorized execution.",
                    "evidence_ids":list(dict.fromkeys(basis)),"system_id":sid,"scope":{"type":"global" if sid=="ALL" else "system","system_ids":scope},
                    "proposed_action":title,"owner":owner,"owner_basis":"source CALENDAR owner" if source else "proposed routing to recorded system/policy owner",
                    "source_action_id":values["action_id"] if values else None,"source_calendar_values":values,
                    "source_status":values["status"] if values else None,"source_version":values["source_version"] if values else None,
                    "approval_required":values["approval_required"] if values else None,
                    "proposed_due_date":due or None,"approved_operational_deadline":None,"approval_status":"pending","date_approval_status":"pending",
                    "date_basis":"Unchanged source calendar proposal; not an approved operational deadline" if due else "No date supplied for this proposal; remain undated pending Operations authorization",
                    "acceptance_criteria":[acceptance,"Retain source evidence IDs/versions and report the observed result; do not claim resolution or approval without actual matching evidence/decision."],
                    "impact_ids":[r["id"] for r in linked],"policy_finding_ids":policy_findings,
                    "rule_refs":list(dict.fromkeys(ref for r in linked for ref in r["rule_refs"])),"legal_citation_ids":citations,
                    "policy_rule_ids":policy_ids,"basis_types":["internal-policy","evidence-provenance"] if policy_only else ["statutory-draft-findings","internal-policy","source-evidence"],
                    "proposal_status":"draft","execution_status":"not-authorized-by-this-snapshot","approval_request_ids":[]}
        proposals.append(proposal)
        return proposal

    for action_id,(sid,keys,acceptance) in EXISTING.items():
        source = source_actions[action_id]
        if source["values"]["system_id"] != sid:
            raise ValueError("Changed calendar system identity: " + action_id)
        if " ".join(source["values"]["action"].casefold().split()) != SOURCE_TITLES[action_id].casefold():
            raise ValueError("Changed calendar action meaning requires review: " + action_id)
        propose(action_id,sid,source["values"]["action"],source["values"]["owner"],keys,acceptance,source)

    additions = [
        ("PROP-AI-001-FACTS","AI-001","Confirm current chat notice/interface and supplier evidence",["product-provider-50-1","product-provider-50-2"],
         "Verify REC-001's notice/release evidence and actual direct interface; obtain supplier role, synthetic-output/marking and obviousness facts without converting complete source fields into corroborated compliance."),
        ("PROP-AI-006-FACTS","AI-006","Confirm internal-use boundary and supplier-interface evidence",["product-provider-50-1","product-provider-50-2","deployer-50-4-text"],
         "Verify REC-007's restricted staff use and absence of public publication, then obtain supplier interface/marking scope; internal use alone must not be treated as a blanket provider exemption."),
        ("PROP-AI-003-MARKET","AI-003","Obtain the current image product's release/interface and market-entry proof",["product-provider-50-1","product-provider-50-2"],
         "Obtain the supplier's current-product release/interface and market-entry notice underlying the recorded entry date, with version/locator; route interaction/obviousness and conditional provider-only Article 50(2) transition interpretation to Legal."),
        ("PROP-AI-008-MARKET","AI-008","Obtain the current audio/video product's release/interface and market-entry proof",["product-provider-50-1","product-provider-50-2"],
         "Obtain the current product's supplier release/interface and market-entry notice. Do not substitute a video export date or use the provider marking transition to defer deployer disclosure."),
        ("PROP-AI-004-PRODUCT-FACTS","AI-004","Confirm pronunciation product interface and output-generation scope",["product-provider-50-1","product-provider-50-2"],
         "Provide current technical descriptions and representative outputs to establish direct-interaction and synthetic-content scope. Pronunciation evaluation alone does not prove generation, emotion recognition or an obviousness exception."),
        ("PROP-AI-007-PRODUCT-FACTS","AI-007","Confirm website guide product interface and output-generation scope",["product-provider-50-1","product-provider-50-2"],
         "Provide the current product/interface description and output examples to establish synthetic-content and interaction scope; retain the REC-008 banner conflict and do not use a fictional graphic as proof of obvious AI interaction."),
        ("PROP-AI-008-DISCLOSURE","AI-008","Review first-exposure disclosure sufficiency",["deployer-50-4-deepfake","company-50-5"],
         "Provide the actual visible/audible label, placement, first-exposure and accessibility evidence for the manipulated presenter videos; request Legal interpretation and Operations authorization for any change, without declaring the existing label sufficient or insufficient."),
        ("PROP-AI-008-EXCEPTION-FACTS","AI-008","Complete factual support for the exception review",["deployer-50-4-deepfake","company-50-5"],
         "Provide REC-010's named owner/rationale and request an authorized expiry proposal; leave absent expiry and approval unknown. Supply the facts to ACT-007's Legal review, without inventing an exception or statutory waiver."),
    ]
    for action_id,sid,title,keys,acceptance in additions:
        propose(action_id,sid,title,facts[sid]["values"]["owner"],keys,acceptance)
    access = propose("PROP-POLICY-ACCESS","ALL","Establish legitimate POLICY access and manual-reference provenance","Operations",[],
                     "Confirm the approved policy/version and provenance through its intended route; keep manual acquisition limits and failed live Notion access visible. Do not activate policy or replace the live read silently.",policy_only=True)
    access["evidence_ids"] += [r["id"] for r in chain[2]["state"]["sources"] if r["source_name"]=="POLICY"]

    review_blockers = five['state'].get('review_blockers', [])
    for sid in sorted({r['system_id'] for r in review_blockers}):
        current = [r for r in review_blockers if r['system_id'] == sid]
        keys = [r['id'].removeprefix('impact-' + sid + '-') for r in findings.values() if r['system_id'] == sid]
        proposal = propose('PROP-' + sid + '-CURRENT-FACTS', sid,
                           'Resolve current input changes and review affected interpretations', facts[sid]['values']['owner'], keys,
                           'Reconcile current source versions and facts, then obtain Legal interpretation and Operations authorization. ' +
                           ' '.join(r['summary'] for r in current))
        proposal['evidence_ids'] += [r['id'] for r in current]
        for p in proposals:
            if p['system_id'] == sid and p['id'] != proposal['id']:
                p['acceptance_criteria'][0] = 'Review the current changed/missing facts before retaining any earlier interpretation. ' + ' '.join(r['summary'] for r in current)
                p['evidence_ids'] += [r['id'] for r in current]

    source_versions = {"calendar_versions":sorted({r["values"]["source_version"] for r in source_actions.values()}),
                       "system_register_versions":sorted({r["values"]["record_version"] for r in facts.values()}),
                       "manual_policy_claimed_version":five["state"]["source_context_provenance"]["policy_version"],
                       "manual_context_claimed_version":five["state"]["source_context_provenance"]["manual_context_version"]}
    version = {"id":"version-actions-inputs","summary":"Exact review-input/source versions; final deliverable hashes do not exist at Stage 06.",
               "evidence_ids":[r["id"] for r in chain[2]["state"]["sources"]],"run_id":five["run_id"],
               "impact_snapshot":review_basis,"source_versions":source_versions,
               "source_captures":[{"id":r["id"],"original_url":r["original_url"],"requested_url":r["requested_url"],"retrieved_at":r["retrieved_at"],"content_hash":r["content_hash"],"local_reference":r["local_reference"],"version_metadata":r["version_metadata"]} for r in chain[2]["state"]["sources"]],
               "final_draft_binding_status":"pending-stage-07","manual_provenance_limits":"Claimed policy/context versions, not a successful live Notion read or approval."}
    requests = []
    def request(request_id,reviewer,kind,subjects,question,extra=None,reviewer_roles=None):
        impacts = list(dict.fromkeys(i for p in subjects for i in p["impact_ids"]))
        refs = [version["id"]]+[p["id"] for p in subjects]+impacts+list(extra or [])
        record = {"id":request_id,"request_id":request_id,"summary":f"Unsent {kind} request to {reviewer}.","evidence_ids":list(dict.fromkeys(refs)),
                  "status":"pending","required_reviewer":reviewer,"reviewer_roles":reviewer_roles or [reviewer],"request_type":kind,"question":question,
                  "subject":{"system_ids":sorted({s for p in subjects for s in p["scope"]["system_ids"]}),"action_ids":[p["id"] for p in subjects],"impact_ids":impacts},
                  "run_id":five["run_id"],"source_versions":source_versions,"review_basis_snapshot":review_basis,"version_context_id":version["id"],
                  "delivery_status":"not-sent","feedback":None,"final_draft_binding_status":"pending-stage-07"}
        requests.append(record)
        for p in subjects:
            p["approval_request_ids"].append(request_id)
        return record

    for sid in sorted(facts):
        subjects = [p for p in proposals if p["system_id"]==sid]
        question = next(r for r in five["state"]["unresolved_items"] if r["system_id"]==sid)
        legal_request = request("REQ-LEGAL-"+sid,"Legal","legal-interpretation",subjects,
                "Confirm the actor/rule/use-specific draft applicability, exclusions and provider-only transition; do not infer compliance or a statutory waiver. " + " ".join(question["specific_questions"]),
                extra=[question["id"]]+[r["id"] for r in five["state"]["impacts"] if r["system_id"]==sid])
        legal_request["subject"]["impact_ids"] = [r["id"] for r in five["state"]["impacts"] if r["system_id"]==sid]
    global_action = next(p for p in proposals if p["id"]=="ACT-008")
    global_action["dependent_legal_request_ids"] = ["REQ-LEGAL-"+sid for sid in sorted(facts)]
    request("REQ-LEGAL-AUTHORITY","Legal","legal-authority-review",[global_action],
            "Confirm the enacted/amended/consolidated hierarchy, historical guidance suitability and FAQ Article 50(2)/50(1) cross-reference discrepancy. Confirm the limited provider-only transition is not a blanket postponement.",
            extra=[r["id"] for r in chain[3]["state"]["authority_blockers"]])
    exception = next(p for p in proposals if p["id"]=="ACT-007")
    request("REQ-LEGAL-EXCEPTION-AI-008","Legal","exception-decision",[exception],
            "Is the version-specific internal exception request authorized, rejected or in need of changes, with reasons/conditions and any authorized expiry? Separately determine whether any statutory qualification exists; no statutory waiver follows from an internal exception.",extra=[r["id"] for r in four["state"]["incident_evidence"] if r["source_record_id"]=="REC-010"])

    for proposal in proposals:
        request("REQ-OPS-"+proposal["id"],"Operations","operational-date-and-policy-review",[proposal],
                (f"Confirm or revise the source-proposed date {proposal['proposed_due_date']} through an actual version-bound decision; it is not an approved deadline. " if proposal["proposed_due_date"] else
                 "No date is supplied for this new proposal: authorize a proposed date or confirm it must remain undated. ")+
                "Confirm any policy activation/scheduling authority needed before implementation; this draft activates nothing and closes no incident.")
        if proposal["id"]=="ACT-007":
            continue  # Legal owns this source action; supporting facts have their own Communications proposal.
        global_review = proposal["id"]=="ACT-008"
        factual_owner = "System owners" if global_review else proposal["owner"]
        request("REQ-FACTS-"+proposal["id"],factual_owner,"factual-confirmation",[proposal],
                "Provide the scoped artifacts/corrections and versions required by this action's acceptance criteria; factual confirmation does not approve legal interpretation, policy activation or operational deadlines.",
                reviewer_roles=sorted({r["values"]["owner"] for r in facts.values()}) if global_review else None)

    escalations = []
    for sid in ("AI-002","AI-003","AI-005","AI-007","AI-008"):
        subjects = [p for p in proposals if p["system_id"]==sid]
        escalations.append({"id":"escalation-"+sid,"summary":"Source evidence/interpretation remains unresolved; the proposed work and pending requests do not close it.",
                            "evidence_ids":[p["id"] for p in subjects]+["question-"+sid],"system_id":sid,"owner":facts[sid]["values"]["owner"],
                            "legal_reviewer":"Legal","date_and_policy_authority":"Operations","resolution_status":"unresolved","due_date":None,
                            "resolution_need":"Obtain scoped factual evidence and matching authorized decisions; retain current source states until then."})
    escalations.append({"id":"escalation-authority-policy","summary":"Stage 03 Legal/guidance questions and live POLICY/manual-provenance limits remain unresolved.",
                        "evidence_ids":["PROP-POLICY-ACCESS"]+[r["id"] for r in chain[3]["state"]["authority_blockers"]],"owner":"Legal / Operations",
                        "resolution_status":"unresolved","due_date":None,"resolution_need":"Legal reviews authority, historical guidance and FAQ questions; Operations establishes legitimate policy access/provenance."})
    coverage = {r["id"]: [p["id"] for p in proposals if r["id"] in p["impact_ids"]] for r in five["state"]["impacts"] if r["state"] in {"supported-impact","unresolved","conflicting"}}
    if any(not any(p["system_id"]==r["system_id"] and r["id"] in p["impact_ids"] for p in proposals) for r in five["state"]["impacts"] if r["id"] in coverage):
        raise ValueError("Material finding has no proposed action")
    return {"proposed_actions":proposals,"approval_requirements":requests,"escalations":escalations,
            "version_context":version,"material_finding_action_links":coverage,
            "approval_boundary":{"Legal":"Legal interpretation and exception decisions", "Operations":"Policy activation and operational dates; incident closure remains a human decision", "System owners":"Factual correction and scoped proof only", "automation":"Prepare local draft proposals and unsent requests only"},
            "source_calendar_reconciliation":{"preserved_ids":sorted(source_actions),"global_action_id":"ACT-008","source_rows_modified":False,"dates_are_approved_deadlines":False},
            "actual_feedback_applied":[],"final_draft_binding_status":"pending-stage-07","as_of":five["state"]["as_of"],"as_of_convention":five["state"]["as_of_convention"]}


def build(stage05, root=ROOT):
    five, four, chain, raw = inputs(stage05, root)
    review_basis = {"snapshot_id":five["snapshot_id"],"path":str(stage05),"sha256":digest(raw)}
    state = assemble(five,four,chain,review_basis)
    decisions = [{"id":"d-actions-and-approvals","summary":"Preserve source calendar proposals and add undated review work without promoting dates/statuses to approval.",
                  "evidence_ids":[p["id"] for p in state["proposed_actions"]],"concern":"Keep source ownership, proposal dates, review authority and actual version-bound decisions distinct.",
                  "options":["Retain source actions and prepare explicit pending review requests", "Infer approval from scheduled/open statuses or derive new dates from statutory transitions"],
                  "chosen_behavior":"Preserve ACT-001–ACT-008 exactly in source fields, keep ACT-008 global, add undated proposals and route scoped unsent requests.",
                  "rationale":"No actual version-specific feedback or authorized dates for the additional work are supplied.",
                  "tradeoffs":["The draft is reviewable but cannot claim delivery, approval, execution, policy activation or incident closure."],
                  "downstream_effect":"Stage 07 must bind requests to exact final draft paths/hashes before any future feedback can be applied."}]
    records=state["proposed_actions"]+state["approval_requirements"]+state["escalations"]+[state["version_context"]]+decisions
    ids=[r["id"] for r in records]
    if len(ids)!=len(set(ids)):
        raise ValueError("Duplicate action/request record IDs")
    consumed=list(dict.fromkeys(five["produced_record_ids"]+four["produced_record_ids"]+[i for s in chain.values() for i in s["produced_record_ids"]]))
    result={"schema_version":five["schema_version"],"snapshot_id":"snapshot-"+str(uuid4()),"run_id":five["run_id"],
            "stage":"actions-and-approvals","sequence":6,"created_at":now(),"status":"blocked",
            "predecessor":review_basis,"consumed_record_ids":consumed,"produced_record_ids":ids,"state":state,
            "unresolved":copy.deepcopy(five["unresolved"])+state["escalations"],"decisions":decisions}
    validate(result,root)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--impact",type=Path,default=ROOT/"deliverables/snapshots/05-impact-analysis.json")
    parser.add_argument("--output",type=Path,default=ROOT/"deliverables/snapshots/06-actions-and-approvals.json")
    args=parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result=build(args.impact.resolve())
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open("x",encoding="utf-8") as output:
        json.dump(result,output,indent=2,ensure_ascii=False)
        output.write("\n")
    print(f"Stage 06 schema-valid; all proposals/requests pending and unsent: {args.output}")


if __name__=="__main__":
    main()
