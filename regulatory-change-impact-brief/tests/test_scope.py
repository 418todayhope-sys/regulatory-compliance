import copy
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from jsonschema.exceptions import ValidationError

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/scope.py"
spec = importlib.util.spec_from_file_location("scope", SCRIPT)
scope = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scope)


class ScopeTests(unittest.TestCase):
    def test_valid_scope_preserves_unknowns_and_lineage(self):
        snapshot = scope.build_scope()
        scope.validate(snapshot)
        self.assertEqual(snapshot["state"]["as_of"], "2026-08-26T00:00:00Z")
        self.assertEqual(snapshot["state"]["system_ids"], [])
        self.assertEqual(snapshot["state"]["expected_system_count"], 8)
        self.assertEqual(snapshot["state"]["audiences"], ["Legal", "Operations"])
        self.assertEqual(snapshot["state"]["approval_status"], "pending")
        self.assertEqual(snapshot["status"], "partial")
        self.assertIsNone(snapshot["predecessor"])
        self.assertEqual(snapshot["consumed_record_ids"], [])
        records = (snapshot["state"]["evidence_records"] + snapshot["unresolved"] + snapshot["decisions"])
        self.assertEqual(set(snapshot["produced_record_ids"]), {r["id"] for r in records})
        ids = {r["id"] for r in records}
        self.assertTrue(all(set(r["evidence_ids"]) <= ids for r in records))
        for record in snapshot["state"]["evidence_records"]:
            self.assertEqual(record["sha256"], "sha256:" + scope.hashlib.sha256(
                (scope.ROOT / record["path"]).read_bytes()).hexdigest())

    def test_fresh_ids(self):
        first, second = scope.build_scope(), scope.build_scope()
        for key in ("run_id", "snapshot_id"):
            self.assertNotEqual(first[key], second[key])

    def test_schema_rejects_invalid_date_and_first_stage_link(self):
        for change in ({"created_at": "not-a-date"}, {"consumed_record_ids": ["invented"]}):
            snapshot = copy.deepcopy(scope.build_scope())
            snapshot.update(change)
            with self.assertRaises(ValidationError):
                scope.validate(snapshot)

    def test_cli_creates_only_scope_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "01-scope.json"
            command = [sys.executable, str(SCRIPT), "--output", str(output)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            before = output.read_bytes()
            self.assertEqual(list(Path(directory).iterdir()), [output])
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(output.read_bytes(), before)

    def test_missing_inputs_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                scope.build_scope(Path(directory))
