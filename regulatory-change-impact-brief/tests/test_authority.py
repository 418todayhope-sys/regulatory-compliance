import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import authority


class AuthorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.selected = authority.ROOT / "deliverables/snapshots/02-source-capture-attempt-004.json"
        cls.previous = json.loads(cls.selected.read_bytes())
        cls.snapshot = authority.build(cls.selected)

    def changed_capture(self, directory, name, transform, update_hash=True):
        previous = copy.deepcopy(self.previous)
        record = next(r for r in previous["state"]["sources"] if r["source_name"] == name)
        path = Path(directory) / "changed.response"
        path.write_bytes(transform(Path(record["local_reference"]).read_bytes()))
        record["local_reference"] = str(path)
        if update_hash:
            record["content_hash"] = authority.digest(path.read_bytes())
        snapshot = Path(directory) / "changed-capture.json"
        snapshot.write_text(json.dumps(previous))
        return snapshot

    def test_schema_run_and_exact_predecessor(self):
        s = self.snapshot
        authority.validate(s)
        self.assertEqual(s["sequence"], 3)
        self.assertEqual(s["run_id"], self.previous["run_id"])
        self.assertEqual(s["predecessor"]["snapshot_id"], self.previous["snapshot_id"])
        self.assertEqual(s["predecessor"]["sha256"], authority.digest(self.selected.read_bytes()))
        self.assertEqual(s["state"]["as_of"], "2026-08-26T00:00:00Z")
        self.assertEqual(s["consumed_record_ids"], self.previous["produced_record_ids"])

    def test_entry_application_and_conditional_transition_separate(self):
        rules = {r["id"]: r for r in self.snapshot["state"]["timing_rules"]}
        self.assertEqual(rules["timing-original-entry"]["date"], "2024-08-01")
        self.assertEqual(rules["timing-amendment-entry"]["date"], "2026-07-27")
        self.assertEqual(rules["timing-general"]["date"], "2026-08-02")
        transition = rules["timing-50-2-transition"]
        self.assertEqual(transition["date"], "2026-12-02")
        self.assertEqual(transition["conditions"], {"role": "provider", "obligation": "Article 50(2)", "system_placed_on_market_before": "2026-08-02"})
        self.assertEqual(transition["system_eligibility"], "unresolved")
        self.assertTrue(all(d["retrieved_at"] != self.snapshot["state"]["as_of"] for d in self.snapshot["state"]["source_documents"].values()))

    def test_authority_versions_and_amendment_relationship(self):
        state = self.snapshot["state"]
        docs = state["source_documents"]
        for name in ("OJ", "AMEND"):
            self.assertEqual(docs[name]["authority"], "binding")
        self.assertEqual(docs["CONSOLIDATED"]["authority"], "reference-only")
        self.assertEqual(docs["CONSOLIDATED"]["identity"]["consolidation_date"], "2026-07-27")
        for name in ("LAW", "TIME", "FAQ"):
            self.assertEqual(docs[name]["authority"], "advisory")
        self.assertIn("internal-policy", state["authority_hierarchy"])
        self.assertEqual(len(state["version_relationships"]), 1)
        self.assertEqual({r["rule_ref"] for r in state["binding_rules"] if r["id"].startswith("rule-")},
                         {f"Article 50({n})" for n in range(1,7)} | {"Article 50(7), as amended"})
        self.assertEqual(state["legal_approval"], "pending")
        self.assertEqual(state["system_findings"], [])

    def test_all_citations_reproduce_exact_source_spans_and_hashes(self):
        s = self.snapshot
        ids = set(s["consumed_record_ids"] + s["produced_record_ids"])
        texts = {}
        for citation in s["state"]["citations"]:
            raw = Path(citation["path"]).read_bytes()
            self.assertEqual(authority.digest(raw), citation["raw_sha256"])
            text = texts.setdefault(citation["path"], authority.visible_text(raw)[0])
            locator = citation["locator"]
            self.assertEqual(text[locator["start"]:locator["end"]], citation["excerpt"])
            self.assertEqual(authority.digest(citation["excerpt"].encode()), citation["excerpt_sha256"])
        for key in ("citations", "binding_rules", "timing_rules", "guidance_context", "authority_blockers", "version_relationships", "supported_interpretations"):
            for record in s["state"][key]:
                self.assertTrue(set(record["evidence_ids"]) <= ids)
        self.assertEqual(len(s["produced_record_ids"]), len(set(s["produced_record_ids"])))

    def test_known_faq_error_and_historical_uncertainty_preserved(self):
        blockers = {r["id"] for r in self.snapshot["state"]["authority_blockers"]}
        self.assertTrue({"u-faq-cross-reference", "u-historical-guidance", "u-system-applicability", "u-policy-and-approval"} <= blockers)
        self.assertEqual(self.snapshot["state"]["timing_conflicts"], [])
        self.assertEqual(self.snapshot["status"], "blocked")

    def test_corrupt_source_withholds_its_rules(self):
        with tempfile.TemporaryDirectory() as directory:
            selected = self.changed_capture(directory, "OJ", lambda b: b+b"changed", update_hash=False)
            result = authority.build(selected)
            self.assertNotIn("rule-50-1", {r["id"] for r in result["state"]["binding_rules"]})
            self.assertIn("u-authority-source-oj", {r["id"] for r in result["state"]["authority_blockers"]})
            authority.validate(result)

    def test_wrong_consolidated_version_not_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            selected = self.changed_capture(directory, "CONSOLIDATED", lambda b: b.replace(b"27.07.2026", b"12.07.2024"))
            result = authority.build(selected)
            self.assertNotIn("CONSOLIDATED", result["state"]["source_documents"])
            self.assertIn("u-authority-source-consolidated", {r["id"] for r in result["state"]["authority_blockers"]})

    def test_changed_faq_timing_is_a_conflict_not_new_law(self):
        with tempfile.TemporaryDirectory() as directory:
            selected = self.changed_capture(directory, "FAQ", lambda b: b.replace(b"applies as from 2 August 2026", b"applies as from 2 September 2026"))
            result = authority.build(selected)
            self.assertEqual(result["state"]["timing_conflicts"][0]["id"], "u-faq-timing-conflict")
            self.assertEqual(next(r["date"] for r in result["state"]["timing_rules"] if r["id"] == "timing-general"), "2026-08-02")

    def test_bad_lineage_and_overwrite_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            previous = copy.deepcopy(self.previous)
            previous["predecessor"]["sha256"] = "sha256:"+"0"*64
            path = Path(directory)/"bad.json"
            path.write_text(json.dumps(previous))
            with self.assertRaises(ValueError):
                authority.build(path)
            output = Path(directory)/"existing.json"
            output.write_text("preserve")
            result = subprocess.run([sys.executable, str(Path(authority.__file__)), "--output", str(output)], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(output.read_text(), "preserve")

    def test_review_date_cannot_follow_retrieval_date(self):
        with tempfile.TemporaryDirectory() as directory:
            previous = copy.deepcopy(self.previous)
            previous["state"]["as_of"] = "2026-10-19T00:00:00Z"
            path = Path(directory)/"changed-review-date.json"
            path.write_text(json.dumps(previous))
            with self.assertRaises(ValueError):
                authority.build(path)
