import copy
import csv
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import publication as p


class PublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = p.ROOT / 'deliverables/snapshots/06-actions-and-approvals.json'
        cls.data = p.inputs(cls.source)
        cls.blobs = p.render(cls.data)

    def bundle(self, directory):
        destination = Path(directory)
        for name, content in self.blobs.items():
            (destination / name).write_bytes(content)
        snapshot = p.make_snapshot(self.data, self.blobs, destination)
        (destination / p.SNAPSHOT).parent.mkdir(parents=True)
        (destination / p.SNAPSHOT).write_text(json.dumps(snapshot), encoding='utf-8')
        return destination, snapshot

    def test_exact_csv_contract_all_findings_and_original_states(self):
        reader = csv.DictReader(io.StringIO(self.blobs[p.FILES[0]].decode(), newline=''))
        self.assertEqual(reader.fieldnames, p.COLUMNS)
        self.assertEqual(len(reader.fieldnames), 10)
        rows = list(reader)
        self.assertEqual(len(rows), 64)
        self.assertEqual(len({r['impact_id'] for r in rows}), 64)
        for row, finding in zip(rows, self.data[1]['state']['impacts']):
            self.assertEqual(row['state'], finding['state'])
            self.assertIn(finding['reason'], row['reason'])
            self.assertEqual(row['evidence_ids'].split(';'), finding['evidence_ids'])
            self.assertEqual(row['approval_status'], 'pending')
        self.assertEqual(sum(r['state'] == 'conflicting' for r in rows), 2)

    def test_dates_are_never_selected_from_multiple_proposals(self):
        for row, finding in zip(p.register_rows(self.data), self.data[1]['state']['impacts']):
            linked = p.local_actions(finding, self.data[0])
            expected = linked[0]['proposed_due_date'] if len(linked) == 1 else None
            self.assertEqual(row['proposed_due_date'], expected or '')
            if not linked:
                self.assertIn('no individual due date', row['reason'])
        self.assertNotIn('2026-12-02', [r['proposed_due_date'] for r in p.register_rows(self.data)])

    def test_only_eight_dated_actions_and_one_global_event(self):
        events = p.parse_calendar(self.blobs[p.FILES[2]])
        dated = [a for a in self.data[0]['state']['proposed_actions'] if a['proposed_due_date']]
        self.assertEqual(len(events), 8)
        self.assertEqual(len(self.data[0]['state']['proposed_actions']) - len(events), 9)
        for event, action in zip(events, dated):
            self.assertEqual(event['UID'], p.uid(action['id']))
            self.assertEqual(event['DTSTART;VALUE=DATE'], action['proposed_due_date'].replace('-', ''))
            self.assertEqual(event['STATUS'], 'TENTATIVE')
            description = p.text_unescape(event['DESCRIPTION'])
            self.assertIn(action['source_version'], description)
            self.assertIn(action['owner'], description)
            self.assertIn('approval_status=pending', description)
            self.assertIn(self.data[0]['run_id'], description)
        self.assertEqual(sum(e['UID'] == p.uid('ACT-008') for e in events), 1)

    def test_empty_calendar_is_valid_when_no_proposals_dated(self):
        data = copy.deepcopy(self.data)
        for action in data[0]['state']['proposed_actions']:
            action['proposed_due_date'] = None
        self.assertEqual(p.parse_calendar(p.render_calendar(data)), [])

    def test_octet_folding_escaping_and_date_conventions(self):
        text = 'é' * 100 + ', semi; newline\nbackslash\\end'
        folded = p.fold('DESCRIPTION:' + p.text_escape(text))
        self.assertTrue(all(len(line.encode()) <= 75 for line in folded.split('\r\n')))
        unfolded = folded.replace('\r\n ', '').partition(':')[2]
        self.assertEqual(p.text_unescape(unfolded), text)
        events = p.parse_calendar(self.blobs[p.FILES[2]])
        expected = p.datetime.fromisoformat(self.data[0]['created_at'].replace('Z', '+00:00')).strftime('%Y%m%dT%H%M%SZ')
        self.assertTrue(all(e['DTSTAMP'] == expected for e in events))
        self.assertNotIn('DTEND', self.blobs[p.FILES[2]].decode())

    def test_invalid_calendars_rejected(self):
        raw = self.blobs[p.FILES[2]]
        for changed in (raw.replace(b'\r\n', b'\n'), raw.replace(b'STATUS:TENTATIVE', b'STATUS:CONFIRMED'),
                        raw.replace(b'DTSTART;VALUE=DATE:20260904', b'DTSTART;VALUE=DATE:20260230')):
            with self.assertRaises(ValueError):
                p.parse_calendar(changed)

    def test_draft_output_is_deterministic_and_uid_is_action_stable(self):
        self.assertEqual(self.blobs, p.render(self.data))
        data = copy.deepcopy(self.data)
        data[0]['state']['proposed_actions'][0]['proposed_due_date'] = '2026-09-05'
        self.assertEqual(p.parse_calendar(p.render_calendar(data))[0]['UID'], p.parse_calendar(self.blobs[p.FILES[2]])[0]['UID'])
        self.assertEqual(p.make_snapshot(self.data, self.blobs, Path('/tmp/a'))['state']['artifacts'][1]['sha256'],
                         p.make_snapshot(self.data, self.blobs, Path('/tmp/b'))['state']['artifacts'][1]['sha256'])

    def test_all_requests_bind_actual_final_bytes_without_circular_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            destination, snapshot = self.bundle(directory)
            p.verify_bundle(destination, self.data)
            p.validate(snapshot)
            artifacts = snapshot['state']['artifacts']
            self.assertEqual(len(snapshot['state']['review_request_bindings']), 43)
            for binding, request in zip(snapshot['state']['review_request_bindings'], self.data[0]['state']['approval_requirements']):
                self.assertEqual(binding['request_id'], request['id'])
                self.assertEqual(binding['artifacts'], artifacts)
                self.assertEqual(binding['subject'], request['subject'])
                self.assertEqual(binding['source_versions'], request['source_versions'])
                self.assertEqual(binding['status'], 'pending')
                self.assertEqual(binding['delivery_status'], 'not-sent')
                self.assertIsNone(binding['feedback'])
                for artifact in binding['artifacts']:
                    self.assertEqual(artifact['sha256'], p.digest(Path(artifact['path']).read_bytes()))
            brief_hash = next(a['sha256'] for a in artifacts if a['path'].endswith('.md'))
            self.assertNotIn(brief_hash.encode(), self.blobs[p.FILES[1]])
            self.assertEqual(snapshot['predecessor']['sha256'], p.digest(self.source.read_bytes()))
            self.assertEqual(snapshot['run_id'], self.data[0]['run_id'])
            self.assertEqual(snapshot['unresolved'], self.data[0]['unresolved'])
            self.assertEqual(snapshot['state']['publication_status'], 'blocked')

    def test_tampering_any_draft_fails_without_repair(self):
        for name in p.FILES:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                destination, _ = self.bundle(directory)
                path = destination / name
                changed = path.read_bytes() + b'\n'
                path.write_bytes(changed)
                with self.assertRaises(ValueError):
                    p.verify_bundle(destination, self.data)
                self.assertEqual(path.read_bytes(), changed)

    def test_binding_or_snapshot_tampering_rejected(self):
        for field in ('hash', 'request', 'predecessor', 'approval'):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                destination, snapshot = self.bundle(directory)
                binding = snapshot['state']['review_request_bindings'][0]
                if field == 'hash':
                    binding['artifacts'][0]['sha256'] = 'sha256:' + '0' * 64
                elif field == 'request':
                    snapshot['state']['review_request_bindings'].pop()
                elif field == 'predecessor':
                    snapshot['predecessor']['sha256'] = 'sha256:' + '0' * 64
                else:
                    binding['status'] = 'approved'
                (destination / p.SNAPSHOT).write_text(json.dumps(snapshot))
                with self.assertRaises(ValueError):
                    p.verify_bundle(destination, self.data)

    def test_rehashing_a_changed_draft_does_not_silently_rebind_it(self):
        with tempfile.TemporaryDirectory() as directory:
            destination, snapshot = self.bundle(directory)
            path = destination / 'compliance-brief.md'
            path.write_bytes(path.read_bytes() + b'\nUnverified additional conclusion.\n')
            changed_hash = p.digest(path.read_bytes())
            for artifact in snapshot['state']['artifacts']:
                if artifact['path'] == str(path):
                    artifact['sha256'] = changed_hash
            for binding in snapshot['state']['review_request_bindings']:
                for artifact in binding['artifacts']:
                    if artifact['path'] == str(path):
                        artifact['sha256'] = changed_hash
            (destination / p.SNAPSHOT).write_text(json.dumps(snapshot))
            with self.assertRaises(ValueError):
                p.verify_bundle(destination, self.data)

    def test_evidence_reference_and_csv_contract_regressions(self):
        for replacement in (b'not_a_field', b'unknown-evidence'):
            changed = dict(self.blobs)
            if replacement == b'not_a_field':
                changed[p.FILES[0]] = changed[p.FILES[0]].replace(b'impact_id,', b'not_a_field,', 1)
            else:
                changed[p.FILES[0]] = changed[p.FILES[0]].replace(b'row-systems-AI-001', replacement, 1)
            with self.assertRaises(ValueError):
                p.inspect_bytes(changed, self.data)

    def test_cli_generation_validate_only_and_overwrite_refusal(self):
        with tempfile.TemporaryDirectory() as directory:
            command = [sys.executable, str(Path(p.__file__)), '--destination', directory]
            completed = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            before = {str(f): f.read_bytes() for f in Path(directory).rglob('*') if f.is_file()}
            self.assertEqual(len(before), 4)
            check = subprocess.run(command + ['--validate-only'], capture_output=True, text=True)
            self.assertEqual(check.returncode, 0, check.stderr)
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertEqual(before, {str(f): f.read_bytes() for f in Path(directory).rglob('*') if f.is_file()})

    def test_modified_stage06_is_not_accepted_as_review_basis(self):
        changed = copy.deepcopy(self.data[0])
        changed['state']['proposed_actions'][0]['approval_status'] = 'approved'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '06.json'
            path.write_text(json.dumps(changed))
            with self.assertRaises(ValueError):
                p.inputs(path)
