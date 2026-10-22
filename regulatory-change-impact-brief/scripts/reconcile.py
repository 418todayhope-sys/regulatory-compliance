"""Stage 04: reconcile source-reported evidence, without legal/system decisions."""
import argparse
import copy
import json
from pathlib import Path
import re
from uuid import uuid4

from capture import digest, now
from scope import ROOT, validate
import registers


def load_chain(path, root=ROOT):
    chain = {}
    selected_raw = path.read_bytes()
    raw = selected_raw
    for sequence in (3, 2, 1):
        snapshot = json.loads(raw)
        validate(snapshot, root)
        expected_stage = {3: "authority-and-timing", 2: "source-capture", 1: "scope"}[sequence]
        if snapshot["sequence"] != sequence or snapshot["stage"] != expected_stage:
            raise ValueError("Unexpected Stage 01–03 chain")
        if snapshot["state"]["as_of"] != "2026-08-26T00:00:00Z":
            raise ValueError("Assigned review date changed")
        chain[sequence] = snapshot
        if sequence < 3 and snapshot["run_id"] != chain[3]["run_id"]:
            raise ValueError("Cross-run predecessor")
        if sequence > 1:
            predecessor = snapshot["predecessor"]
            raw = Path(predecessor["path"]).read_bytes()
            if digest(raw) != predecessor["sha256"] or json.loads(raw)["snapshot_id"] != predecessor["snapshot_id"]:
                raise ValueError("Predecessor hash/identity mismatch")
    for record in chain[1]["state"]["evidence_records"]:
        if digest((root / record["path"]).read_bytes()) != record["sha256"]:
            raise ValueError("Scope document/interview hash mismatch")
    return chain, selected_raw


def verified_tables(capture):
    """Recheck both derived artifacts and their actual raw rows; never trust flags alone."""
    tables = capture["state"]["register_tables"]
    for table in tables:
        raw = Path(table["raw_reference"]).read_bytes()
        artifact = Path(table["extracted_reference"]).read_bytes()
        if digest(raw) != table["raw_sha256"] or digest(artifact) != table["extracted_sha256"]:
            raise ValueError("Register raw/derived evidence hash mismatch")
        stored = json.loads(artifact)
        if {k:v for k,v in table.items() if k not in {"extracted_reference", "extracted_sha256"}} != stored:
            raise ValueError("Snapshot table differs from captured extraction artifact")
        source = next(r for r in capture["state"]["sources"] if r["id"] in table["evidence_ids"])
        if source["content_hash"] != table["raw_sha256"] or source["local_reference"] != table["raw_reference"]:
            raise ValueError("Table/raw source binding mismatch")
        parsed, _ = registers.extract(table["source_name"], raw, source["content_type"], [{"gid":table["gid"], "name":table["tab_name"]}])
        matches = [p for p in parsed if p["gid"] == table["gid"] and p["tab_name"] == table["tab_name"]]
        if len(matches) != 1 or any(matches[0][k] != table[k] for k in ("headers", "records", "record_ids", "record_count")):
            raise ValueError("Extracted table is not reproduced by the raw evidence")
    checks = registers.validate_relationships(tables)
    if not checks["valid"] or checks != capture["state"]["register_validation"]:
        raise ValueError("Register validation failed: " + "; ".join(checks["errors"]))
    return tables, checks


def source_rows(tables, name):
    choices = [t for t in tables if t["source_name"] == name]
    canonical = next((t for t in choices if t["format"] == "csv"), choices[0])
    key = registers.HEADERS[name][0]
    result = []
    for row in canonical["records"]:
        values = copy.deepcopy(row["values"])
        source_id = values[key]
        provenance = []
        for table in choices:
            match = next(r for r in table["records"] if r["values"][key] == source_id)
            provenance.append({"table_id": table["id"], "source_attempt_ids": table["evidence_ids"],
                               "workbook_id": table["workbook_id"], "tab_name": table["tab_name"], "gid": table["gid"],
                               "row_number": match["row_number"], "column_names": table["headers"], "format": table["format"],
                               "original_url": table["original_url"], "retrieval_url": table["retrieval_url"],
                               "retrieved_at": table["retrieved_at"], "raw_reference": table["raw_reference"],
                               "raw_sha256": table["raw_sha256"], "extracted_reference": table["extracted_reference"],
                               "extracted_sha256": table["extracted_sha256"]})
        result.append({"id": f"row-{name.lower()}-{source_id}", "summary": f"{name} source-reported record {source_id}; not independently corroborated.",
                       "evidence_ids": [t["id"] for t in choices], "source_record_id": source_id, "source_name": name,
                       "system_id": values["system_id"], "category": "source-fact", "values": values,
                       "source_record_version": values.get("record_version", values.get("source_version")),
                       "version_note": "Null means no row version supplied; raw capture hash remains the exact evidence version.",
                       "provenance": provenance, "independently_corroborated": False, "approval_verified": False})
    return result


def policy_context(capture, root):
    result = []
    for manual in capture["state"].get("manual_references", []):
        raw = (root / manual["path"]).read_bytes()
        if digest(raw) != manual["sha256"]:
            raise ValueError("Manual POLICY reference hash mismatch")
        lines = raw.decode("utf-8").splitlines(keepends=True)
        heads = [i for i,line in enumerate(lines) if line.startswith("#")]
        for index, start in enumerate(heads):
            end = heads[index+1] if index+1 < len(heads) else len(lines)
            text = "".join(lines[start:end])
            heading = lines[start].lstrip("#").strip()
            if not any(line.strip() for line in lines[start+1:end]):
                continue
            result.append({"id": f"policy-supplement-{index:02}", "summary": f"Manual POLICY supplemental context: {heading}; provenance unverified.",
                           "evidence_ids": [manual["id"]], "category": "supplemental-manual-context", "heading": heading,
                           "system_id": heading if re.fullmatch(r"AI-\d{3}", heading) else None,
                           "excerpt": text, "path": manual["path"], "raw_sha256": manual["sha256"],
                           "locator": {"line_start": start+1, "line_end": end, "lines": "one-based inclusive"},
                           "excerpt_sha256": digest(text.encode("utf-8")), "manual_provenance": copy.deepcopy(manual),
                           "live_retrieval": False, "independently_corroborated": False, "approval_verified": False,
                           "limits": "Manual context does not replace missing source evidence, refresh stale records, prove approval or establish legal applicability."})
    return result


def assemble(chain, tables, checks, root=ROOT):
    """Pure reconciliation of validated source rows; no legal applicability decisions."""
    systems = source_rows(tables, "SYSTEMS")
    incidents = source_rows(tables, "EVIDENCE")
    calendar = source_rows(tables, "CALENDAR")
    policy = policy_context(chain[2], root)
    states, gaps, conflicts, observations, approvals = [], [], [], [], []
    by_system = {r["system_id"]:r for r in systems}
    kinds = {"missing":"missing", "stale":"stale", "conflicting":"conflicting", "partial":"partial",
             "unknown":"unverified", "unverified":"unverified", "not_applicable":"not-applicable", "not-applicable":"not-applicable", "complete":"complete"}
    for row in systems+incidents:
        fields = ("evidence_status", "current_notice", "provider_role") if row["source_name"] == "SYSTEMS" else ("evidence_state",)
        for field in fields:
            raw_value = row["values"].get(field)
            if raw_value not in kinds:
                continue
            kind = kinds[raw_value]
            state = {"id": f"state-{row['source_record_id']}-{field}", "summary": f"{row['source_record_id']}.{field} reports {raw_value!r}; scope is this field only.",
                     "evidence_ids": [row["id"]], "system_id": row["system_id"], "category": "source-state-observation",
                     "source_record_id": row["source_record_id"], "field": field, "reported_value": raw_value, "evidence_kind": kind,
                     "independently_corroborated": False}
            states.append(state)
            if kind in {"missing", "stale", "partial", "unverified"}:
                gaps.append({"id": f"gap-{row['source_record_id']}-{field}", "summary": state["summary"],
                             "evidence_ids": [state["id"], row["id"]], "category": "unresolved-question", "system_id": row["system_id"],
                             "source_record_id": row["source_record_id"], "evidence_kind": kind,
                             "owner": row["values"].get("owner"), "reported_details": row["values"].get("notes"),
                             "resolution_need": "Owner must provide current scoped proof/clarification; no compliance conclusion or date is assigned."})
        if row["source_name"] == "EVIDENCE" and row["values"].get("evidence_state") == "conflicting":
            system = by_system[row["system_id"]]
            conflicts.append({"id": "conflict-"+row["source_record_id"], "summary": f"Preserve {row['source_record_id']} reported conflict without selecting a winning claim.",
                              "evidence_ids": [row["id"],system["id"]], "system_id":row["system_id"], "category":"reported-conflict",
                              "source_record_id":row["source_record_id"], "owner":row["values"].get("owner"),
                              "reported_details": row["values"]["notes"], "system_reported_values": copy.deepcopy(system["values"]),
                              "resolution_need":"Owner must reconcile underlying artifacts and reports; existing reported labels remain unchanged.", "resolution_status":"unresolved"})
    for system in systems:
        sid = system["system_id"]
        evidence_rows = [r for r in incidents if r["system_id"] == sid]
        actions = [r for r in calendar if r["system_id"] == sid]
        observations.append({"id":"join-"+sid,"summary":f"{sid}: joined {len(evidence_rows)} evidence/incident records and {len(actions)} system-specific calendar records by exact system_id.",
                             "evidence_ids":[r["id"] for r in [system]+evidence_rows+actions],"category":"inferred-observation", "system_id":sid,
                             "system_record_id":system["source_record_id"],"evidence_record_ids":[r["source_record_id"] for r in evidence_rows],
                             "calendar_record_ids":[r["source_record_id"] for r in actions],
                             "supplemental_context_ids":[r["id"] for r in policy if r["system_id"] == sid],
                             "interpretation_limit":"Join/count observation only; no legal applicability, eligibility, compliance, approval or operational-date decision."})
    for row in calendar:
        approvals.append({"id":"approval-observation-"+row["source_record_id"],"summary":f"{row['source_record_id']}: reported calendar status/required reviewer are not evidence of an actual approval.",
                          "evidence_ids":[row["id"]],"category":"approval-observation","system_id":row["system_id"],"source_record_id":row["source_record_id"],
                          "reported_status":row["values"]["status"],"reported_approval_required":row["values"]["approval_required"],
                          "approval_state":"unverified","approval_verified":False})
    for row in incidents:
        if row["values"].get("record_type") == "exception_request":
            approvals.append({"id":"approval-observation-"+row["source_record_id"],"summary":"Exception request remains a source-reported request; no authenticated Legal approval or expiry is supplied.",
                              "evidence_ids":[row["id"]],"source_record_id":row["source_record_id"],"system_id":row["system_id"],"category":"approval-observation",
                              "reported_status":row["values"]["status"],"reported_details":row["values"]["notes"],"approval_state":"unverified",
                              "approval_verified":False,"expiry_date":None})
        if row["source_record_id"] == "REC-009" and row["values"].get("notes") == "Visible label verified but machine-readable provenance not checked":
            observations.append({"id":"observation-REC-009-facets","summary":"REC-009 reports visible-label verification separately from unchecked machine-readable provenance; partial evidence is not complete provenance proof.",
                                 "evidence_ids":[row["id"]],"category":"inferred-observation","system_id":row["system_id"],"source_record_id":"REC-009",
                                 "facets":{"visible_label":"source-reported verified", "machine_readable_provenance":"unverified"},"independently_corroborated":False})
    general_gap = {"id":"u-reconciliation-proof","summary":"Downloaded register rows and manual context are source reports, not independently verified underlying artifacts or approvals.",
                   "evidence_ids":[r["id"] for r in incidents+policy],"category":"unresolved-question","owner":"System owners / Operations / Legal",
                   "resolution_need":"Obtain underlying proof and authorized version-bound feedback; preserve all Stage 03 authority and POLICY-access blockers."}
    gaps.append(general_gap)
    result = {"system_facts":systems,"policy_controls":policy,"incident_evidence":incidents,"calendar_records":calendar,
            "conflicts":conflicts,"evidence_gaps":gaps,"evidence_state_observations":states,"inferred_observations":observations,
            "approval_observations":approvals,"global_calendar_record_ids":[r["source_record_id"] for r in calendar if r["system_id"] == "ALL"],
            "coverage":{"system_count":len(systems),"system_ids":sorted(by_system),"evidence_record_count":len(incidents),"calendar_record_count":len(calendar)},
            "register_validation":checks,"tab_discovery_limitation":registers.LIMITATION,
            "legal_applicability":"not-determined","transition_eligibility":"not-determined","compliance_status":"not-determined",
            "date_handling":"Source dates are retained verbatim; no operational date is assigned, approved or changed."}
    if chain[1]["state"].get("analysis_profile"):
        result["analysis_profile"] = copy.deepcopy(chain[1]["state"]["analysis_profile"])
    return result


def build(stage03, root=ROOT):
    chain, raw = load_chain(stage03, root)
    tables, checks = verified_tables(chain[2])
    state = assemble(chain, tables, checks, root)
    state.update({"as_of":chain[1]["state"]["as_of"],"as_of_convention":chain[1]["state"]["as_of_convention"],
                  "selected_capture_snapshot_id":chain[2]["snapshot_id"]})
    decisions = [{"id":"d-evidence-reconciliation","summary":"Reconcile matching register representations by exact system_id and retain their source-reported distinctions.",
                  "evidence_ids":[t["id"] for t in tables],"concern":"Avoid overwriting evidence states or converting reports into approval/compliance conclusions.",
                  "options":["Preserve matching HTML/CSV rows with both provenances", "Treat a newer/manual statement or complete field as resolving every evidence question"],
                  "chosen_behavior":"Use CSV values only after HTML agreement; retain both row locators, conflicts, scoped gaps and manual provenance separately.",
                  "rationale":"The interview requires unresolved/conflicting proof to stay visible for owners and authorized reviewers.",
                  "tradeoffs":["Duplicate source representations add provenance but do not supply independent corroboration."],
                  "downstream_effect":"Later stages must determine applicability and request actual decisions without treating this reconciliation as approval."}]
    keys = ("system_facts","policy_controls","incident_evidence","calendar_records","conflicts","evidence_gaps","evidence_state_observations","inferred_observations","approval_observations")
    produced = [r["id"] for k in keys for r in state[k]]+[r["id"] for r in decisions]
    if len(produced) != len(set(produced)):
        raise ValueError("Duplicate reconciliation record IDs")
    consumed = list(dict.fromkeys(chain[3]["produced_record_ids"]+[t["id"] for t in tables]+[m["id"] for m in chain[2]["state"].get("manual_references",[])]))
    if state.get("analysis_profile"):
        consumed.append(state["analysis_profile"]["id"])
    result = {"schema_version":chain[3]["schema_version"],"snapshot_id":"snapshot-"+str(uuid4()),"run_id":chain[3]["run_id"],
              "stage":"evidence-reconciliation","sequence":4,"created_at":now(),"status":"blocked",
              "predecessor":{"snapshot_id":chain[3]["snapshot_id"],"path":str(stage03),"sha256":digest(raw)},
              "consumed_record_ids":consumed,"produced_record_ids":produced,"state":state,
              "unresolved":copy.deepcopy(chain[3]["unresolved"])+state["conflicts"]+state["evidence_gaps"],"decisions":decisions}
    validate(result, root)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authority",type=Path,default=ROOT/"deliverables/snapshots/03-authority-and-timing.json")
    parser.add_argument("--output",type=Path,default=ROOT/"deliverables/snapshots/04-evidence-reconciliation.json")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = build(args.authority.resolve())
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open("x",encoding="utf-8") as output:
        json.dump(result,output,indent=2,ensure_ascii=False)
        output.write("\n")
    print(f"Stage 04 schema-valid; evidence/authority questions remain unresolved: {args.output}")


if __name__ == "__main__":
    main()
