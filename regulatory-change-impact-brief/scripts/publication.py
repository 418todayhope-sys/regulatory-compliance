"""Stage 07: create and inspect local DRAFT files; never deliver or approve them."""
import argparse
import copy
import csv
from datetime import date, datetime, timezone
import io
import json
from pathlib import Path
import re
from uuid import NAMESPACE_URL, uuid4, uuid5

import actions
from capture import digest, now
from scope import ROOT, validate

COLUMNS = ['impact_id', 'system_id', 'rule_ref', 'state', 'evidence_ids', 'reason',
           'owner', 'proposed_action', 'proposed_due_date', 'approval_status']
FILES = ('impact-register.csv', 'compliance-brief.md', 'action-calendar.ics')
SNAPSHOT = 'snapshots/07-publication-validation.json'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def inputs(stage06, root=ROOT):
    stage06 = Path(stage06)
    raw = stage06.read_bytes()
    six = json.loads(raw)
    if Path(six['predecessor']['path']).is_absolute():
        stage06 = stage06.resolve()
    else:
        stage06 = stage06.resolve().relative_to(root.resolve())
    validate(six, root)
    require(six['stage'] == 'actions-and-approvals' and six['sequence'] == 6, 'Expected Stage 06')
    parent = Path(six['predecessor']['path'])
    require(digest(parent.read_bytes()) == six['predecessor']['sha256'], 'Stage 05 predecessor hash mismatch')
    five, four, chain, raw05 = actions.inputs(parent, root)
    require(six['predecessor']['snapshot_id'] == five['snapshot_id'] and six['run_id'] == five['run_id'],
            'Stage 06 predecessor/run mismatch')
    basis = {'snapshot_id': five['snapshot_id'], 'path': str(parent), 'sha256': digest(raw05)}
    require(six['state'] == actions.assemble(five, four, chain, basis), 'Stage 06 proposals differ from verified basis')
    require(six['unresolved'] == five['unresolved'] + six['state']['escalations'], 'Stage 06 unresolved records changed')
    require(len(five['state']['impacts']) == 64, 'Expected 64 impact findings')
    require(six['state']['as_of'] == '2026-08-26T00:00:00Z', 'Assigned review date changed')
    return six, five, four, chain, raw, stage06


def local_actions(finding, six):
    return [a for a in six['state']['proposed_actions']
            if a['system_id'] == finding['system_id'] and finding['id'] in a['impact_ids']]


def register_rows(data):
    six, five, four, *_ = data
    facts = {r['system_id']: r for r in four['state']['system_facts']}
    result = []
    for f in five['state']['impacts']:
        linked = local_actions(f, six)
        # A single date cell cannot express several proposals or dated/undated mixtures.
        due = linked[0]['proposed_due_date'] if len(linked) == 1 else None
        resolution = ('No system-specific action for this scoped finding; Legal review REQ-LEGAL-' + f['system_id'] +
                      ' and global coordination ACT-008 remain pending; no individual due date is assigned.') if not linked else (
                      'Action/date mapping: ' + '; '.join(a['id'] + '=' + (a['proposed_due_date'] or 'undated pending authorization') for a in linked) +
                      '. A date cell is populated only for one linked, dated action; consult the brief/calendar. All dates are unapproved proposals.')
        result.append(dict(zip(COLUMNS, [f['id'], f['system_id'], '; '.join(f['rule_refs']), f['state'],
                      ';'.join(f['evidence_ids']),
                      f"DRAFT; run={six['run_id']}; as-of=2026-08-26; {f['draft_applicability']}; actor={f['subject_actor']}. " + f['reason'] + ' ' + resolution,
                      '; '.join(dict.fromkeys(a['owner'] for a in linked)) or facts[f['system_id']]['values']['owner'],
                      '; '.join(a['id'] + ': ' + a['proposed_action'] for a in linked), due or '', f['approval_status']])))
    return result


def render_csv(data):
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=COLUMNS, lineterminator='\r\n')
    writer.writeheader()
    writer.writerows(register_rows(data))
    return output.getvalue().encode('utf-8')


def text_escape(value):
    return value.replace('\\', '\\\\').replace('\r\n', '\n').replace('\r', '\n').replace('\n', '\\n').replace(';', '\\;').replace(',', '\\,')


def text_unescape(value):
    result, index = [], 0
    while index < len(value):
        char = value[index]
        if char == '\\':
            index += 1
            require(index < len(value) and value[index] in 'nN,;\\', 'Invalid iCalendar TEXT escape')
            char = '\n' if value[index] in 'nN' else value[index]
        result.append(char)
        index += 1
    return ''.join(result)


def fold(line):
    """RFC 5545 content lines: <=75 octets, without splitting a UTF-8 character."""
    lines, current = [], ''
    for char in line:
        if len((current + char).encode('utf-8')) > 75:
            lines.append(current)
            current = ' '
        current += char
    return '\r\n'.join(lines + [current])


def uid(action_id):
    return str(uuid5(NAMESPACE_URL, 'quillhaven/regulatory-change-impact-brief/action/' + action_id)) + '@quillhaven.invalid'


def event_description(action, six):
    return (f"DRAFT; UNAPPROVED; approval_status=pending; action_id={action['id']}; system_ids=" +
            ','.join(action['scope']['system_ids']) + f"; owner={action['owner']}; run={six['run_id']}; as-of=2026-08-26; " +
            f"source_version={action['source_version']}; source_status={action['source_status']}; proposed date only, not an approved operational deadline. " +
            'Action: ' + action['proposed_action'] + '. Acceptance: ' + ' '.join(action['acceptance_criteria']) +
            '; rule_refs=' + ', '.join(action['rule_refs']) + '; evidence_ids=' + ','.join(action['evidence_ids']) +
            '; pending unsent request_ids=' + ','.join(action['approval_request_ids']))


def render_calendar(data):
    six = data[0]
    stamp = datetime.fromisoformat(six['created_at'].replace('Z', '+00:00')).astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Quillhaven//Regulatory Review DRAFT//EN', 'CALSCALE:GREGORIAN']
    for action in six['state']['proposed_actions']:
        if not action['proposed_due_date']:
            continue
        due = date.fromisoformat(action['proposed_due_date'])
        lines += ['BEGIN:VEVENT', 'UID:' + uid(action['id']), 'DTSTAMP:' + stamp,
                  'DTSTART;VALUE=DATE:' + due.strftime('%Y%m%d'),
                  'SUMMARY:' + text_escape('DRAFT UNAPPROVED ' + action['id'] + ': ' + action['proposed_action']),
                  'DESCRIPTION:' + text_escape(event_description(action, six)), 'STATUS:TENTATIVE', 'TRANSP:TRANSPARENT', 'END:VEVENT']
    lines += ['END:VCALENDAR']
    return ('\r\n'.join(fold(line) for line in lines) + '\r\n').encode('utf-8')


def parse_calendar(raw):
    """Strict parser for the emitted RFC 5545 subset, including UTF-8 folding/TEXT."""
    text = raw.decode('utf-8')
    require(text.endswith('\r\n') and '\n' not in text.replace('\r\n', '') and '\r' not in text.replace('\r\n', ''), 'Calendar requires CRLF')
    logical = []
    for line in text[:-2].split('\r\n'):
        require(bool(line) and len(line.encode('utf-8')) <= 75, 'Invalid calendar content-line length')
        if line.startswith((' ', '\t')):
            require(bool(logical), 'Orphan calendar fold')
            logical[-1] += line[1:]
        else:
            logical.append(line)
    require(logical[0] == 'BEGIN:VCALENDAR' and logical[-1] == 'END:VCALENDAR', 'Invalid VCALENDAR enclosure')
    header, events, event = {}, [], None
    for line in logical[1:-1]:
        if line == 'BEGIN:VEVENT':
            require(event is None, 'Nested VEVENT')
            event = {}
        elif line == 'END:VEVENT':
            require(event is not None, 'Unexpected VEVENT end')
            events.append(event)
            event = None
        else:
            key, sep, value = line.partition(':')
            target = header if event is None else event
            require(bool(sep) and key not in target, 'Malformed/duplicate calendar property')
            require(key in ({'VERSION', 'PRODID', 'CALSCALE'} if event is None else
                            {'UID', 'DTSTAMP', 'DTSTART;VALUE=DATE', 'SUMMARY', 'DESCRIPTION', 'STATUS', 'TRANSP'}), 'Unsupported calendar property')
            target[key] = value
    require(event is None and header.get('VERSION') == '2.0' and bool(header.get('PRODID')), 'Incomplete calendar')
    seen = set()
    for event in events:
        require({'UID', 'DTSTAMP', 'DTSTART;VALUE=DATE', 'SUMMARY', 'DESCRIPTION', 'STATUS'} <= event.keys(), 'Missing required event property')
        require(event['UID'] not in seen, 'Duplicate UID')
        seen.add(event['UID'])
        require(bool(re.fullmatch(r'\d{8}T\d{6}Z', event['DTSTAMP'])), 'DTSTAMP must be UTC')
        datetime.strptime(event['DTSTAMP'], '%Y%m%dT%H%M%SZ')
        require(bool(re.fullmatch(r'\d{8}', event['DTSTART;VALUE=DATE'])), 'DTSTART must be DATE')
        datetime.strptime(event['DTSTART;VALUE=DATE'], '%Y%m%d')
        require(event['STATUS'] == 'TENTATIVE', 'Event is not tentative')
        for field in ('SUMMARY', 'DESCRIPTION'):
            require('UNAPPROVED' in text_unescape(event[field]), 'Event approval boundary missing')
    return events


def render_brief(data):
    six, five, four, chain, raw, path = data
    three = chain[3]
    lines = ['# DRAFT — Article 50 impact review', '',
             f"Run ID: `{six['run_id']}`. Assigned as-of date: **2026-08-26** (UTC date anchor, not retrieval time).",
             'Intended recipients: **Legal and Operations**; scoped factual requests also name system owners.',
             '**DRAFT / UNAPPROVED / NOT SENT. Publication blocked.** This bounded package prepares human review; it is not final legal advice or a compliance determination.', '',
             f"Input: Stage 06 `{six['snapshot_id']}`, `{path}`, `{digest(raw)}`.",
             'Exact final file hashes and all request/version bindings are detached in `snapshots/07-publication-validation.json`, under `state.review_request_bindings`. This brief deliberately contains no hash of itself.', '',
             '## Authority and timing', '']
    for key, value in three['state']['authority_hierarchy'].items():
        lines.append(f'- {key}: {value}.')
    for record in three['state']['binding_rules'] + three['state']['timing_rules']:
        lines.append(f"- {record['id']}: {record['summary']} Date: {record.get('date', 'see cited provision')}. [{'; '.join(record['evidence_ids'])}].")
    lines += ['', 'Provider-only Article 50(2) transition eligibility is a conditional draft assessment, never a blanket postponement of deployer disclosure or an approved operational deadline. AI-003 and AI-008 have recorded June 1, 2026 market-entry facts; underlying notices remain unverified. Other unknown market-entry facts remain unknown.', '', '## Supported draft observations and unresolved findings', '',
              'All 64 actor/rule findings are in the CSV, including scoped supported-no-impact findings. Such findings do not mean a system is compliant. Statutory draft findings, source observations and internal policy expectations remain separate. No approval or evidence corroboration is inferred from downloaded records.', '']
    for role in five['state']['role_assessments']:
        sid = role['system_id']
        lines += [f'### {sid}', f"{role['id']}: provider={role['provider_assessment']}; deployer={role['deployer_assessment']}. {role['basis']} [{'; '.join(role['evidence_ids'])}]."]
        for f in five['state']['impacts']:
            if f['system_id'] == sid:
                lines.append(f"- {f['id']} — {f['state']}; {f['draft_applicability']}; actor: {f['subject_actor']}. {f['reason']} [{'; '.join(f['evidence_ids'])}].")
        question = next(r for r in five['state']['unresolved_items'] if r['system_id'] == sid)
        lines.append(f"Open {question['id']}: " + ' '.join(question['specific_questions']))
    lines += ['', '## Internal policy expectations — separate control basis', '']
    for record in five['state']['policy_expectations']:
        lines.append(f"- {record['id']}: {record['summary']} [{'; '.join(record['evidence_ids'])}].")
    lines += ['', '## Source limitations and preserved blockers', '',
              ('This is an offline continuation of the selected capture-004 run, not a new live retrieval. The assigned as-of date is distinct from actual retrieval timestamps below. No later retrieval proves historical guidance availability.' if path.is_absolute() else
               "This draft uses this run's newly retrieved Stage 02 evidence. The assigned as-of date is distinct from actual retrieval timestamps below. No later retrieval proves historical guidance availability."),
              'SYSTEMS, EVIDENCE and CALENDAR are source-reported records, not independently corroborated proof or approval. HTML grid and gid=0 CSV agree for the captured tab; additional undisclosed/inaccessible tabs cannot be excluded. Preserve missing, stale, partial, conflicting and unverified facets.',
              'POLICY live Notion access failed. Supplemental manual policy and operating context are user-supplied, with claimed versions and incomplete acquisition provenance; they are not successful live Notion reads, independently verified facts or approvals.',
              'REC-003 and REC-008 conflicts remain; REC-005 is stale; REC-009 has partial provenance; REC-010 is an unapproved exception with missing expiry. AI-005 release, provider/deployer role and biometric-use facts remain unresolved.',
              'Required authority questions prevent formal conclusions or normal validated publication. Useful bounded draft work and eight tentative source-dated proposals are retained for review; no policy or operational date is authorized.', '']
    for source in chain[2]['state']['sources']:
        lines.append(f"- {source['id']} ({source['source_name']}): {source['retrieval_status']}; retrieved {source['retrieved_at']}; original {source['original_url']}; bytes {source['local_reference']}; {source['content_hash']}; version {json.dumps(source['version_metadata'], ensure_ascii=False, sort_keys=True)}.")
    for record in three['state']['authority_blockers']:
        lines.append(f"- Open {record['id']}: {record['summary']} [{'; '.join(record['evidence_ids'])}].")
    lines += ['', '## Proposed actions and dates', '',
              'All 17 actions remain pending. The calendar contains only the eight source-dated proposals, each TENTATIVE and UNAPPROVED. Nine undated proposals are omitted; Operations must authorize any date. ACT-008 is one global action across all eight systems. Source calendar dates are preserved proposals, not approved deadlines.',
              'CSV due dates are populated only for a single system-specific linked action. Multiple/undated mappings leave that cell blank and disclose the mapping in the reason; global ACT-008 is not an individual finding deadline.', '']
    for action in six['state']['proposed_actions']:
        lines.append(f"- {action['id']} ({action['system_id']}; owner {action['owner']}): {action['proposed_action']}. Proposed date: {action['proposed_due_date'] or 'UNDATED — authorization pending'}; approval pending; source version {action['source_version'] or 'new undated proposal'}. Acceptance: {' '.join(action['acceptance_criteria'])} Basis: {', '.join(action['evidence_ids'])}.")
    lines += ['', '## Specific review requests — pending and unsent', '',
              'Legal owns interpretation and exception decisions. Operations owns policy activation, operational dates and incident closure. System owners confirm facts only. No actual feedback is supplied or applied. Each request below binds to all three exact final draft versions in the detached snapshot; any later feedback must match the request, subject, role, run and hashes before application.', '']
    for request in six['state']['approval_requirements']:
        lines += [f"### {request['id']} — {request['required_reviewer']}",
                  f"Status: pending; delivery: not-sent; binding: `binding-{request['id']}` in `snapshots/07-publication-validation.json`.",
                  f"Run: {request['run_id']}; source versions: {json.dumps(request['source_versions'], sort_keys=True)}.",
                  f"Subject: {json.dumps(request['subject'], sort_keys=True)}. Required roles: {', '.join(request['reviewer_roles'])}.",
                  request['question'], f"Evidence: {', '.join(request['evidence_ids'])}.", '']
    lines += ['## Citation and provenance index', '',
              'Exact legal excerpts and their excerpt hashes are retained in Stage 03. The following locators use normalized-visible-text-v1 Unicode character offsets, start inclusive/end exclusive. Register row IDs and dual HTML/CSV provenance are in Stage 04; all role/transition/impact IDs in Stage 05; action/request IDs in Stage 06.', '']
    for citation in three['state']['citations']:
        lines.append(f"- {citation['id']}: {citation['source_name']}, {citation['section']}; {citation['path']}; raw {citation['raw_sha256']}; locator {json.dumps(citation['locator'], sort_keys=True)}; excerpt {citation['excerpt_sha256']}.")
    lines += ['', 'Manual context provenance: ' + json.dumps(five['state']['source_context_provenance'], ensure_ascii=False, sort_keys=True), '']
    if 'review_blockers' in five['state']:
        brief = '\n'.join(lines)
        brief = brief.replace('All 64 actor/rule findings are in the CSV, including scoped supported-no-impact findings.',
                              'All 64 actor/rule findings are in the CSV; scoped supported-no-impact entries appear only where still supported.')
        if not four['state']['policy_controls']:
            brief = brief.replace('Supplemental manual policy and operating context are user-supplied, with claimed versions and incomplete acquisition provenance; they are not successful live Notion reads, independently verified facts or approvals.',
                                  'No supplemental manual policy or operating-context records were available; no source facts, live reads or approvals are inferred.')
        timing = '; '.join(r['system_id'] + ': market entry ' + (r['market_entry_date'] or 'unknown') +
                           ', draft assessment ' + r['assessment'] for r in five['state']['transition_assessments']
                           if r['system_id'] in {'AI-003', 'AI-008'})
        brief = brief.replace('AI-003 and AI-008 have recorded June 1, 2026 market-entry facts; underlying notices remain unverified.',
                              timing + '. Underlying notices remain unverified.')
        reported = '; '.join(r['source_record_id'] + ' (' + r['system_id'] + '): ' + r['values']['evidence_state']
                             for r in four['state']['incident_evidence']) or 'No EVIDENCE records were returned.'
        brief = brief.replace('REC-003 and REC-008 conflicts remain; REC-005 is stale; REC-009 has partial provenance; REC-010 is an unapproved exception with missing expiry. AI-005 release, provider/deployer role and biometric-use facts remain unresolved.',
                              'Current source-reported evidence states: ' + reported + '. These reports do not prove approval or independent corroboration.')
        count = len(six['state']['proposed_actions'])
        dated = sum(bool(a['proposed_due_date']) for a in six['state']['proposed_actions'])
        brief = brief.replace('All 17 actions remain pending.', f'All {count} actions remain pending.').replace('Nine undated proposals are omitted;', f'{count-dated} undated proposals are omitted;')
        brief += '\n## Current input review blockers\n\n'
        for blocker in five['state']['review_blockers']:
            brief += blocker['id'] + ': ' + blocker['summary'] + ' ' + blocker['resolution_need'] + ' Evidence: ' + ', '.join(blocker['evidence_ids']) + '.\n\n'
        return (brief + '\n').encode('utf-8')
    return '\n'.join(lines).encode('utf-8')


def render(data):
    return dict(zip(FILES, (render_csv(data), render_brief(data), render_calendar(data))))


def inspect_bytes(blobs, data):
    """Inspect final bytes against source records; a render comparison also detects prose drift."""
    six, five, four, chain, *_ = data
    known = set(i for s in [six, five, four, *chain.values()] for i in s['produced_record_ids'])
    reader = csv.DictReader(io.StringIO(blobs[FILES[0]].decode('utf-8'), newline=''), strict=True)
    require(reader.fieldnames == COLUMNS, 'CSV contract mismatch')
    rows = list(reader)
    require(len(rows) == 64 and len({r['impact_id'] for r in rows}) == 64, 'CSV coverage/identity mismatch')
    expected_rows = register_rows(data)
    require(rows == expected_rows, 'CSV source/state/action/date mismatch')
    for row in rows:
        require(set(row['evidence_ids'].split(';')) <= known, 'Dangling CSV evidence reference')
        require(row['approval_status'] == 'pending' and row['reason'].startswith('DRAFT;'), 'CSV draft/approval boundary missing')
        if row['proposed_due_date']:
            require(date.fromisoformat(row['proposed_due_date']).isoformat() == row['proposed_due_date'], 'Invalid CSV date')
    events = parse_calendar(blobs[FILES[2]])
    dated = [a for a in six['state']['proposed_actions'] if a['proposed_due_date']]
    require(len(events) == len(dated), 'Calendar dated-action coverage mismatch')
    for event, action in zip(events, dated):
        require(event['UID'] == uid(action['id']), 'Calendar action UID mismatch')
        require(event['DTSTART;VALUE=DATE'] == action['proposed_due_date'].replace('-', ''), 'Calendar proposed date mismatch')
        require(text_unescape(event['DESCRIPTION']) == event_description(action, six), 'Calendar provenance/action mismatch')
    brief = blobs[FILES[1]].decode('utf-8')
    require(all(term in brief for term in ['DRAFT', 'UNAPPROVED', six['run_id'], '2026-08-26', 'Legal and Operations', 'Publication blocked']), 'Brief scope/status mismatch')
    require(all(request['question'] in brief and f"binding-{request['id']}" in brief for request in six['state']['approval_requirements']), 'Missing review request')
    require(blobs == render(data), 'Final draft bytes differ from deterministic source-derived output')
    return [
        ('csv-contract-coverage', 'Exact ten-column UTF-8 contract; 64 unique source findings, original states/reasons and traceable evidence.'),
        ('calendar-rfc5545', 'CRLF/UTF-8 octet folding, escaped TEXT, stable UIDs, UTC DTSTAMP and valid all-day DATE syntax.'),
        ('calendar-proposals', 'Only dated actions; matching source dates, TENTATIVE/unapproved status and one global ACT-008.'),
        ('brief-review-boundaries', 'Run/as-of/recipients, authority and unresolved findings, pending unsent requests and detached binding references.'),
        ('cross-file-agreement', 'Final bytes reproduce verified Stage 05–06 facts and separate policy, observations, draft findings and approvals.')]


def artifacts_for(blobs, destination, root=ROOT, portable=False):
    if portable:
        destination = destination.resolve().relative_to(root.resolve())
    return [{'id': 'artifact-' + name.split('.')[0], 'path': str(destination / name) if portable else str((destination / name).resolve()),
             'sha256': digest(blobs[name]), 'validation_status': 'valid', 'draft_status': 'DRAFT'} for name in FILES]


def bindings_for(six, artifacts, basis):
    return [{'id': 'binding-' + request['id'], 'summary': 'Unsent review request bound to exact final DRAFT bytes.',
             'evidence_ids': [request['id']] + [a['id'] for a in artifacts], 'request_id': request['id'],
             'run_id': six['run_id'], 'subject': copy.deepcopy(request['subject']),
             'required_reviewer': request['required_reviewer'], 'reviewer_roles': request['reviewer_roles'],
             'source_versions': copy.deepcopy(request['source_versions']), 'review_basis_snapshot': basis,
             'artifacts': copy.deepcopy(artifacts), 'status': 'pending', 'delivery_status': 'not-sent', 'feedback': None}
            for request in six['state']['approval_requirements']]


def make_snapshot(data, blobs, destination, root=ROOT):
    six, five, four, chain, raw, path = data
    inspected = inspect_bytes(blobs, data)
    basis = {'snapshot_id': six['snapshot_id'], 'path': str(path), 'sha256': digest(raw)}
    artifacts = artifacts_for(blobs, destination, root, portable=not path.is_absolute())
    bindings = bindings_for(six, artifacts, basis)
    checks = [{'id': 'check-publication-' + key, 'summary': summary, 'evidence_ids': [a['id'] for a in artifacts], 'status': 'passed'}
              for key, summary in inspected + [('hash-bindings', 'Actual final-byte hashes bind every pending request to all three drafts; no circular draft hash.'),
                                               ('snapshot-chain', 'Schema and predecessor hashes, same run/as-of, immutable raw evidence and reproduced Stage 05–06 basis verified.')]]
    decision = {'id': 'd-publication-draft-only', 'summary': 'Retain a useful review-ready bounded draft with blocked publication.',
                'evidence_ids': [a['id'] for a in artifacts] + [r['id'] for r in chain[3]['state']['authority_blockers']],
                'concern': 'Avoid promoting technically valid draft files or source dates into legal approval or publication.',
                'options': ['Prepare bounded local drafts with explicit unresolved authority', 'Defer all draft work'],
                'chosen_behavior': 'Write three DRAFT artifacts, retain eight tentative source-dated proposals and bind unsent requests; publication remains blocked.',
                'rationale': 'The captured evidence supports reviewable scoped drafts but unresolved authority, facts and approvals prevent formal conclusions.',
                'tradeoffs': ['Technical validation passes without resolving legal questions or authorizing execution.'],
                'downstream_effect': 'Any later feedback must match exact request/run/role/subject/file hashes; changed drafts require new detached bindings.'}
    consumed = list(dict.fromkeys(i for s in [six, five, four, *chain.values()] for i in s['produced_record_ids']))
    result = {'schema_version': six['schema_version'], 'snapshot_id': 'snapshot-' + str(uuid4()), 'run_id': six['run_id'],
              'stage': 'publication-validation', 'sequence': 7, 'created_at': now(), 'status': 'blocked', 'predecessor': basis,
              'consumed_record_ids': consumed, 'produced_record_ids': [r['id'] for r in artifacts + bindings + checks + [decision]],
              'state': {'artifacts': artifacts, 'validation_checks': checks, 'publication_status': 'blocked',
                        'draft_validation_status': 'passed', 'readiness': 'human-review-ready-bounded-draft',
                        'as_of': six['state']['as_of'], 'as_of_convention': six['state']['as_of_convention'],
                        'review_request_bindings': bindings, 'actual_feedback_applied': [],
                        'approval_boundary': copy.deepcopy(six['state']['approval_boundary']),
                        'dated_action_ids': [a['id'] for a in six['state']['proposed_actions'] if a['proposed_due_date']],
                        'undated_action_ids': [a['id'] for a in six['state']['proposed_actions'] if not a['proposed_due_date']],
                        'impact_count': len(five['state']['impacts']), 'draft_time_convention': 'Deterministic event DTSTAMP is actual Stage 06 creation time in UTC; as-of is a separate date anchor.',
                        'delivery_status': 'not-sent', 'final_draft_binding_status': 'bound-pending-human-review'},
              'unresolved': copy.deepcopy(six['unresolved']), 'decisions': [decision]}
    validate(result, root)
    return result


def verify_bundle(destination, data=None, root=ROOT):
    """Read-only revalidation. Never repair a tampered file or silently rebind its hash."""
    snapshot = json.loads((destination / SNAPSHOT).read_bytes())
    validate(snapshot, root)
    if data is None:
        data = inputs(Path(snapshot['predecessor']['path']), root)
    blobs = {name: (destination / name).read_bytes() for name in FILES}
    expected = make_snapshot(data, blobs, destination, root)
    # Only identity and observed validation time are deliberately nondeterministic.
    for key in expected:
        if key not in {'snapshot_id', 'created_at'}:
            require(snapshot[key] == expected[key], 'Snapshot integrity/binding mismatch: ' + key)
    return snapshot


def generate(stage06, destination, root=ROOT):
    targets = [destination / name for name in (*FILES, SNAPSHOT)]
    for target in targets:
        if target.exists():
            raise FileExistsError(target)
    data = inputs(stage06, root)
    blobs = render(data)
    inspect_bytes(blobs, data)
    destination.mkdir(parents=True, exist_ok=True)
    for name, content in blobs.items():
        with (destination / name).open('xb') as output:
            output.write(content)
    # Hash/revalidate bytes read after writing, rather than trusting in-memory output.
    actual = {name: (destination / name).read_bytes() for name in FILES}
    snapshot = make_snapshot(data, actual, destination, root)
    targets[-1].parent.mkdir(parents=True, exist_ok=True)
    with targets[-1].open('x', encoding='utf-8') as output:
        json.dump(snapshot, output, ensure_ascii=False, indent=2)
        output.write('\n')
    return verify_bundle(destination, data, root)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--actions', type=Path, default=ROOT / 'deliverables/snapshots/06-actions-and-approvals.json')
    parser.add_argument('--destination', type=Path, default=ROOT / 'deliverables')
    parser.add_argument('--validate-only', action='store_true', help='Read-only inspection of actual drafts, hashes and chain')
    args = parser.parse_args()
    result = verify_bundle(args.destination.resolve()) if args.validate_only else generate(args.actions.resolve(), args.destination.resolve())
    print(f"Stage 07: {result['state']['impact_count']} findings; {len(result['state']['dated_action_ids'])} tentative events; "
          f"{len(result['state']['review_request_bindings'])} pending unsent bindings; draft validation passed; publication BLOCKED.")


if __name__ == '__main__':
    main()
