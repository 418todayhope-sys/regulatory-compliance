"""Offline relocation regression tests using copies of the actual saved package."""
import hashlib
import json
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import portable
import workflow

ROOT = Path(__file__).resolve().parents[2]
ORIGINAL = Path(json.loads((ROOT / 'deliverables/snapshots/07-publication-validation.json').read_bytes())
                ['predecessor']['path']).parents[2]


class PortableTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='project-b-relocation-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'checkout with spaces'
        self.root.mkdir()
        for name in ('deliverables', 'interviews', 'references', 'regulatory-change-impact-brief'):
            shutil.copytree(ROOT / name, self.root / name, ignore=shutil.ignore_patterns('__pycache__'))
        for name in ('README.md', 'Project_B_Learner_Assignment_Codex.md', 'snapshot.schema.json'):
            shutil.copy2(ROOT / name, self.root / name)

    def test_actual_relocated_bundle_verifies_offline_without_changes(self):
        before = {str(p.relative_to(self.root)): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in self.root.rglob('*') if p.is_file()}
        with patch.object(socket, 'create_connection', side_effect=AssertionError('Network forbidden')):
            result = portable.verify(self.root, ORIGINAL)
        command = [sys.executable, '-B', 'regulatory-change-impact-brief/scripts/portable.py',
                   '--original-root', str(ORIGINAL)]
        completed = subprocess.run(command, cwd=self.root, capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn('publication blocked', completed.stdout)
        self.assertEqual(result['state']['publication_status'], 'blocked')
        after = {str(p.relative_to(self.root)): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before, after)
        self.assertIs(workflow.Path, Path)

    def test_missing_local_bytes_never_fall_back_to_original_workspace(self):
        (self.root / 'deliverables/impact-register.csv').unlink()
        with self.assertRaises(FileNotFoundError):
            portable.verify(self.root, ORIGINAL)
        self.assertIs(workflow.Path, Path)

    def test_tampered_local_bytes_are_rejected(self):
        with (self.root / 'deliverables/compliance-brief.md').open('ab') as handle:
            handle.write(b'\nUnapproved modification\n')
        with self.assertRaises(ValueError):
            portable.verify(self.root, ORIGINAL)

    def test_mapping_rejects_escape_symlink_and_writes(self):
        with portable.relocated_paths(self.root, ORIGINAL) as logical:
            for value in ('../outside', str(ORIGINAL / '../outside'), '/unrelated/file'):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    logical(value).read_bytes()
            (self.root / 'escape').symlink_to(Path(self.temp.name))
            with self.assertRaises(ValueError):
                logical('escape/file').read_bytes()
            with self.assertRaises(ValueError):
                logical('new-file').open('w')

    def test_invalid_mapping_and_package_are_rejected(self):
        for original, package in ((Path('relative'), 'deliverables'), (ORIGINAL, '../deliverables')):
            with self.subTest(original=original, package=package), self.assertRaises(ValueError):
                portable.verify(self.root, original, package)


if __name__ == '__main__':
    unittest.main()
