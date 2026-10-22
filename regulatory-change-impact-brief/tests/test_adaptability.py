"""Explicit controlled changes: no live captures or edits to completed repository evidence."""
import copy
import csv
import hashlib
from html import escape
import io
import json
from pathlib import Path
import re
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import impact
import operating
import registers
import workflow as w
import test_workflow as fixtures


class OperatingReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.four = json.loads((w.ROOT / 'deliverables/snapshots/04-evidence-reconciliation.json').read_bytes())
        cls.three = json.loads((w.ROOT / 'deliverables/snapshots/03-authority-and-timing.json').read_bytes())
        cls.baseline = impact.analyze(cls.four, cls.three)

    def analyze(self, change):
        four = copy.deepcopy(self.four)
        change(four)
        return impact.analyze(four, self.three)

    def test_variable_evidence_count_including_empty_and_unique_ids(self):
        rows = [r['values'] for r in self.four['state']['incident_evidence']]
        headers = list(rows[0])
        extra = dict(rows[0], record_id='REC-011')
        data = [headers] + [[r.get(h, '') for h in headers] for r in rows + [extra]]
        self.assertTrue(registers.table('EVIDENCE', data, '0', 'Incident Evidence Register')['valid'])
        self.assertTrue(registers.table('EVIDENCE', [headers], '0', 'Incident Evidence Register')['valid'])
        data[-1][headers.index('record_id')] = rows[0]['record_id']
        self.assertFalse(registers.table('EVIDENCE', data, '0', 'Incident Evidence Register')['valid'])

    def test_changed_system_use_withholds_only_that_systems_interpretations(self):
        def change(four):
            four['state']['system_facts'][1]['values']['use_case'] = 'Publishes public-interest news text'
        result = self.analyze(change)
        for finding in result['impacts']:
            if finding['system_id'] == 'AI-002':
                self.assertEqual(finding['draft_applicability'], impact.UNKNOWN)
                self.assertEqual(finding['state'], 'unresolved')
                self.assertIn('SYSTEMS.use_case', finding['reason'])
            else:
                original = next(r for r in self.baseline['impacts'] if r['id'] == finding['id'])
                self.assertEqual(finding, original)
        self.assertTrue(all(r['approval_status'] == 'pending' for r in result['impacts']))

    def test_new_prose_missing_context_and_missing_field_are_review_blockers(self):
        for kind in ('new prose', 'missing context', 'missing field'):
            def change(four):
                if kind == 'new prose':
                    c = next(r for r in four['state']['policy_controls'] if r['heading'] == 'AI-008')
                    c['excerpt'] = 'New current use: fictional presenters and new outputs.\n'
                elif kind == 'missing context':
                    four['state']['policy_controls'] = [r for r in four['state']['policy_controls'] if r['heading'] != 'AI-008']
                else:
                    four['state']['system_facts'][7]['values']['use_case'] = ''
            with self.subTest(kind=kind):
                result = self.analyze(change)
                self.assertTrue(all(f['draft_applicability'] == impact.UNKNOWN for f in result['impacts'] if f['system_id'] == 'AI-008'))
                self.assertTrue(result['review_blockers'])

    def test_whitespace_names_and_new_versions_are_not_operating_changes(self):
        def change(four):
            for c in four['state']['policy_controls']:
                c['excerpt'] = re.sub(r'\s+', ' ', c['excerpt'].split('\n', 1)[-1]).strip()
            for row in four['state']['system_facts']:
                row['values']['system_name'] = 'Renamed inventory label'
                row['values']['record_version'] = 'register-2026-08-27'
        self.assertEqual(self.analyze(change), self.baseline)

    def test_changed_role_scope_and_invalid_context_date_do_not_abort(self):
        for heading in ('Operating scope', 'Article 50 review — company operating facts'):
            def change(four):
                section = next(r for r in four['state']['policy_controls'] if r['heading'] == heading)
                section['excerpt'] = 'Changed scope without verified current role facts or usable dates.'
            result = self.analyze(change)
            self.assertTrue(all(f['draft_applicability'] == impact.UNKNOWN for f in result['impacts']))
            self.assertTrue(all(r['provider_assessment'] == 'unresolved' for r in result['role_assessments']))

    def test_market_date_recomputes_transition_and_ambiguous_timing_is_withheld(self):
        def change_date(four):
            context = next(c for c in four['state']['policy_controls'] if c['heading'] == 'Product timing and evidence limits')
            context['excerpt'] = context['excerpt'].replace('1 June 2026', '2 August 2026')
        result = self.analyze(change_date)
        self.assertTrue(all(r['assessment'] == 'supported-draft-ineligible' for r in result['transition_assessments'] if r['system_id'] in {'AI-003','AI-008'}))
        def unknown(four):
            context = next(c for c in four['state']['policy_controls'] if c['heading'] == 'Product timing and evidence limits')
            context['excerpt'] = 'A new release might be available; its market date and relevant product are unconfirmed.'
        result = self.analyze(unknown)
        self.assertTrue(all(r['assessment'] == 'unresolved' and r['market_entry_date'] is None for r in result['transition_assessments'] if r['system_id'] in {'AI-003','AI-008'}))
        disclosure = next(f for f in result['impacts'] if f['id'] == 'impact-AI-008-deployer-50-4-deepfake')
        self.assertEqual(disclosure['draft_applicability'], impact.APPLIES)

    def test_missing_evidence_record_is_visible_not_a_fixed_count_error(self):
        def change(four):
            four['state']['incident_evidence'] = []
            four['state']['conflicts'] = []
        result = self.analyze(change)
        self.assertTrue(any(b['category'] == 'missing-evidence-record' for b in result['review_blockers']))
        self.assertTrue(all(f['draft_applicability'] == impact.UNKNOWN for f in result['impacts']))

    def test_ambiguous_dates_and_missing_policy_are_explicit_review_blockers(self):
        def dates(four):
            header = next(r for r in four['state']['policy_controls'] if r['heading'] == 'Article 50 review — company operating facts')
            header['excerpt'] += '\nBusiness observation date: 1 September 2026.\n'
        result = self.analyze(dates)
        self.assertTrue(all(f['draft_applicability'] == impact.UNKNOWN for f in result['impacts']))
        def policy(four):
            four['state']['policy_controls'] = [r for r in four['state']['policy_controls'] if r['heading'] != 'Evidence and exceptions']
        result = self.analyze(policy)
        self.assertTrue(any(b['policy_only'] for b in result['review_blockers']))
        self.assertEqual([f['state'] for f in result['impacts']], [f['state'] for f in self.baseline['impacts']])
        self.assertTrue(all(p['review_state']=='unresolved' for p in result['policy_expectations']))

    def test_invalid_state_and_missing_field_are_not_treated_as_changed_operating_use(self):
        for value, category in [('', 'missing-evidence-value'), ('approved', 'invalid-evidence-state')]:
            def change(four):
                four['state']['incident_evidence'][0]['values']['evidence_state'] = value
            result = self.analyze(change)
            self.assertTrue(any(b['category'] == category for b in result['review_blockers']))
            self.assertTrue(all(f['approval_status']=='pending' for f in result['impacts']))

    def test_reassigned_record_withholds_both_systems_and_updated_proof_does_not_auto_resolve(self):
        def move(four):
            row = next(r for r in four['state']['incident_evidence'] if r['source_record_id']=='REC-003')
            row['system_id'] = row['values']['system_id'] = 'AI-001'
            four['state']['conflicts'] = []
        result = self.analyze(move)
        self.assertTrue(all(f['draft_applicability']==impact.UNKNOWN for f in result['impacts'] if f['system_id'] in {'AI-001','AI-003'}))
        def refreshed(four):
            row = next(r for r in four['state']['incident_evidence'] if r['source_record_id']=='REC-003')
            row['values']['evidence_state'] = 'complete'
            four['state']['conflicts'] = [r for r in four['state']['conflicts'] if r['source_record_id']!='REC-003']
        result = self.analyze(refreshed)
        self.assertTrue(all(f['state']=='unresolved' for f in result['impacts'] if f['system_id']=='AI-003'))

    def test_each_legal_document_is_parsed_once_per_verification_without_persistent_cache(self):
        selected = w.ROOT / 'deliverables/snapshots/04-evidence-reconciliation.json'
        with patch.object(impact.authority, 'visible_text', wraps=impact.authority.visible_text) as parser:
            impact.inputs(selected)
        self.assertEqual(parser.call_count, len({c['path'] for c in self.three['state']['citations']}))


class ChangedInputWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.WorkflowTests.setUpClass.__func__(cls)
        cls.tables = {}
        capture = json.loads((w.ROOT / 'deliverables/snapshots/02-source-capture-attempt-004.json').read_bytes())
        for table in capture['state']['register_tables']:
            if table['format'] == 'csv':
                cls.tables[table['source_name']] = table
        cls.workbooks = {registers.workbook_id(t['original_url']): name for name,t in cls.tables.items()}

    setUp = fixtures.WorkflowTests.setUp
    transport = fixtures.WorkflowTests.transport
    run_workflow = fixtures.WorkflowTests.run_workflow
    run_dir = fixtures.WorkflowTests.run_dir
    assert_chain = fixtures.WorkflowTests.assert_chain

    def modified(self, duplicate=False):
        def transport(url, timeout):
            response = self.transport(url, timeout)
            name = next((name for workbook,name in self.workbooks.items() if workbook in url), None)
            if name not in {'EVIDENCE', 'SYSTEMS'}:
                return response
            table = self.tables[name]
            rows = [copy.deepcopy(r['values']) for r in table['records']]
            headers = list(table['headers'])
            if name == 'EVIDENCE':
                headers += ['record_version']
                extra = dict(rows[0], record_id='REC-001' if duplicate else 'REC-011', system_id='AI-001',
                             record_type='incident', status='open', evidence_state='conflicting',
                             notes='Current owner report and observed interaction disagree; review required.',
                             record_version='evidence-2026-08-27')
                rows.append(extra)
            else:
                row = next(r for r in rows if r['system_id'] == 'AI-002')
                row.update(use_case='Public-interest text publication; actual editorial responsibility awaits verification',
                           owner='Admissions EU', record_version='register-2026-08-27')
            grid = [headers] + [[r.get(h, '') for h in headers] for r in rows]
            if 'format=csv' in url:
                output = io.StringIO(newline='')
                csv.writer(output).writerows(grid)
                response['body'] = output.getvalue().encode()
            else:
                html = '<table class="waffle">' + ''.join('<tr>' + ''.join('<td>' + escape(v) + '</td>' for v in row) + '</tr>' for row in grid) + '</table>'
                response['body'] = re.sub(r'<table class="waffle\b[\s\S]*?</table>', lambda _: html, response['body'].decode(), count=1).encode()
            return response
        return transport

    def test_eleventh_conflict_changed_facts_recompute_through_stage07_and_preserve_history(self):
        first = self.run_workflow()
        before = {str(p.relative_to(self.run_dir(first))): p.read_bytes() for p in self.run_dir(first).rglob('*') if p.is_file()}
        manual = self.root / 'references/manual/policy-manual-reference.md'
        manual.write_text(manual.read_text().replace('presenters are real people', 'presenters are fictional'))
        second = self.run_workflow(transport=self.modified())
        final = self.assert_chain(second)
        directory = self.run_dir(second)
        four = json.loads((directory / 'snapshots/04-evidence-reconciliation.json').read_bytes())
        five = json.loads((directory / 'snapshots/05-impact-analysis.json').read_bytes())
        six = json.loads((directory / 'snapshots/06-actions-and-approvals.json').read_bytes())
        row = next(r for r in four['state']['incident_evidence'] if r['source_record_id'] == 'REC-011')
        self.assertEqual(four['state']['coverage']['evidence_record_count'], 11)
        self.assertEqual(row['source_record_version'], 'evidence-2026-08-27')
        self.assertEqual(row['system_id'], 'AI-001')
        self.assertEqual(len(row['provenance']), 2)
        self.assertTrue(all(p['row_number'] == 12 and p['gid'] == '0' for p in row['provenance']))
        self.assertIn('conflict-REC-011', [r['id'] for r in four['state']['conflicts']])
        for finding in five['state']['impacts']:
            if finding['system_id'] in {'AI-001','AI-002','AI-008'}:
                self.assertEqual(finding['draft_applicability'], impact.UNKNOWN)
                self.assertEqual(finding['state'], 'conflicting' if finding['system_id']=='AI-001' else 'unresolved')
        for sid in ('AI-001','AI-002','AI-008'):
            proposal = next(p for p in six['state']['proposed_actions'] if p['id'] == 'PROP-' + sid + '-CURRENT-FACTS')
            self.assertIsNone(proposal['proposed_due_date'])
            self.assertEqual(proposal['approval_status'], 'pending')
        self.assertEqual(next(p for p in six['state']['proposed_actions'] if p['id']=='PROP-AI-002-CURRENT-FACTS')['owner'], 'Admissions EU')
        self.assertTrue(all(r['status']=='pending' and r['delivery_status']=='not-sent' for r in six['state']['approval_requirements']))
        self.assertEqual(len(final['state']['review_request_bindings']), len(six['state']['approval_requirements']))
        self.assertEqual(final['state']['publication_status'], 'blocked')
        brief = (directory / 'compliance-brief.md').read_text()
        self.assertIn('REC-011 (AI-001): conflicting', brief)
        self.assertIn('Current input review blockers', brief)
        self.assertEqual(before, {str(p.relative_to(self.run_dir(first))): p.read_bytes() for p in self.run_dir(first).rglob('*') if p.is_file()})
        history = self.root / 'deliverables/history' / first['run_id']
        for name, raw in before.items():
            self.assertEqual((history / name).read_bytes(), raw)

    def test_duplicate_record_failure_retains_diagnostics_and_fresh_retry_links(self):
        first = self.run_workflow()
        with self.assertRaises(ValueError):
            self.run_workflow(transport=self.modified(duplicate=True))
        failed = next(json.loads(p.read_bytes()) for p in (self.root/'deliverables/runs').glob('*/result.json')
                      if json.loads(p.read_bytes())['outcome']=='failed')
        self.assertEqual(failed['failed_stage'], '04-evidence-reconciliation.json')
        self.assert_chain(first)
        self.calls.clear()
        retry = self.run_workflow(transport=self.modified(), retry_run=failed['run_id'])
        self.assertEqual(len(self.calls), 13)
        self.assertNotEqual(retry['run_id'], first['run_id'])
        self.assertNotEqual(retry['run_id'], failed['run_id'])
        self.assert_chain(retry)
