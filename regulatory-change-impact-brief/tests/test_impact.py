import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import impact


class ImpactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.selected = impact.ROOT/"deliverables/snapshots/04-evidence-reconciliation.json"
        cls.four, cls.chain, _ = impact.inputs(cls.selected)
        cls.result = impact.build(cls.selected)
        cls.state = cls.result["state"]
        cls.findings = {r["id"]:r for r in cls.state["impacts"]}

    def finding(self,sid,key):
        return self.findings[f"impact-{sid}-{key}"]

    def test_all_eight_systems_all_scoped_rules_and_applicability_categories(self):
        self.assertEqual(len(self.state["impacts"]),64)
        self.assertEqual({r["system_id"] for r in self.state["impacts"]},set(impact.SYSTEM_IDS))
        for sid in impact.SYSTEM_IDS:
            self.assertEqual(sum(r["system_id"]==sid for r in self.state["impacts"]),8)
        self.assertEqual({r["draft_applicability"] for r in self.state["impacts"]},{impact.APPLIES,impact.NO,impact.CONDITIONAL,impact.UNKNOWN})
        self.assertTrue(all(r["state"] in {"unresolved","conflicting"} for r in self.state["impacts"] if r["draft_applicability"]==impact.CONDITIONAL))

    def test_roles_use_operating_facts_not_system_names(self):
        roles = {r["system_id"]:r for r in self.state["role_assessments"]}
        for sid in impact.SYSTEM_IDS:
            self.assertEqual(roles[sid]["provider_assessment"],"unresolved" if sid=="AI-005" else "supported-draft-not-provider")
            self.assertEqual(roles[sid]["deployer_assessment"],"supported-draft-deployer")
        changed = copy.deepcopy(self.four)
        for r in changed["state"]["system_facts"]:
            r["values"]["system_name"]="Own-brand provider-like name is only an inventory label"
        self.assertEqual(impact.analyze(changed,self.chain[3])["role_assessments"],self.state["role_assessments"])
        self.assertEqual(self.finding("AI-003","company-50-2")["draft_applicability"],impact.NO)
        self.assertEqual(self.finding("AI-003","product-provider-50-2")["draft_applicability"],impact.APPLIES)

    def test_ai001_direct_notice_is_separate_from_company_provider_role(self):
        self.assertEqual(self.finding("AI-001","company-50-1")["draft_applicability"],impact.NO)
        self.assertEqual(self.finding("AI-001","product-provider-50-1")["draft_applicability"],impact.CONDITIONAL)
        self.assertTrue(self.finding("AI-001","product-provider-50-1")["conditional_on"])
        self.assertEqual(self.finding("AI-001","deployer-50-3")["draft_applicability"],impact.NO)

    def test_private_text_is_not_public_interest_publication_or_blanket_marking_exemption(self):
        for sid in ("AI-002","AI-006"):
            self.assertEqual(self.finding(sid,"deployer-50-4-text")["draft_applicability"],impact.NO)
            self.assertEqual(self.finding(sid,"product-provider-50-2")["draft_applicability"],impact.CONDITIONAL)
            # Staff are natural persons; lack of applicant interaction cannot exclude every supplier interface.
            self.assertEqual(self.finding(sid,"product-provider-50-1")["draft_applicability"],impact.CONDITIONAL)

    def test_illustrations_and_stylized_avatar_not_automatically_deepfakes_or_obvious_ai(self):
        for sid in ("AI-003","AI-007"):
            self.assertEqual(self.finding(sid,"deployer-50-4-deepfake")["draft_applicability"],impact.NO)
        guide=self.finding("AI-007","product-provider-50-1")
        self.assertEqual(guide["draft_applicability"],impact.CONDITIONAL)
        self.assertEqual(guide["state"],"conflicting")
        self.assertEqual(self.finding("AI-003","product-provider-50-2")["state"],"conflicting")

    def test_pronunciation_not_emotion_inference_and_assessment_uncertainty_remains(self):
        self.assertEqual(self.finding("AI-004","deployer-50-3")["draft_applicability"],impact.NO)
        self.assertEqual(self.finding("AI-004","product-provider-50-1")["draft_applicability"],impact.CONDITIONAL)
        for r in self.state["impacts"]:
            if r["system_id"]=="AI-005":
                self.assertEqual(r["draft_applicability"],impact.UNKNOWN)
                self.assertEqual(r["state"],"unresolved")
        question=next(r for r in self.state["unresolved_items"] if r["system_id"]=="AI-005")
        self.assertIn("REC-005",question["unresolved_source_records"])
        self.assertEqual(len(question["specific_questions"]),3)

    def test_ai008_deepfake_trigger_survives_provider_transition_and_unapproved_exception(self):
        disclosure=self.finding("AI-008","deployer-50-4-deepfake")
        self.assertEqual(disclosure["draft_applicability"],impact.APPLIES)
        self.assertEqual(disclosure["state"],"unresolved")
        self.assertIn("REC-009",disclosure["source_record_ids"])
        self.assertIn("REC-010",disclosure["source_record_ids"])
        self.assertEqual(self.finding("AI-008","company-50-5")["draft_applicability"],impact.APPLIES)
        exception=next(r for r in self.state["observed_approval_limits"] if r["source_record_id"]=="REC-010")
        self.assertFalse(exception["approval_verified"])
        self.assertIsNone(exception["expiry_date"])

    def test_transition_uses_product_entry_not_exports_and_is_scoped_to_provider_marking(self):
        transitions={r["system_id"]:r for r in self.state["transition_assessments"]}
        for sid in ("AI-003","AI-008"):
            r=transitions[sid]
            self.assertEqual(r["market_entry_date"],"2026-06-01")
            self.assertEqual(r["assessment"],"supported-draft-eligible")
            self.assertEqual(r["transition_phase"],"transition-active")
            self.assertEqual(r["scope"],"provider Article 50(2) only")
            self.assertIn("Article 50(4)",r["does_not_defer"])
        self.assertEqual(transitions["AI-005"]["assessment"],"unresolved")
        self.assertIsNone(transitions["AI-005"]["market_entry_date"])
        self.assertEqual(impact.transition_window("2026-08-01","2026-08-26")["assessment"],"supported-draft-eligible")
        self.assertEqual(impact.transition_window("2026-08-02","2026-08-26")["assessment"],"supported-draft-ineligible")
        self.assertEqual(impact.transition_window("2026-06-01","2026-12-02")["transition_phase"],"transition-date-reached-or-passed")
        self.assertEqual(impact.transition_window("2026-06-01","2026-08-26",actor_role="deployer")["assessment"],"not-applicable-to-this-actor")

    def test_changed_product_entry_changes_only_conditional_transition_not_deepfake_trigger(self):
        changed=copy.deepcopy(self.four)
        context=next(r for r in changed["state"]["policy_controls"] if r["heading"]=="Product timing and evidence limits")
        context["excerpt"]=context["excerpt"].replace("1 June 2026","2 August 2026")
        result=impact.analyze(changed,self.chain[3])
        self.assertTrue(all(r["assessment"]=="supported-draft-ineligible" for r in result["transition_assessments"] if r["system_id"] in {"AI-003","AI-008"}))
        disclosure=next(r for r in result["impacts"] if r["id"]=="impact-AI-008-deployer-50-4-deepfake")
        self.assertEqual(disclosure["draft_applicability"],impact.APPLIES)

    def test_citations_facts_graph_and_scope_linkage(self):
        result=self.result
        impact.validate(result)
        self.assertEqual(result["predecessor"]["sha256"],impact.digest(self.selected.read_bytes()))
        self.assertEqual(result["predecessor"]["snapshot_id"],self.four["snapshot_id"])
        self.assertEqual(result["run_id"],self.four["run_id"])
        self.assertEqual(result["state"]["as_of"],"2026-08-26T00:00:00Z")
        known=set(result["produced_record_ids"]+result["consumed_record_ids"])
        for s in list(self.chain.values())+[self.four]:
            known.update(s["produced_record_ids"])
        legal={r["id"] for r in self.chain[3]["state"]["citations"]}
        for r in self.state["impacts"]:
            self.assertTrue(r["legal_citation_ids"])
            self.assertTrue(set(r["legal_citation_ids"])<=legal)
            self.assertIn("row-systems-"+r["system_id"],r["evidence_ids"])
            self.assertTrue(r["manual_context_ids"])
            self.assertTrue(set(r["evidence_ids"])<=known)
        for key in ("role_assessments","transition_assessments","policy_expectations","unresolved_items","unaffected_items"):
            for r in self.state[key]:
                self.assertTrue(set(r["evidence_ids"])<=known)
        self.assertEqual(len(result["produced_record_ids"]),len(set(result["produced_record_ids"])))

    def test_prior_conflicts_policy_distinction_and_no_final_decisions(self):
        self.assertEqual(self.state["conflicts"],self.four["state"]["conflicts"])
        self.assertEqual(self.state["observed_evidence"],self.four["state"]["evidence_state_observations"])
        self.assertEqual(self.result["unresolved"][:len(self.four["unresolved"])],self.four["unresolved"])
        self.assertEqual(self.state["final_compliance_status"],"not-determined")
        for r in self.state["impacts"]+self.state["policy_expectations"]:
            self.assertEqual(r["approval_status"],"pending")
            self.assertNotIn("proposed_due_date",r)
        self.assertTrue(all(r["basis_type"]=="internal-policy" for r in self.state["policy_expectations"]))
        self.assertTrue(all(r["basis_type"]=="statutory" for r in self.state["impacts"]))

    def test_changed_operating_meaning_is_unresolved_and_missing_legal_basis_fails_closed(self):
        changed=copy.deepcopy(self.four)
        context=next(r for r in changed["state"]["policy_controls"] if r["heading"]=="AI-008")
        context["excerpt"]=context["excerpt"].replace("presenters are real people","presenters are fictional")
        result=impact.analyze(changed,self.chain[3])
        self.assertTrue(result["review_blockers"])
        self.assertTrue(all(r["draft_applicability"]==impact.UNKNOWN for r in result["impacts"] if r["system_id"]=="AI-008"))
        three=copy.deepcopy(self.chain[3])
        three["state"]["timing_rules"]=[r for r in three["state"]["timing_rules"] if r["id"]!="timing-50-2-transition"]
        with self.assertRaises(ValueError):
            impact.analyze(self.four,three)

    def test_cli_output_exclusivity_and_tampered_input(self):
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/"05.json"
            command=[sys.executable,str(Path(impact.__file__)),"--output",str(output)]
            result=subprocess.run(command,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            before=output.read_bytes()
            self.assertEqual(list(Path(directory).iterdir()),[output])
            self.assertNotEqual(subprocess.run(command,capture_output=True).returncode,0)
            self.assertEqual(output.read_bytes(),before)
            changed=copy.deepcopy(self.four)
            changed["state"]["system_facts"][0]["values"]["owner"]="Unbacked fact"
            bad=Path(directory)/"tampered.json"
            bad.write_text(json.dumps(changed))
            with self.assertRaises(ValueError):
                impact.build(bad)
