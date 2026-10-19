"""Offline tests; also runnable from the exported public view without original HTML."""
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
import public_evidence as public
import portable
from capture import digest

ROOT = Path(__file__).resolve().parents[2]


class PublicEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='project-b-public-tests-')
        cls.base = Path(cls.temp.name) / 'public base'
        if (ROOT / public.MANIFEST).exists():
            shutil.copytree(ROOT, cls.base, ignore=shutil.ignore_patterns('__pycache__', '.git'))
        else:
            with patch.object(socket, 'create_connection', side_effect=AssertionError('Network forbidden')):
                public.export(ROOT, cls.base)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.temp_case = tempfile.TemporaryDirectory(prefix='project-b-public-case-')
        self.addCleanup(self.temp_case.cleanup)
        self.root = Path(self.temp_case.name) / 'relocated checkout with spaces'
        shutil.copytree(self.base, self.root)
        self.manifest = json.loads((self.root / public.MANIFEST).read_bytes())

    def save_manifest(self):
        (self.root / public.MANIFEST).write_text(json.dumps(self.manifest, indent=2) + '\n')

    def rebind_test_file(self, path):
        name = str(path.relative_to(self.root)); raw = path.read_bytes()
        for item in self.manifest['files']:
            if item['path'] == name:
                item.update(sha256=digest(raw), size=len(raw))
        for entry in self.manifest['omitted_originals']:
            if entry['extract_path'] == name:
                entry['extract_sha256'] = digest(raw)
        self.save_manifest()

    def test_offline_relocation_preserves_every_retained_byte(self):
        before = {str(p.relative_to(self.root)): digest(p.read_bytes()) for p in self.root.rglob('*') if p.is_file()}
        with patch.object(socket, 'create_connection', side_effect=AssertionError('Network forbidden')):
            result = public.verify(self.root)
        self.assertEqual(result['retained_evidence_validation'], 'passed')
        self.assertEqual(result['original_html_byte_verification'], 'unavailable')
        self.assertEqual(result['omitted_original_count'], 12)
        self.assertEqual(result['publication_status'], 'blocked')
        self.assertFalse(result['retrieval_performed'])
        self.assertTrue(result['historical_configuration_bytes_unavailable'])
        self.assertEqual(before, {str(p.relative_to(self.root)): digest(p.read_bytes()) for p in self.root.rglob('*') if p.is_file()})

    def test_cli_runs_inside_relocated_public_checkout(self):
        result = subprocess.run([sys.executable, '-B', 'regulatory-change-impact-brief/scripts/public_evidence.py',
                                 '--validate', '.'], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['original_html_byte_verification'], 'unavailable')

    def test_all_twelve_originals_absent_and_retained_files_have_no_key_shapes(self):
        for entry in self.manifest['omitted_originals']:
            self.assertFalse((self.root / entry['original_path']).exists())
        for item in self.manifest['files']:
            self.assertIsNone(public.KEY_SHAPE.search((self.root / item['path']).read_bytes()))

    def test_missing_extract_is_rejected(self):
        (self.root / self.manifest['omitted_originals'][0]['extract_path']).unlink()
        with self.assertRaises(ValueError): public.verify(self.root)

    def test_changed_business_record_with_rehashed_manifest_is_rejected(self):
        path = self.root / self.manifest['omitted_originals'][0]['extract_path']
        data = json.loads(path.read_bytes()); data['tables'][0]['records'][0]['values']['owner'] = 'UNVERIFIED SUBSTITUTE'
        path.write_text(json.dumps(data)); self.rebind_test_file(path)
        with self.assertRaisesRegex(ValueError, 'differs|records'): public.verify(self.root)

    def test_invalid_provenance_with_rehashed_manifest_is_rejected(self):
        path = self.root / self.manifest['omitted_originals'][0]['extract_path']
        data = json.loads(path.read_bytes()); data['retrieved_at'] = '2026-01-01T00:00:00Z'
        path.write_text(json.dumps(data)); self.rebind_test_file(path)
        with self.assertRaisesRegex(ValueError, 'provenance'): public.verify(self.root)

    def test_original_hash_and_unapproved_substitution_are_rejected(self):
        self.manifest['omitted_originals'][0]['original_sha256'] = 'sha256:' + '0' * 64
        self.save_manifest()
        with self.assertRaises(ValueError): public.verify(self.root)
        self.manifest['omitted_originals'][0]['original_path'] = 'deliverables/sources/unapproved.response'
        self.save_manifest()
        with self.assertRaises(ValueError): public.verify(self.root)

    def test_invalid_row_locator_is_rejected_even_after_rehash(self):
        path = self.root / self.manifest['omitted_originals'][0]['extract_path']
        data = json.loads(path.read_bytes()); data['tables'][0]['records'][0]['row_number'] = 999
        path.write_text(json.dumps(data)); self.rebind_test_file(path)
        with self.assertRaises(ValueError): public.verify(self.root)

    def test_draft_tampering_is_rejected(self):
        path = self.root / 'deliverables/compliance-brief.md'
        path.write_bytes(path.read_bytes() + b'\nUNAPPROVED\n'); self.rebind_test_file(path)
        with self.assertRaises(ValueError): public.verify(self.root)

    def test_trusted_manifest_digest_rejects_rebaselining(self):
        expected = digest((self.root / public.MANIFEST).read_bytes())
        self.manifest['untrusted_note'] = 'changed'; self.save_manifest()
        with self.assertRaisesRegex(ValueError, 'Trusted manifest'): public.verify(self.root, expected)

    def test_path_escape_and_unexpected_files_are_rejected(self):
        self.manifest['omitted_originals'][0]['extract_path'] = '../outside.json'; self.save_manifest()
        with self.assertRaises(ValueError): public.verify(self.root)
        (self.root / 'unexpected.tmp').write_text('unexpected')
        with self.assertRaises(ValueError): public.verify(self.root)

    def test_full_strict_mode_still_rejects_public_view(self):
        with self.assertRaises(FileNotFoundError):
            portable.verify(self.root, Path(self.manifest['original_root']))

    def git(self, *arguments):
        result = subprocess.run(['git', '-c', 'core.hooksPath=/dev/null', *map(str, arguments)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def assert_public_passes(self):
        self.assertEqual(public.verify(self.root)['retained_evidence_validation'], 'passed')

    def test_normal_git_checkout_is_not_assessment_evidence(self):
        self.git('init', '--quiet', self.root)
        self.assertEqual(self.git('-C', self.root, 'rev-parse', '--is-inside-work-tree'), 'true')
        (self.root / '.git' / 'unrelated-admin-state').write_text('administrative state')
        self.assert_public_passes()
        (self.root / 'unexpected.txt').write_text('ordinary unexpected file')
        with self.assertRaisesRegex(ValueError, 'inventory'): public.verify(self.root)

    def test_git_pointer_checkout_without_commits(self):
        admin = Path(self.temp_case.name) / 'separate admin'
        self.git('init', '--quiet', '--separate-git-dir', admin, self.root)
        self.assertTrue((self.root / '.git').is_file())
        self.assertEqual(self.git('-C', self.root, 'rev-parse', '--is-inside-work-tree'), 'true')
        self.assert_public_passes()
        (self.root / 'deliverables/impact-register.csv').unlink()
        with self.assertRaises(ValueError): public.verify(self.root)

    def test_linked_worktree_with_existing_history_and_no_new_commit(self):
        # Clone only existing local history. No network, staging or new commits.
        source = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', '--show-toplevel'],
                                capture_output=True, text=True)
        if source.returncode:
            self.skipTest('No existing local history; separate-Git-dir pointer test still covers file form')
        clone = Path(self.temp_case.name) / 'history clone'
        linked = Path(self.temp_case.name) / 'linked worktree'
        self.git('clone', '--quiet', '--no-local', '--single-branch', '--no-tags', source.stdout.strip(), clone)
        self.git('-C', clone, 'worktree', 'add', '--quiet', '--detach', linked, 'HEAD')
        shutil.copytree(self.base, linked, dirs_exist_ok=True)
        self.assertTrue((linked / '.git').is_file())
        self.assertEqual(public.verify(linked)['retained_evidence_validation'], 'passed')

    def test_git_metadata_cannot_be_manifest_evidence_or_a_symlink(self):
        (self.root / '.git').mkdir()
        admin = self.root / '.git' / 'config'; admin.write_text('admin')
        self.manifest['files'].append({'path':'.git/config', 'sha256':digest(admin.read_bytes()), 'size':5})
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, 'Git metadata'): public.verify(self.root)
        self.manifest['files'].pop(); self.save_manifest()
        admin.unlink(); (self.root / '.git').rmdir()
        (self.root / '.git').symlink_to(Path(self.temp_case.name), target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'Symlink'): public.verify(self.root)

    def test_git_checkout_still_rejects_changed_hashes_and_assessment_symlinks(self):
        self.git('init', '--quiet', self.root)
        brief = self.root / 'deliverables/compliance-brief.md'
        raw = brief.read_bytes(); brief.write_bytes(raw + b'\nchanged\n')
        with self.assertRaisesRegex(ValueError, 'hash/size'): public.verify(self.root)
        brief.unlink(); brief.symlink_to(self.base / 'deliverables/compliance-brief.md')
        with self.assertRaisesRegex(ValueError, 'Symlink'): public.verify(self.root)

    def test_only_root_git_metadata_is_exempt_and_pointer_must_be_valid(self):
        nested = self.root / 'deliverables/.git'; nested.mkdir()
        with self.assertRaisesRegex(ValueError, 'Nested Git'): public.verify(self.root)
        nested.rmdir(); (self.root / '.git').write_text('ordinary file, not a Git pointer')
        with self.assertRaisesRegex(ValueError, 'worktree pointer'): public.verify(self.root)

    def test_full_local_package_remains_strict_and_export_refuses_overwrite(self):
        if (ROOT / public.MANIFEST).exists():
            self.skipTest('Original raw HTML intentionally unavailable in public assessment view')
        original = Path(self.manifest['original_root'])
        self.assertEqual(portable.verify(ROOT, original)['state']['draft_validation_status'], 'passed')
        with self.assertRaises(ValueError): public.export(ROOT, self.root)


if __name__ == '__main__':
    unittest.main()
