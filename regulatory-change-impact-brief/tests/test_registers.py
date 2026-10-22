import copy
import csv
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import capture
import registers


class RegisterTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = json.loads((capture.ROOT / "deliverables/snapshots/02-source-capture-attempt-003.json").read_text())
        self.sources = {r["source_name"]: r for r in self.snapshot["state"]["sources"] if r["source_name"] in registers.HEADERS}

    def extracted(self):
        tables = []
        for name, record in self.sources.items():
            raw = Path(record["local_reference"]).read_bytes()
            self.assertEqual(capture.digest(raw), record["content_hash"])
            result, discovered = registers.extract(name, raw, record["content_type"], [{"gid": "0", "name": registers.TABS[name]}])
            self.assertEqual(discovered, [{"gid": "0", "name": registers.TABS[name]}])
            self.assertEqual(len(result), 1)
            result[0]["source_name"] = name
            tables.extend(result)
        return tables

    def test_capture003_grid_rows_headers_counts_and_interface_exclusion(self):
        tables = self.extracted()
        for table in tables:
            self.assertTrue(table["valid"], table["errors"])
            self.assertEqual(table["record_count"], {"SYSTEMS":8,"EVIDENCE":10,"CALENDAR":8}[table["source_name"]])
            self.assertEqual(table["headers"], registers.HEADERS[table["source_name"]])
            self.assertEqual(table["gid"], "0")
        result = registers.validate_relationships(tables)
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["system_ids"], [f"AI-{i:03}" for i in range(1,9)])
        self.assertFalse(result["approval_verified"])

    def test_states_and_unapproved_exception_preserved_exactly(self):
        tables = self.extracted()
        evidence = next(t for t in tables if t["source_name"] == "EVIDENCE")
        by_id = {r["values"]["record_id"]: r["values"] for r in evidence["records"]}
        for key, state in [("REC-002", "missing"), ("REC-003", "conflicting"), ("REC-005", "stale"), ("REC-009", "partial")]:
            self.assertEqual(by_id[key]["evidence_state"], state)
        self.assertEqual(by_id["REC-010"]["status"], "draft")
        self.assertEqual(by_id["REC-010"]["notes"], "No Legal approval or expiry date recorded")

    def test_reordered_headers_extra_columns_and_csv_roundtrip(self):
        for table in self.extracted():
            headers = list(reversed(table["headers"])) + ["unrelated"]
            rows = [headers] + [[r["values"].get(h, "extra") for h in headers] for r in table["records"]]
            output = io.StringIO(newline="")
            csv.writer(output).writerows(rows)
            result, _ = registers.extract(table["source_name"], output.getvalue().encode(), "text/csv", [{"gid": "0", "name": table["tab_name"]}])
            self.assertTrue(result[0]["valid"], result[0]["errors"])
            self.assertEqual(result[0]["record_ids"], table["record_ids"])

    def test_bad_headers_duplicate_ids_and_truncated_count_reported(self):
        table = self.extracted()[0]
        rows = [table["headers"]] + [list(r["values"].values()) for r in table["records"]]
        duplicate = copy.deepcopy(rows)
        duplicate[2][0] = duplicate[1][0]
        missing = copy.deepcopy(rows)
        missing[0][0] = "renamed_unknown_key"
        for broken in (duplicate, missing, rows[:-1]):
            self.assertFalse(registers.table("SYSTEMS", broken, "0", registers.TABS["SYSTEMS"])["valid"])

    def test_unknown_join_and_changed_csv_are_errors_all_action_is_allowed(self):
        tables = self.extracted()
        evidence = next(t for t in tables if t["source_name"] == "EVIDENCE")
        other = copy.deepcopy(evidence)
        other["records"][0]["values"]["system_id"] = "AI-999"
        result = registers.validate_relationships(tables + [other])
        self.assertTrue(any("disagree" in e for e in result["errors"]))
        self.assertTrue(any("AI-999" in e for e in result["errors"]))
        self.assertFalse(any("ALL" in e for e in registers.validate_relationships(tables)["errors"]))

    def test_no_grid_shell_and_unconfigured_extra_grid(self):
        result, _ = registers.extract("SYSTEMS", b"<table><tr><td>system_id</td></tr></table>", "text/html", [])
        self.assertEqual(result, [])
        parser = registers.Grids()
        parser.feed('<div id="0-grid-container"><table class="waffle"><tr><td>first</td></tr></table></div><div id="9-grid-container"><table class="waffle"><tr><td>second</td></tr></table></div>')
        self.assertEqual([t["gid"] for t in parser.tables], ["0", "9"])

    def test_blank_grid_rows_keep_physical_row_locators(self):
        parser = registers.Grids()
        parser.feed('<div id="0-grid-container"><table class="waffle"><tr><td>system_id</td></tr><tr><td></td></tr><tr><td>AI-001</td></tr></table></div>')
        result = registers.table("SYSTEMS", parser.tables[0]["rows"], "0", registers.TABS["SYSTEMS"])
        self.assertEqual(result["records"][0]["row_number"], 3)

    def test_capture_integration_csv_provenance_artifacts_and_preservation(self):
        fixtures = self.extracted()
        lookup = {r["original_url"]: r for r in self.sources.values()}
        calls = []
        def transport(url, timeout):
            calls.append(url)
            original = url.split("/export?")[0]
            if original in lookup:
                record = lookup[original]
                if "/export?" in url:
                    table = next(t for t in fixtures if t["source_name"] == record["source_name"])
                    output = io.StringIO(newline="")
                    csv.writer(output).writerows([table["headers"]] + [list(r["values"].values()) for r in table["records"]])
                    return {"status": 200, "url": url, "body": output.getvalue().encode(), "headers": {"Content-Type": "text/csv"}}
                return {"status": 200, "url": record["final_url"], "body": Path(record["local_reference"]).read_bytes(), "headers": {"Content-Type": "text/html"}}
            return {"status": 200, "url": url, "body": b"<title>Unverified fixture</title>", "headers": {"Content-Type": "text/html"}}
        with tempfile.TemporaryDirectory() as directory:
            path, snapshot = capture.capture(capture.ROOT / "deliverables/snapshots/01-scope.json", capture.ROOT / "regulatory-change-impact-brief/references/source-config.json", Path(directory) / "new", transport=transport)
            self.assertTrue(snapshot["state"]["register_validation"]["valid"])
            self.assertEqual(len(snapshot["state"]["register_tables"]), 6)
            capture.validate(json.loads(path.read_text()))
            for table in snapshot["state"]["register_tables"]:
                self.assertEqual(capture.digest(Path(table["raw_reference"]).read_bytes()), table["raw_sha256"])
                self.assertEqual(capture.digest(Path(table["extracted_reference"]).read_bytes()), table["extracted_sha256"])
                self.assertFalse(table["independently_corroborated"])
                self.assertFalse(table["approval_verified"])
                self.assertIn("retrieved_at", table)
                self.assertIn("tab_discovery_limitation", table)
                if table["format"] == "csv":
                    self.assertEqual(table["requested_url"], registers.csv_url(table["original_url"], table["gid"]))
                    self.assertGreater(calls.index(table["requested_url"]), calls.index(table["original_url"]))
