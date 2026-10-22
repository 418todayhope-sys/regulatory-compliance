"""Controlled fixture transports only: no live network traffic in workflow tests."""
import copy
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from urllib.error import URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import workflow as w


class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture_responses = {}
        selected = json.loads((w.ROOT / 'deliverables/snapshots/02-source-capture-attempt-004.json').read_bytes())
        original_root = Path(selected['predecessor']['path']).parents[2]
        for source in selected['state']['sources']:
            reference = Path(source['local_reference'])
            fixture_path = reference.relative_to(original_root) if reference.is_absolute() else reference
            cls.fixture_responses[source['requested_url']] = {
                'body': (w.ROOT / fixture_path).read_bytes(), 'status': source['http_status'],
                'url': source['final_url'], 'headers': {'Content-Type': source['content_type']}}

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.calls = []
        paths = ['Project_B_Learner_Assignment_Codex.md', 'README.md', 'snapshot.schema.json',
                 'interviews/project-b-regulatory-compliance-20261018-1952.md',
                 'references/manual/policy-manual-reference.md', str(w.CONFIG), str(w.operating.PROFILE)]
        for name in paths:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(w.ROOT / name, target)

    def transport(self, url, timeout):
        self.calls.append(url)
        self.assertIn(url, self.fixture_responses, 'Unexpected source route')
        return copy.deepcopy(self.fixture_responses[url])

    def run_workflow(self, **options):
        with redirect_stdout(io.StringIO()):
            return w.execute('Controlled fixture run for recovery verification', root=self.root,
                             transport=options.pop('transport', self.transport), **options)

    def run_dir(self, result):
        return self.root / 'deliverables/runs' / result['run_id']

    def assert_chain(self, result):
        directory = self.run_dir(result)
        with w.workspace(self.root):
            final = w.verify_run(directory, self.root)
        self.assertEqual(final['run_id'], result['run_id'])
        self.assertEqual(final['state']['draft_validation_status'], 'passed')
        self.assertEqual(final['state']['publication_status'], 'blocked')
        parent = json.loads((directory / 'snapshots/03-authority-and-timing.json').read_bytes())['predecessor']['path']
        self.assertEqual(parent, f"deliverables/runs/{result['run_id']}/snapshots/02-source-capture.json")
        self.assertNotIn('capture-004', parent)
        for artifact in final['state']['artifacts']:
            self.assertFalse(Path(artifact['path']).is_absolute())
            self.assertEqual(w.digest((self.root / artifact['path']).read_bytes()), artifact['sha256'])
        return final

    def test_initial_run_complete_fresh_capture_and_relative_hash_chain(self):
        result = self.run_workflow()
        self.assertEqual(result['outcome'], 'completed')
        self.assertEqual(result['completed_stages'], list(w.NAMES))
        self.assertEqual(len(self.calls), 13)
        self.assertEqual(len(set(self.calls)), 13)
        self.assert_chain(result)
        run = self.run_dir(result)
        scope = json.loads((run / 'snapshots/01-scope.json').read_bytes())
        self.assertIsNone(scope['state']['supersedes_run_id'])
        self.assertEqual(scope['state']['path_convention'], 'repository-relative')
        for source in scope['state']['evidence_records']:
            self.assertTrue(source['path'].startswith(f"deliverables/runs/{result['run_id']}/inputs/"))
        self.assertNotIn(str(self.root), '\n'.join(p.read_text(errors='replace') for p in run.rglob('*.json')))

    def test_rerun_preserves_all_previous_bytes_and_approval_versions(self):
        first = self.run_workflow()
        directory = self.run_dir(first)
        extra = directory / 'approvals/owner-response.json'
        extra.parent.mkdir()
        extra.write_text('{"status":"pending","note":"fixture only; not authenticated approval"}')
        before = {str(p.relative_to(directory)): p.read_bytes() for p in directory.rglob('*') if p.is_file()}
        self.calls.clear()
        second = self.run_workflow()
        self.assertNotEqual(first['run_id'], second['run_id'])
        self.assertEqual(len(self.calls), 13)
        self.assertEqual(before, {str(p.relative_to(directory)): p.read_bytes() for p in directory.rglob('*') if p.is_file()})
        history = self.root / 'deliverables/history' / first['run_id']
        for name, raw in before.items():
            self.assertEqual((history / name).read_bytes(), raw)
        with w.workspace(self.root):
            w.validate_archive(Path('deliverables/history') / first['run_id'] / 'preservation.json')
        second_scope = json.loads((self.run_dir(second) / 'snapshots/01-scope.json').read_bytes())
        self.assertEqual(second_scope['state']['supersedes_run_id'], first['run_id'])
        self.assertTrue(second_scope['state']['change_retry_reason'])
        self.assert_chain(second)
        self.assertTrue(all(b['status'] == 'pending' for b in self.assert_chain(second)['state']['review_request_bindings']))
        ids1 = [json.loads((directory / 'snapshots' / name).read_bytes())['snapshot_id'] for name in w.NAMES]
        ids2 = [json.loads((self.run_dir(second) / 'snapshots' / name).read_bytes())['snapshot_id'] for name in w.NAMES]
        self.assertFalse(set(ids1) & set(ids2))

    def test_failed_capture_never_uses_old_evidence_and_retry_retrieves_again(self):
        first = self.run_workflow()
        original = (self.run_dir(first) / 'compliance-brief.md').read_bytes()
        failures = []
        def unavailable(url, timeout):
            failures.append(url)
            raise URLError('controlled offline fixture')
        with self.assertRaises(ValueError):
            self.run_workflow(transport=unavailable)
        result_files = list((self.root / 'deliverables/runs').glob('*/result.json'))
        failed = next(json.loads(p.read_bytes()) for p in result_files if json.loads(p.read_bytes())['outcome'] == 'failed')
        self.assertEqual(failed['failed_stage'], '04-evidence-reconciliation.json')
        self.assertEqual(len(failures), 16)  # ten originals, three legal fallbacks, three tab exports
        failed_dir = self.run_dir(failed)
        captured = json.loads((failed_dir / 'snapshots/02-source-capture.json').read_bytes())
        self.assertTrue(all(s['local_reference'] is None and s['content_hash'] is None for s in captured['state']['sources']))
        self.assertFalse((failed_dir / 'compliance-brief.md').exists())
        self.assertEqual((self.run_dir(first) / 'compliance-brief.md').read_bytes(), original)
        self.assertIn('--retry-run ' + failed['run_id'], failed['recovery_action'])
        self.calls.clear()
        retry = self.run_workflow(retry_run=failed['run_id'])
        self.assertEqual(len(self.calls), 13)
        scope = json.loads((self.run_dir(retry) / 'snapshots/01-scope.json').read_bytes())
        self.assertEqual(scope['state']['retry_of_run_id'], failed['run_id'])
        self.assertEqual(scope['state']['supersedes_run_id'], failed['run_id'])
        self.assertEqual(scope['state']['previous_completed_run_id'], first['run_id'])
        self.assertEqual(len(retry['history_preservation']), 2)
        self.assert_chain(retry)

    def test_relocation_and_frozen_inputs_survive_new_original_versions(self):
        first = self.run_workflow()
        # A later edit does not invalidate the already frozen source basis.
        (self.root / 'README.md').write_text('Later local README version\n')
        self.assert_chain(first)
        with tempfile.TemporaryDirectory() as directory:
            relocated = Path(directory) / 'other-checkout'
            shutil.copytree(self.root, relocated)
            bundle = Path('deliverables/runs') / first['run_id']
            with w.workspace(relocated):
                verified = w.verify_run(bundle, relocated)
                self.assertEqual(verified['run_id'], first['run_id'])

    def test_missing_and_corrupt_prior_evidence_is_preserved_and_reported(self):
        first = self.run_workflow()
        directory = self.run_dir(first)
        (directory / 'impact-register.csv').unlink()  # fixture damage only
        (directory / 'compliance-brief.md').write_bytes(b'CORRUPTED FIXTURE')
        second = self.run_workflow()
        manifest = json.loads((self.root / second['history_preservation'][0]['path']).read_bytes())
        self.assertTrue(any(i['issue'] == 'missing draft' for i in manifest['pre_existing_issues']))
        self.assertTrue(any(i['issue'] == 'pre-existing hash mismatch' for i in manifest['pre_existing_issues']))
        history = self.root / 'deliverables/history' / first['run_id']
        self.assertEqual((history / 'compliance-brief.md').read_bytes(), b'CORRUPTED FIXTURE')
        self.assertFalse((history / 'impact-register.csv').exists())
        self.assert_chain(second)

    def test_interrupted_run_can_be_retried_without_resuming_partial_files(self):
        interrupted = 'run-interrupted-fixture'
        directory = self.root / 'deliverables/runs' / interrupted
        directory.mkdir(parents=True)
        (directory / 'started.json').write_text(json.dumps({'run_id': interrupted}))
        (directory / 'partial.response').write_bytes(b'partial fixture')
        (directory / 'result.json').write_bytes(b'corrupted fixture outcome')
        retry = self.run_workflow(retry_run=interrupted)
        self.assertNotEqual(retry['run_id'], interrupted)
        self.assertEqual((directory / 'partial.response').read_bytes(), b'partial fixture')
        self.assertEqual((self.root / 'deliverables/history' / interrupted / 'partial.response').read_bytes(), b'partial fixture')
        manifest = json.loads((self.root / retry['history_preservation'][0]['path']).read_bytes())
        self.assertTrue(any(i['issue'] == 'unreadable technical outcome/start metadata' for i in manifest['pre_existing_issues']))
        self.assertEqual(len(self.calls), 13)
        self.assert_chain(retry)

    def test_legacy_history_copies_actual_bytes_without_rewriting_bindings(self):
        directory = self.root / 'deliverables'
        (directory / 'snapshots').mkdir(parents=True)
        old = {'run_id': 'run-legacy-fixture', 'invalid': 'controlled incomplete legacy fixture'}
        (directory / 'snapshots/01-scope.json').write_text(json.dumps(old))
        (directory / 'compliance-brief.md').write_bytes(b'old draft with original binding')
        first = self.run_workflow()
        preserved = self.root / 'deliverables/history/run-legacy-fixture'
        self.assertEqual((preserved / 'compliance-brief.md').read_bytes(), b'old draft with original binding')
        self.assertEqual((directory / 'compliance-brief.md').read_bytes(), b'old draft with original binding')
        self.assertTrue(json.loads((preserved / 'preservation.json').read_bytes())['pre_existing_issues'])
        self.assert_chain(first)

    def test_changed_calendar_bytes_recompute_new_drafts_and_keep_old_versions(self):
        first = self.run_workflow()
        original = (self.run_dir(first) / 'action-calendar.ics').read_bytes()
        def changed(url, timeout):
            response = self.transport(url, timeout)
            if '1xtXl_P7Yb9LaECZjjgtlyI-idoAJTAhH-1gQ4vQaCGA' in url:
                response['body'] = response['body'].replace(b'2026-09-04', b'2026-09-05').replace(b'calendar-2026-08-26', b'calendar-2026-08-27')
            return response
        second = self.run_workflow(transport=changed)
        six = json.loads((self.run_dir(second) / 'snapshots/06-actions-and-approvals.json').read_bytes())
        action = next(a for a in six['state']['proposed_actions'] if a['id'] == 'ACT-001')
        self.assertEqual(action['proposed_due_date'], '2026-09-05')
        self.assertEqual(action['source_version'], 'calendar-2026-08-27')
        self.assertEqual(action['approval_status'], 'pending')
        self.assertIn(b'DTSTART;VALUE=DATE:20260905', (self.run_dir(second) / 'action-calendar.ics').read_bytes())
        self.assertEqual((self.run_dir(first) / 'action-calendar.ics').read_bytes(), original)
        self.assert_chain(second)

    def test_archive_occurrences_and_corruption_never_overwrite_history(self):
        directory = self.root / 'deliverables'
        directory.mkdir()
        draft = directory / 'compliance-brief.md'
        draft.write_bytes(b'original fixture')
        previous = {'directory': Path('deliverables'), 'run_id': 'run-archive-fixture', 'legacy': True}
        with w.workspace(self.root):
            first = w.archive(previous, 'run-first-fixture')
            manifest_bytes = Path(first['path']).read_bytes()
            draft.write_bytes(b'later observed fixture')
            second = w.archive(previous, 'run-second-fixture')
            self.assertIn('/occurrences/run-second-fixture/', second['path'])
            self.assertEqual(Path(first['path']).read_bytes(), manifest_bytes)
            archived = Path('deliverables/history/run-archive-fixture/compliance-brief.md')
            self.assertEqual(archived.read_bytes(), b'original fixture')
            archived.write_bytes(b'corrupted fixture archive')
            with self.assertRaises(ValueError):
                w.archive(previous, 'run-third-fixture')
            self.assertEqual(archived.read_bytes(), b'corrupted fixture archive')
        self.assertEqual(self.calls, [])

    def test_legacy_external_manual_and_interview_input_bytes_are_archived(self):
        directory = self.root / 'deliverables'
        (directory / 'snapshots').mkdir(parents=True)
        manual = self.root / 'references/manual/policy-manual-reference.md'
        raw = manual.read_bytes()
        snapshot = {'run_id': 'run-legacy-input-fixture', 'state': {'manual_reference':
                    {'path': 'references/manual/policy-manual-reference.md', 'sha256': w.digest(raw)}}}
        (directory / 'snapshots/02-source-capture.json').write_text(json.dumps(snapshot))
        with w.workspace(self.root):
            preserved = w.archive({'directory': Path('deliverables'), 'legacy': True,
                                   'run_id': 'run-legacy-input-fixture'}, 'run-preserving-inputs')
            w.validate_archive(Path(preserved['path']))
        target = directory / 'history/run-legacy-input-fixture/supplemental-inputs/references/manual/policy-manual-reference.md'
        self.assertEqual(target.read_bytes(), raw)
        manual.write_bytes(b'later fixture source version')
        self.assertEqual(target.read_bytes(), raw)

    def test_concurrent_operator_is_rejected_before_capture(self):
        with w.workspace(self.root), w.locked():
            with self.assertRaises(RuntimeError):
                self.run_workflow()
        self.assertEqual(self.calls, [])

    def test_reason_and_unknown_retry_are_rejected_honestly(self):
        with self.assertRaises(ValueError):
            w.execute('', root=self.root, transport=self.transport)
        with self.assertRaises(FileNotFoundError):
            self.run_workflow(retry_run='run-never-existed')
        self.assertEqual(self.calls, [])
        failed = json.loads(next((self.root / 'deliverables/runs').glob('*/result.json')).read_bytes())
        self.assertEqual(failed['outcome'], 'failed')
        self.assertEqual(failed['failed_stage'], 'preservation')

    def test_damaged_retry_start_is_preserved_without_inventing_identity(self):
        for index, raw in enumerate((b'{broken json', b'[]', b'{}', b'{"run_id":"run-other"}')):
            with self.subTest(raw=raw):
                retry_id = f'run-damaged-start-{index}'
                directory = self.root / 'deliverables/runs' / retry_id
                directory.mkdir(parents=True)
                (directory / 'started.json').write_bytes(raw)
                (directory / 'partial.response').write_bytes(b'original partial evidence')
                with self.assertRaisesRegex(ValueError, 'identity unverifiable|identity is unverifiable'):
                    self.run_workflow(retry_run=retry_id)
                self.assertEqual((directory / 'started.json').read_bytes(), raw)
                history = self.root / 'deliverables/history' / retry_id
                self.assertEqual((history / 'started.json').read_bytes(), raw)
                self.assertEqual((history / 'partial.response').read_bytes(), b'original partial evidence')
                failures = [json.loads(p.read_bytes()) for p in (self.root / 'deliverables/runs').glob('*/result.json')]
                failed = next(r for r in failures if r.get('retry_of_run_id') == retry_id)
                self.assertEqual(failed['outcome'], 'failed')
                self.assertEqual(failed['failed_stage'], 'preservation')
                self.assertEqual(len(failed['history_preservation']), 1)
                self.assertFalse((self.run_dir(failed) / 'snapshots/01-scope.json').exists())
        self.assertEqual(self.calls, [])

    def test_completed_discovery_rejects_invalid_timestamps_and_orders_actual_instants(self):
        timestamps = [123, None, [], {}, True, '', 'not-a-date',
                      '2026-02-30T00:00:00Z', '2026-10-19T00:00:00',
                      '2026-10-19T10:00:00+02:00', '2026-10-19T08:30:00Z']
        originals = {}
        for index, timestamp in enumerate(timestamps):
            run_id = f'run-discovery-{index}'
            path = self.root / 'deliverables/runs' / run_id / 'result.json'
            path.parent.mkdir(parents=True)
            raw = json.dumps({'outcome': 'completed', 'run_id': run_id, 'finished_at': timestamp}).encode()
            path.write_bytes(raw)
            originals[path] = raw
        with w.workspace(self.root):
            previous = w.discover_previous()
        self.assertEqual(previous['run_id'], 'run-discovery-10')
        for path, raw in originals.items():
            self.assertEqual(path.read_bytes(), raw)
        self.assertEqual(self.calls, [])
