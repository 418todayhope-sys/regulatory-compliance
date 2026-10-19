"""Validate current facts against an explicit reviewed basis; never interpret new prose."""
from datetime import datetime
import json
from pathlib import Path
import re

from capture import digest

PROFILE = Path('regulatory-change-impact-brief/references/reviewed-case.json')
ENGINE_PROFILE_SHA256 = 'sha256:0142224a7f843720262f4d4d24ac863301631c19fa77fffc4e1f52d5710145db'
SYSTEM_IDS = tuple(f'AI-{i:03}' for i in range(1, 9))


def normalized(text):
    # Headings/layout/whitespace do not change the recorded prose meaning.
    return re.sub(r'\s+', ' ', re.sub(r'^#+[^\n]*\n', '', text)).strip()


def parse_date(text):
    for fmt in ('%Y-%m-%d', '%d %B %Y'):
        try:
            return datetime.strptime(text.strip(), fmt).date().isoformat()
        except ValueError:
            pass
    return None


def assess(four):
    state = four['state']
    config = state.get('analysis_profile')
    profile_path = Path(config['path']) if config else Path(__file__).resolve().parents[1] / 'references/reviewed-case.json'
    raw = profile_path.read_bytes()
    if config and digest(raw) != config['sha256']:
        raise ValueError('Reviewed analysis configuration hash mismatch')
    if digest(raw) != ENGINE_PROFILE_SHA256:
        raise ValueError('Reviewed configuration changed without a matching interpretation-engine revision')
    profile = json.loads(raw)
    facts = {r['system_id']: r for r in state['system_facts']}
    if set(facts) != set(SYSTEM_IDS) or len(state['system_facts']) != 8:
        raise ValueError('Expected eight distinct case systems; changed scope requires a new reviewed scope')
    if profile['profile_version'] != 'reviewed-case/1' or set(profile['systems']) != set(SYSTEM_IDS):
        raise ValueError('Unsupported reviewed analysis configuration')
    sections, blockers = {}, []
    for r in state['policy_controls']:
        sections.setdefault(r['heading'], []).append(r)
    def section(heading):
        matches = sections.get(heading, [])
        return matches[0] if len(matches) == 1 else None
    def block(sid, category, field, observed, expected=None, refs=None, timing_only=False, policy_only=False):
        relevant = refs or [facts[sid]['id']]
        record = {'id': f'review-{sid}-{len(blockers)+1:03}', 'system_id': sid,
                  'summary': f'{sid}: {category} ({field}); current evidence requires owner/Legal review, not reuse of the prior interpretation.',
                  'evidence_ids': list(dict.fromkeys(relevant)), 'category': category, 'field': field,
                  'observed': observed, 'reviewed_basis': expected, 'timing_only': timing_only, 'policy_only': policy_only,
                  'owner': facts[sid]['values'].get('owner'), 'status': 'unresolved', 'approval_status': 'pending',
                  'resolution_need': 'System owner to confirm the current version and actual facts; Legal to review affected actor/rule applicability; Operations to authorize any policy or date change.'}
        blockers.append(record)
    for sid, fact in facts.items():
        for field in profile['system_fields']:
            value = fact['values'].get(field)
            if value != profile['systems'][sid][field]:
                block(sid, 'missing-operating-fact' if not value else 'changed-operating-fact',
                      'SYSTEMS.' + field, value, profile['systems'][sid][field])
        current = section(sid)
        expected = profile['contexts'].get(sid)
        if current is None or normalized(current['excerpt']) != normalized(expected or ''):
            refs = [r['id'] for r in sections.get(sid, [])] or [fact['id']]
            block(sid, 'missing-or-ambiguous-context' if current is None else 'changed-operating-context',
                  sid, current['excerpt'] if current else None, expected, refs)
    operating = section('Operating scope')
    if operating is None or normalized(operating['excerpt']) != normalized(profile['contexts']['Operating scope']):
        for sid in facts:
            block(sid, 'missing-or-changed-role-context', 'Operating scope', operating['excerpt'] if operating else None,
                  profile['contexts']['Operating scope'], [operating['id']] if operating else None)
    for heading in ('Learner and public transparency', 'Evidence and exceptions', 'Approval boundary'):
        current = section(heading)
        if current is None or normalized(current['excerpt']) != normalized(profile['contexts'][heading]):
            for sid in facts:
                block(sid, 'missing-or-changed-policy-context', heading, current['excerpt'] if current else None,
                      profile['contexts'][heading], [current['id']] if current else None, policy_only=True)
    header = section('Article 50 review — company operating facts')
    header_text = header['excerpt'] if header else ''
    def dated(label):
        matches = re.findall(re.escape(label) + r':\s*([^.;\n]+)', header_text)
        return parse_date(matches[0]) if len(matches) == 1 else None
    observed_date, authored_date = dated('Business observation date'), dated('Authoring clarification date')
    if observed_date != '2026-08-26' or authored_date is None:
        for sid in facts:
            block(sid, 'unverified-context-date', 'context dates',
                  {'observation': observed_date, 'authoring': authored_date}, refs=[header['id']] if header else None)
    timing = section('Product timing and evidence limits')
    timing_text = timing['excerpt'] if timing else ''
    match = re.search(r'first offered commercially in the EU on (\d{1,2} \w+ \d{4}|\d{4}-\d{2}-\d{2})', timing_text)
    market_date = parse_date(match[1]) if match else None
    def timing_template(text):
        return re.sub(r'first offered commercially in the EU on (\d{1,2} \w+ \d{4}|\d{4}-\d{2}-\d{2})',
                      'first offered commercially in the EU on <market-entry-date>', normalized(text))
    if market_date is None or timing_template(timing_text) != timing_template(profile['contexts']['Product timing and evidence limits']):
        market_date = None
        for sid in ('AI-003', 'AI-008'):
            block(sid, 'unverified-product-timing', 'market-entry facts', timing_text or None,
                  refs=[timing['id']] if timing else None, timing_only=True)
    actual = {r['source_record_id']: r for r in state['incident_evidence']}
    for record_id, reviewed in profile['evidence'].items():
        if record_id not in actual:
            block(reviewed['system_id'], 'missing-evidence-record', record_id, None, reviewed)
    for record_id, row in actual.items():
        sid, values = row['system_id'], row['values']
        if sid not in facts:
            raise ValueError('Unknown system_id in evidence; join validation required')
        if not values.get('record_type') or not values.get('evidence_state'):
            block(sid, 'missing-evidence-value', record_id, values, refs=[row['id'], facts[sid]['id']])
        elif values['evidence_state'] not in {'complete','missing','stale','conflicting','partial','unverified','unknown','not-applicable','not_applicable'}:
            block(sid, 'invalid-evidence-state', record_id, values['evidence_state'], refs=[row['id'], facts[sid]['id']])
        reviewed = profile['evidence'].get(record_id)
        if reviewed and reviewed['system_id'] != sid:
            original_sid = reviewed['system_id']
            block(original_sid, 'reassigned-evidence-record', record_id, {'current_system_id': sid}, reviewed,
                  [row['id'], facts[original_sid]['id']])
        changes = {k: {'observed': values.get(k), 'reviewed': reviewed.get(k) if reviewed else None}
                   for k in profile['evidence_fields'] if reviewed is None or values.get(k) != reviewed.get(k)}
        if changes:
            block(sid, 'additional-evidence-record' if reviewed is None else 'changed-evidence-record', record_id,
                  changes, reviewed, [row['id'], facts[sid]['id']])
    return {'profile': profile, 'profile_sha256': digest(raw), 'sections': sections, 'section': section,
            'blockers': blockers, 'observed_date': observed_date, 'authored_date': authored_date,
            'market_date': market_date, 'configured': config is not None}


def apply(state, four, review):
    """Withhold affected interpretations; never decide new legal triggers from changed prose."""
    blockers = review['blockers']
    for finding in state['impacts']:
        relevant = [b for b in blockers if b['system_id'] == finding['system_id'] and not b['policy_only'] and
                    (not b['timing_only'] or finding['id'].endswith('product-provider-50-2'))]
        if relevant:
            conflicts = [r for r in four['state']['conflicts'] if r['system_id'] == finding['system_id']]
            finding.update(state='conflicting' if conflicts else 'unresolved', draft_applicability='unresolved',
                           reason='Current input review withholds this actor/rule interpretation: ' + ' '.join(b['summary'] for b in relevant),
                           conditional_on=['Resolve current source facts and obtain version-specific Legal review.'])
            finding['summary'] = finding['reason']
            finding['evidence_ids'] = list(dict.fromkeys(finding['evidence_ids'] + [b['id'] for b in relevant]))
    full_sids = {b['system_id'] for b in blockers if not b['timing_only'] and not b['policy_only']}
    timing_sids = full_sids | {b['system_id'] for b in blockers if b['timing_only']}
    for role in state['role_assessments']:
        if role['system_id'] in full_sids:
            role.update(provider_assessment='unresolved', deployer_assessment='unresolved',
                        category='unresolved-operating-facts', basis='Current operating facts changed or are missing; no role is inferred from inventory labels or an outdated context.')
            role['evidence_ids'] += [b['id'] for b in blockers if b['system_id'] == role['system_id'] and not b['policy_only']]
    for transition in state['transition_assessments']:
        if transition['system_id'] in timing_sids:
            transition.update(assessment='unresolved', transition_phase=None)
            transition['evidence_ids'] += [b['id'] for b in blockers if b['system_id'] == transition['system_id'] and not b['policy_only']]
    for question in state['unresolved_items']:
        relevant = [b for b in blockers if b['system_id'] == question['system_id']]
        if relevant:
            question['specific_questions'] = [b['summary'] + ' ' + b['resolution_need'] for b in relevant]
            question['evidence_ids'] += [b['id'] for b in relevant]
    for policy in state['policy_expectations']:
        relevant = [b for b in blockers if b['system_id'] == policy['system_id']]
        if relevant:
            policy['review_state'] = 'unresolved'
            policy['summary'] = 'Current source/policy changes require review; no prior policy fulfilment or authorization is carried forward.'
            policy['evidence_ids'] += [b['id'] for b in relevant]
    state['unaffected_items'] = [r for r in state['unaffected_items'] if
                               next(f for f in state['impacts'] if r['evidence_ids'][0] == f['id'])['draft_applicability'] == 'supported-draft-non-applicability']
    if blockers or review['configured']:
        state['review_blockers'] = blockers
        state['analysis_configuration'] = {'profile_version': review['profile']['profile_version'], 'sha256': review['profile_sha256'],
                                           'meaning': 'Reviewed interpretation configuration, not a current company source or approval.'}
    for collection in state.values():
        if isinstance(collection, list):
            for record in collection:
                if isinstance(record, dict) and 'evidence_ids' in record:
                    record['evidence_ids'] = list(dict.fromkeys(record['evidence_ids']))
    return state
