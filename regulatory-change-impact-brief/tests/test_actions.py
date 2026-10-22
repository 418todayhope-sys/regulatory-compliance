import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import actions


class ActionsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.selected=actions.ROOT/"deliverables/snapshots/05-impact-analysis.json"
        cls.five,cls.four,cls.chain,cls.raw=actions.inputs(cls.selected)
        cls.result=actions.build(cls.selected)
        cls.state=cls.result["state"]
        cls.proposals={r["id"]:r for r in cls.state["proposed_actions"]}
        cls.requests={r["id"]:r for r in cls.state["approval_requirements"]}

    def test_existing_calendar_identity_owner_date_requirements_and_version_preserved(self):
        for row in self.four["state"]["calendar_records"]:
            values=row["values"]
            proposal=self.proposals[values["action_id"]]
            self.assertEqual(proposal["source_calendar_values"],values)
            self.assertEqual(proposal["owner"],values["owner"])
            self.assertEqual(proposal["proposed_due_date"],values["due_date"])
            self.assertEqual(proposal["proposed_action"],values["action"])
            self.assertEqual(proposal["approval_required"],values["approval_required"])
            self.assertEqual(proposal["source_version"],values["source_version"])
            self.assertIn(row["id"],proposal["evidence_ids"])

    def test_single_global_act008_is_not_fanned_out(self):
        proposal=self.proposals["ACT-008"]
        self.assertEqual(proposal["system_id"],"ALL")
        self.assertEqual(proposal["scope"]["type"],"global")
        self.assertEqual(len(proposal["scope"]["system_ids"]),8)
        self.assertEqual([r["source_action_id"] for r in self.state["proposed_actions"]].count("ACT-008"),1)
        self.assertEqual(len(proposal["dependent_legal_request_ids"]),8)
        factual=self.requests["REQ-FACTS-ACT-008"]
        self.assertEqual(factual["required_reviewer"],"System owners")
        self.assertIn("Assessment Operations",factual["reviewer_roles"])

    def test_nine_additional_actions_stay_undated_and_transition_is_not_a_deadline(self):
        new=[r for r in self.state["proposed_actions"] if r["source_action_id"] is None]
        self.assertEqual(len(new),9)
        self.assertTrue(all(r["proposed_due_date"] is None for r in new))
        self.assertTrue(all(r["approved_operational_deadline"] is None for r in self.state["proposed_actions"]))
        self.assertNotIn("2026-12-02",[r["proposed_due_date"] for r in self.state["proposed_actions"]])
        self.assertEqual(self.proposals["PROP-AI-008-MARKET"]["owner"],"Communications")

    def test_legal_operations_and_factual_authorities_are_distinct(self):
        for r in self.state["approval_requirements"]:
            if r["request_type"].startswith("legal-") or r["request_type"]=="exception-decision":
                self.assertEqual(r["required_reviewer"],"Legal")
            if r["request_type"]=="operational-date-and-policy-review":
                self.assertEqual(r["required_reviewer"],"Operations")
        self.assertEqual(self.requests["REQ-FACTS-ACT-005"]["required_reviewer"],"Assessment Operations")
        self.assertEqual(self.requests["REQ-FACTS-PROP-AI-008-EXCEPTION-FACTS"]["required_reviewer"],"Communications")
        self.assertEqual(self.proposals["ACT-007"]["owner"],"Legal")
        self.assertEqual(self.requests["REQ-LEGAL-EXCEPTION-AI-008"]["required_reviewer"],"Legal")

    def test_every_approval_pending_unsent_and_without_feedback(self):
        self.assertEqual(len(self.requests),43)
        self.assertTrue(all(r["status"]=="pending" and r["delivery_status"]=="not-sent" and r["feedback"] is None for r in self.requests.values()))
        self.assertTrue(all(r["approval_status"]=="pending" and r["date_approval_status"]=="pending" for r in self.proposals.values()))
        self.assertEqual(self.state["actual_feedback_applied"],[])
        self.assertEqual(self.proposals["ACT-008"]["source_status"],"scheduled")

    def test_specific_conflicts_release_and_provenance_work_preserved(self):
        self.assertIn("REC-003"," ".join(self.proposals["ACT-004"]["acceptance_criteria"]))
        self.assertIn("REC-008"," ".join(self.proposals["ACT-002"]["acceptance_criteria"]))
        self.assertIn("biometric"," ".join(self.proposals["ACT-005"]["acceptance_criteria"]))
        self.assertIn("REC-009"," ".join(self.proposals["ACT-006"]["acceptance_criteria"]))
        self.assertIn("REC-010"," ".join(self.proposals["ACT-007"]["acceptance_criteria"]))
        self.assertIn("statutory",self.requests["REQ-LEGAL-EXCEPTION-AI-008"]["question"])
        self.assertIn("historical guidance",self.requests["REQ-LEGAL-AUTHORITY"]["question"])

    def test_material_findings_have_targeted_actions_and_rule_citations(self):
        findings={r["id"]:r for r in self.five["state"]["impacts"]}
        for finding_id,action_ids in self.state["material_finding_action_links"].items():
            finding=findings[finding_id]
            self.assertTrue(any(self.proposals[i]["system_id"]==finding["system_id"] for i in action_ids))
        for p in self.proposals.values():
            self.assertTrue(p["impact_ids"] or p["policy_finding_ids"])
            if p["impact_ids"]:
                self.assertTrue(p["rule_refs"])
                self.assertTrue(p["legal_citation_ids"])
            else:
                self.assertTrue(p["policy_rule_ids"])
                self.assertEqual(p["basis_types"],["internal-policy","evidence-provenance"])

    def test_request_subject_run_sources_and_review_basis_are_exact(self):
        expected={"snapshot_id":self.five["snapshot_id"],"path":str(self.selected),"sha256":actions.digest(self.raw)}
        for request in self.requests.values():
            self.assertEqual(request["review_basis_snapshot"],expected)
            self.assertEqual(request["run_id"],self.five["run_id"])
            self.assertEqual(request["source_versions"]["calendar_versions"],["calendar-2026-08-26"])
            self.assertEqual(request["final_draft_binding_status"],"pending-stage-07")
            self.assertTrue(request["subject"]["action_ids"])
        for sid in actions.impact.SYSTEM_IDS:
            self.assertEqual(len(self.requests["REQ-LEGAL-"+sid]["subject"]["impact_ids"]),8)

    def test_schema_snapshot_linkage_all_references_and_inherited_unresolved(self):
        s=self.result
        actions.validate(s)
        self.assertEqual(s["sequence"],6)
        self.assertEqual(s["predecessor"]["sha256"],actions.digest(self.raw))
        self.assertEqual(s["run_id"],self.five["run_id"])
        self.assertEqual(s["state"]["as_of"],"2026-08-26T00:00:00Z")
        self.assertEqual(s["unresolved"][:len(self.five["unresolved"])],self.five["unresolved"])
        known=set(s["produced_record_ids"]+s["consumed_record_ids"])
        records=s["state"]["proposed_actions"]+s["state"]["approval_requirements"]+s["state"]["escalations"]+[s["state"]["version_context"]]+s["unresolved"]+s["decisions"]
        self.assertTrue(all(set(r["evidence_ids"])<=known for r in records))
        self.assertEqual(len(s["produced_record_ids"]),len(set(s["produced_record_ids"])))
        for p in self.proposals.values():
            self.assertTrue(set(p["approval_request_ids"])<=set(self.requests))

    def test_source_status_cannot_approve_and_blank_date_stays_blank(self):
        changed=copy.deepcopy(self.four)
        row=next(r for r in changed["state"]["calendar_records"] if r["source_record_id"]=="ACT-001")
        row["values"]["status"]="approved"
        row["values"]["due_date"]=""
        state=actions.assemble(self.five,changed,self.chain,self.result["predecessor"])
        proposal=next(r for r in state["proposed_actions"] if r["id"]=="ACT-001")
        self.assertEqual(proposal["source_status"],"approved")
        self.assertEqual(proposal["source_calendar_values"]["due_date"],"")
        self.assertIsNone(proposal["proposed_due_date"])
        self.assertEqual(proposal["approval_status"],"pending")
        self.assertIsNone(proposal["approved_operational_deadline"])

    def test_invalid_date_and_changed_calendar_identity_fail_closed(self):
        changed=copy.deepcopy(self.four)
        changed["state"]["calendar_records"][0]["values"]["due_date"]="2026/09/04"
        with self.assertRaises(ValueError):
            actions.assemble(self.five,changed,self.chain,self.result["predecessor"])
        changed=copy.deepcopy(self.four)
        changed["state"]["calendar_records"][0]["values"]["action"]="Activate policy without review"
        with self.assertRaises(ValueError):
            actions.assemble(self.five,changed,self.chain,self.result["predecessor"])
        changed=copy.deepcopy(self.four)
        changed["state"]["calendar_records"][0]["values"]["system_id"]="AI-999"
        with self.assertRaises(ValueError):
            actions.assemble(self.five,changed,self.chain,self.result["predecessor"])

    def test_cli_creates_only_stage06_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/"06.json"
            command=[sys.executable,str(Path(actions.__file__)),"--output",str(output)]
            result=subprocess.run(command,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            before=output.read_bytes()
            self.assertEqual(list(Path(directory).iterdir()),[output])
            self.assertNotEqual(subprocess.run(command,capture_output=True).returncode,0)
            self.assertEqual(output.read_bytes(),before)

    def test_modified_findings_and_bad_predecessor_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            changed=copy.deepcopy(self.five)
            changed["state"]["impacts"][0]["summary"]="Unbacked conclusion"
            path=Path(directory)/"changed.json"
            path.write_text(json.dumps(changed))
            with self.assertRaises(ValueError):
                actions.build(path)
            changed=copy.deepcopy(self.five)
            changed["predecessor"]["sha256"]="sha256:"+"0"*64
            path.write_text(json.dumps(changed))
            with self.assertRaises(ValueError):
                actions.build(path)
