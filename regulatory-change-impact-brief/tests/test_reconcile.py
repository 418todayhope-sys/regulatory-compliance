import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import reconcile


class ReconciliationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.selected = reconcile.ROOT/"deliverables/snapshots/03-authority-and-timing.json"
        cls.chain, _ = reconcile.load_chain(cls.selected)
        cls.result = reconcile.build(cls.selected)
        cls.state = cls.result["state"]

    def test_coverage_exact_joins_and_global_action(self):
        self.assertEqual(self.state["coverage"], {"system_count":8,"system_ids":[f"AI-{i:03}" for i in range(1,9)],"evidence_record_count":10,"calendar_record_count":8})
        joins = {r["system_id"]:r for r in self.state["inferred_observations"] if r["id"].startswith("join-")}
        self.assertEqual(joins["AI-005"]["evidence_record_ids"], ["REC-005","REC-006"])
        self.assertEqual(joins["AI-008"]["evidence_record_ids"], ["REC-009","REC-010"])
        self.assertEqual(joins["AI-008"]["calendar_record_ids"], ["ACT-006","ACT-007"])
        self.assertEqual(self.state["global_calendar_record_ids"], ["ACT-008"])
        self.assertTrue(all("ACT-008" not in r["calendar_record_ids"] for r in joins.values()))

    def test_source_values_versions_and_both_row_provenances_unchanged(self):
        tables = self.chain[2]["state"]["register_tables"]
        for row in self.state["system_facts"]+self.state["incident_evidence"]+self.state["calendar_records"]:
            self.assertEqual(len(row["provenance"]), 2)
            self.assertFalse(row["independently_corroborated"])
            for provenance in row["provenance"]:
                table = next(t for t in tables if t["id"] == provenance["table_id"])
                key = reconcile.registers.HEADERS[row["source_name"]][0]
                source = next(r for r in table["records"] if r["values"][key] == row["source_record_id"])
                self.assertEqual(row["values"], source["values"])
                self.assertEqual(provenance["row_number"], source["row_number"])
                self.assertEqual(provenance["retrieved_at"], table["retrieved_at"])
                self.assertEqual(reconcile.digest(Path(provenance["raw_reference"]).read_bytes()), provenance["raw_sha256"])
            self.assertEqual(row["source_record_version"],row["values"].get("record_version",row["values"].get("source_version")))

    def test_conflicts_stale_partial_and_exception_survive(self):
        conflicts = {r["source_record_id"]:r for r in self.state["conflicts"]}
        self.assertEqual(set(conflicts), {"REC-003","REC-008"})
        self.assertEqual(conflicts["REC-003"]["system_reported_values"]["evidence_status"], "complete")
        self.assertEqual(conflicts["REC-008"]["reported_details"], "Owner says a banner exists but the current capture shows none")
        records = {r["source_record_id"]:r for r in self.state["incident_evidence"]}
        self.assertEqual(records["REC-005"]["values"]["evidence_state"], "stale")
        self.assertEqual(records["REC-009"]["values"]["evidence_state"], "partial")
        facets = next(r["facets"] for r in self.state["inferred_observations"] if r["id"] == "observation-REC-009-facets")
        self.assertEqual(facets["machine_readable_provenance"], "unverified")
        self.assertEqual(records["REC-010"]["values"]["status"], "draft")
        exception = next(r for r in self.state["approval_observations"] if r["source_record_id"] == "REC-010")
        self.assertFalse(exception["approval_verified"])
        self.assertIsNone(exception["expiry_date"])

    def test_evidence_states_are_scoped_and_not_applicable_is_not_no_impact(self):
        states = self.state["evidence_state_observations"]
        self.assertTrue({"missing","stale","conflicting","partial","unverified","not-applicable"} <= {r["evidence_kind"] for r in states})
        record = next(r for r in states if r["evidence_kind"] == "not-applicable")
        self.assertEqual(record["system_id"], "AI-006")
        self.assertEqual(record["field"], "current_notice")
        self.assertEqual(record["reported_value"], "not_applicable")
        self.assertEqual(self.state["compliance_status"], "not-determined")
        self.assertEqual(self.state["legal_applicability"], "not-determined")
        self.assertEqual(self.state["transition_eligibility"], "not-determined")

    def test_manual_policy_exact_sections_and_provenance_limits(self):
        for context in self.state["policy_controls"]:
            raw = (reconcile.ROOT/context["path"]).read_bytes()
            self.assertEqual(reconcile.digest(raw),context["raw_sha256"])
            lines = raw.decode().splitlines(keepends=True)
            locator = context["locator"]
            self.assertEqual("".join(lines[locator["line_start"]-1:locator["line_end"]]),context["excerpt"])
            self.assertFalse(context["live_retrieval"])
            self.assertFalse(context["approval_verified"])
            self.assertIsNone(context["manual_provenance"]["manual_retrieved_at"])
        self.assertTrue(any("expiry date, and Legal approval" in r["excerpt"] for r in self.state["policy_controls"]))
        self.assertTrue(any(r["system_id"] == "AI-005" for r in self.state["policy_controls"]))

    def test_schema_linkage_references_and_inherited_unresolved(self):
        s = self.result
        reconcile.validate(s)
        self.assertEqual(s["sequence"],4)
        self.assertEqual(s["predecessor"]["sha256"],reconcile.digest(self.selected.read_bytes()))
        self.assertEqual(s["run_id"],self.chain[3]["run_id"])
        self.assertEqual(s["state"]["as_of"], "2026-08-26T00:00:00Z")
        inherited = self.chain[3]["unresolved"]
        self.assertEqual(s["unresolved"][:len(inherited)],inherited)
        ids = set(s["produced_record_ids"])
        self.assertEqual(len(ids),len(s["produced_record_ids"]))
        for previous in self.chain.values():
            ids.update(previous["produced_record_ids"])
        for key in ("system_facts","policy_controls","incident_evidence","calendar_records","conflicts","evidence_gaps","evidence_state_observations","inferred_observations","approval_observations"):
            self.assertTrue(all(set(r["evidence_ids"]) <= ids for r in s["state"][key]))

    def test_dates_and_approval_requirements_not_promoted_to_decisions(self):
        for r in self.state["calendar_records"]:
            self.assertIn("due_date",r["values"])
            self.assertFalse(r["approval_verified"])
        self.assertTrue(all(r["approval_state"] == "unverified" for r in self.state["approval_observations"]))
        self.assertEqual(next(r["values"]["due_date"] for r in self.state["calendar_records"] if r["source_record_id"] == "ACT-007"),"2026-09-15")
        self.assertEqual(self.result["status"],"blocked")

    def test_raw_hash_mismatch_rejected(self):
        capture = copy.deepcopy(self.chain[2])
        with tempfile.TemporaryDirectory() as directory:
            table = capture["state"]["register_tables"][0]
            bad = Path(directory)/"damaged.response"
            bad.write_bytes(b"damaged")
            table["raw_reference"] = str(bad)
            with self.assertRaises(ValueError):
                reconcile.verified_tables(capture)

    def test_fabricated_extraction_with_matching_artifact_hash_rejected(self):
        capture = copy.deepcopy(self.chain[2])
        with tempfile.TemporaryDirectory() as directory:
            table = capture["state"]["register_tables"][0]
            table["records"][0]["values"]["owner"] = "Fabricated owner"
            target = Path(directory)/"forged-extract.json"
            target.write_text(json.dumps({k:v for k,v in table.items() if k not in {"extracted_reference","extracted_sha256"}}))
            table["extracted_reference"] = str(target)
            table["extracted_sha256"] = reconcile.digest(target.read_bytes())
            with self.assertRaises(ValueError):
                reconcile.verified_tables(capture)

    def test_join_validation_and_manual_hash_failure_rejected(self):
        capture = copy.deepcopy(self.chain[2])
        capture["state"]["register_validation"]["valid"] = False
        with self.assertRaises(ValueError):
            reconcile.verified_tables(capture)
        capture = copy.deepcopy(self.chain[2])
        capture["state"]["manual_references"][0]["sha256"] = "sha256:"+"0"*64
        with self.assertRaises(ValueError):
            reconcile.policy_context(capture,reconcile.ROOT)

    def test_cli_creates_only_stage04_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)/"04.json"
            command = [sys.executable,str(Path(reconcile.__file__)),"--output",str(output)]
            result = subprocess.run(command,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            before = output.read_bytes()
            self.assertEqual(list(Path(directory).iterdir()),[output])
            result = subprocess.run(command,capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertEqual(output.read_bytes(),before)

    def test_tampered_predecessor_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            bad = copy.deepcopy(self.chain[3])
            bad["predecessor"]["sha256"] = "sha256:"+"0"*64
            path = Path(directory)/"broken-stage03.json"
            path.write_text(json.dumps(bad))
            with self.assertRaises(ValueError):
                reconcile.build(path)
