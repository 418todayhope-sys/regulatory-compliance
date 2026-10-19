"""Run all seven stages with fresh retrieval and append-only recovery/history."""
import argparse
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import re
from uuid import uuid4

import actions
import authority
import capture
import impact
import publication
import reconcile
import scope
import operating
from capture import digest, now
from scope import ROOT, validate

NAMES = ('01-scope.json', '02-source-capture.json', '03-authority-and-timing.json',
         '04-evidence-reconciliation.json', '05-impact-analysis.json',
         '06-actions-and-approvals.json', '07-publication-validation.json')
CONFIG = Path('regulatory-change-impact-brief/references/source-config.json')


def read(path):
    return json.loads(Path(path).read_bytes())


def write(path, value):
    """Every evidence/ledger write is exclusive; no output is replaced."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as output:
        json.dump(value, output, indent=2, ensure_ascii=False)
        output.write('\n')
        output.flush()
        os.fsync(output.fileno())


def copy_bytes(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    raw = source.read_bytes()
    with target.open('xb') as output:
        output.write(raw)
        output.flush()
        os.fsync(output.fileno())
    if target.read_bytes() != raw:
        raise ValueError('Preservation copy verification failed')
    return digest(raw)


@contextmanager
def workspace(root):
    """Relative evidence paths always resolve against the selected repository."""
    before = Path.cwd()
    os.chdir(root)
    try:
        yield
    finally:
        os.chdir(before)


@contextmanager
def locked():
    Path('deliverables').mkdir(exist_ok=True)
    # This empty coordination file is not evidence. flock is released even on crash.
    with Path('deliverables/.workflow.lock').open('a') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Another workflow owns the repository lock') from None
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def inventory(directory, legacy=False):
    """Preserve all available files, including extra requests/approvals, not just a whitelist."""
    records = []
    if not directory.exists():
        return records
    for path in sorted(directory.rglob('*')):
        relative = path.relative_to(directory)
        if legacy and relative.parts[0] in {'runs', 'history', '.workflow.lock'}:
            continue
        if path.is_symlink():
            raise ValueError('Symlink in run evidence; inspect before retry')
        if path.is_file():
            records.append({'source_path': str(path), 'relative_path': str(relative),
                            'sha256': digest(path.read_bytes()), 'size': path.stat().st_size})
    return records


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def prior_issues(directory):
    """Record pre-existing damage; never describe the history copy as a repair."""
    issues = []
    for name in (*NAMES,):
        path = directory / 'snapshots' / name
        # Legacy Stage 02 can have an explicitly selected attempt filename instead.
        if not path.exists():
            issues.append({'path': str(path), 'issue': 'missing expected snapshot'})
    for name in publication.FILES:
        if not (directory / name).is_file():
            issues.append({'path': str(directory / name), 'issue': 'missing draft'})
    for name in ('started.json', 'result.json'):
        metadata = directory / name
        if metadata.exists():
            try:
                read(metadata)
            except (ValueError, OSError):
                issues.append({'path': str(metadata), 'issue': 'unreadable technical outcome/start metadata'})
        elif name == 'result.json' and (directory / 'started.json').exists():
            issues.append({'path': str(metadata), 'issue': 'missing final outcome; interrupted run not assumed complete'})
    pairs = [('path', 'sha256'), ('local_reference', 'content_hash'), ('raw_reference', 'raw_sha256'),
             ('extracted_reference', 'extracted_sha256')]
    for path in sorted((directory / 'snapshots').glob('*.json')):
        try:
            snapshot = read(path)
            validate(snapshot, Path.cwd())
            for record in walk(snapshot):
                for locator, checksum in pairs:
                    ref, expected = record.get(locator), record.get(checksum)
                    if not isinstance(ref, str) or not isinstance(expected, str) or not expected.startswith('sha256:'):
                        continue
                    target = Path(ref)
                    if not target.is_file():
                        issues.append({'path': ref, 'issue': 'referenced bytes missing', 'expected_sha256': expected})
                    elif digest(target.read_bytes()) != expected:
                        issues.append({'path': ref, 'issue': 'pre-existing hash mismatch', 'expected_sha256': expected,
                                       'observed_sha256': digest(target.read_bytes())})
        except Exception as error:
            # Schema and decoding exceptions are diagnostics, not authorization to discard bytes.
            issues.append({'path': str(path), 'issue': 'snapshot unreadable or schema-invalid', 'error_type': type(error).__name__})
    unique = {json.dumps(issue, sort_keys=True): issue for issue in issues}
    return list(unique.values())


def discover_previous():
    completed = []
    for path in Path('deliverables/runs').glob('*/result.json'):
        try:
            result = read(path)
            if (result['outcome'] == 'completed' and result['run_id'] == path.parent.name
                    and re.fullmatch(r'run-[A-Za-z0-9-]+', result['run_id'])):
                completed.append((result['finished_at'], {'run_id': result['run_id'], 'directory': path.parent,
                                  'legacy': False, 'completed': True, 'result_path': str(path)}))
        except (OSError, ValueError, KeyError, TypeError):
            continue  # Its directory is still retained; it cannot establish a successful run.
    if completed:
        return max(completed, key=lambda pair: pair[0])[1]
    directory = Path('deliverables')
    files = inventory(directory, legacy=True)
    if not files:
        return None
    run_id = None
    for name in (NAMES[-1], NAMES[0]):
        try:
            value = read(directory / 'snapshots' / name)['run_id']
            if re.fullmatch(r'run-[A-Za-z0-9-]+', value):
                run_id = value
                break
        except (OSError, ValueError, KeyError, TypeError):
            pass
    try:
        was_completed = read(directory / 'snapshots' / NAMES[-1]).get('state', {}).get('draft_validation_status') == 'passed'
    except (OSError, ValueError, TypeError):
        was_completed = False
    return {'run_id': run_id, 'directory': directory, 'legacy': True, 'completed': was_completed,
            'archive_key': run_id or 'unidentified-' + digest(json.dumps(files, sort_keys=True).encode())[7:23]}


def validate_archive(manifest_path):
    manifest = read(manifest_path)
    for item in manifest['files']:
        if digest(Path(item['archived_path']).read_bytes()) != item['sha256']:
            raise ValueError('History bytes/hash mismatch; existing archive will not be overwritten')
    return manifest


def referenced_inputs(directory, existing):
    """Legacy manual/input bytes may live outside deliverables; preserve those too."""
    known = {str(Path(item['source_path']).resolve()) for item in existing}
    result = []
    for snapshot_path in sorted((directory / 'snapshots').glob('*.json')):
        try:
            snapshot = read(snapshot_path)
        except (OSError, ValueError):
            continue
        for record in walk(snapshot):
            ref, expected = record.get('path'), record.get('sha256')
            if not isinstance(ref, str) or not isinstance(expected, str) or not expected.startswith('sha256:'):
                continue
            path = Path(ref)
            resolved = path.resolve()
            if str(resolved) in known or not path.is_file():
                continue
            try:
                relative = resolved.relative_to(Path.cwd())
            except ValueError:
                continue  # Outside-repository references are reported, never silently substituted.
            if relative.parts[:2] in (('deliverables', 'history'), ('deliverables', 'runs')):
                continue  # Other immutable runs/archives remain at their original locations.
            known.add(str(resolved))
            result.append({'source_path': str(relative), 'relative_path': str(Path('supplemental-inputs') / relative),
                           'sha256': digest(path.read_bytes()), 'size': path.stat().st_size})
    return sorted(result, key=lambda item: item['source_path'])


def archive(previous, new_run_id):
    files = inventory(previous['directory'], previous['legacy'])
    files += referenced_inputs(previous['directory'], files)
    key = previous.get('archive_key', previous['run_id'])
    destination = Path('deliverables/history') / key
    manifest_path = destination / 'preservation.json'
    if manifest_path.exists():
        old = validate_archive(manifest_path)
        if [(r['source_path'], r['sha256']) for r in old['files']] == [(r['source_path'], r['sha256']) for r in files]:
            return {'path': str(manifest_path), 'sha256': digest(manifest_path.read_bytes()), 'run_id': previous['run_id']}
        # Retain later observations of changed/damaged originals without replacing the first copy.
        destination = destination / 'occurrences' / new_run_id
        manifest_path = destination / 'preservation.json'
    elif destination.exists():
        # Interrupted archive occurrence is evidence, too.
        destination = destination / 'occurrences' / new_run_id
        manifest_path = destination / 'preservation.json'
    destination.mkdir(parents=True, exist_ok=False)
    for item in files:
        target = destination / item['relative_path']
        if copy_bytes(Path(item['source_path']), target) != item['sha256']:
            raise ValueError('Source changed during history preservation')
        item['archived_path'] = str(target)
    manifest = {'run_id': previous['run_id'], 'preserved_for_run_id': new_run_id, 'recorded_at': now(),
                'files': files, 'pre_existing_issues': prior_issues(previous['directory']),
                'limits': 'Only available bytes are preserved. Missing/corrupt references are not reconstructed; original approval and request versions are unchanged.'}
    write(manifest_path, manifest)
    validate_archive(manifest_path)
    return {'path': str(manifest_path), 'sha256': digest(manifest_path.read_bytes()), 'run_id': previous['run_id']}


def snapshot_inputs(run, config_path):
    """Freeze local inputs for historical reproducibility, with disclosed manual provenance."""
    config = read(config_path)
    required = ['Project_B_Learner_Assignment_Codex.md', 'README.md', 'snapshot.schema.json', config['interview'], str(operating.PROFILE)]
    if config.get('manual_policy_reference'):
        required.append(config['manual_policy_reference'])
    copies = {}
    for name in dict.fromkeys(required):
        original = Path(name)
        if original.is_absolute() or '..' in original.parts:
            raise ValueError('Local input paths must be repository-relative')
        target = run / 'inputs' / original
        copies[str(original)] = {'path': str(target), 'sha256': copy_bytes(original, target)}
    original_config = run / 'inputs/source-config.original.json'
    copies['runtime-source-config-original'] = {'path': str(original_config), 'sha256': copy_bytes(config_path, original_config)}
    config['interview'] = copies[config['interview']]['path']
    if config.get('manual_policy_reference'):
        config['manual_policy_reference'] = copies[config['manual_policy_reference']]['path']
    effective = run / 'inputs/source-config.runtime.json'
    write(effective, config)
    return copies, effective


def scope_for_run(run_id, reason, previous, retry, archives, copies):
    original_config = read(Path('deliverables/runs') / run_id / 'inputs/source-config.original.json')
    result = scope.build_scope(Path.cwd(), interview=original_config['interview'])
    result['run_id'] = run_id
    state = result['state']
    for record in state['evidence_records']:
        if record['sha256'] != copies[record['path']]['sha256']:
            raise ValueError('Local input changed while freezing the run; retry with a new run ID')
        record['original_path'] = record['path']
        record['path'] = copies[record['path']]['path']
    profile_record = {'id': 'e-analysis-profile', 'summary': 'Reviewed interpretation configuration; not fresh company evidence or approval.',
                      'evidence_ids': [], **copies[str(operating.PROFILE)]}
    state['evidence_records'].append(profile_record)
    result['produced_record_ids'].append(profile_record['id'])
    state['analysis_profile'] = profile_record
    state['frozen_inputs'] = copies
    state.update({'supersedes_run_id': retry or (previous['run_id'] if previous else None),
                  'previous_completed_run_id': previous['run_id'] if previous and previous.get('completed') else None,
                  'retry_of_run_id': retry, 'change_retry_reason': reason,
                  'path_convention': 'repository-relative', 'history_preservation': archives})
    record = {'id': 'e-run-history', 'summary': 'Actual prior run preservation and operator-provided change/retry reason.',
              'evidence_ids': [], 'new_run_id': run_id, 'supersedes_run_id': state['supersedes_run_id'],
              'retry_of_run_id': retry, 'reason': reason, 'archives': archives}
    state['run_history_evidence'] = [record]
    decision = {'id': 'd-workflow-recompute', 'summary': 'Recompute all seven stages from a fresh capture in a new immutable run directory.',
                'evidence_ids': ['e-run-history'], 'concern': 'Preserve previous evidence and approvals through reruns and failed attempts.',
                'options': ['Create isolated run and preserve history', 'Reuse prior capture or replace previous draft files'],
                'chosen_behavior': 'Fresh capture, immutable run inputs, complete downstream recomputation; no approval carry-over.',
                'rationale': reason, 'tradeoffs': ['A failed attempt consumes storage but preserves diagnostics and the previous review package.'],
                'downstream_effect': 'New request bindings apply only to new draft bytes; prior decisions remain attached to prior versions.'}
    result['produced_record_ids'] += [record['id'], decision['id']]
    result['decisions'].append(decision)
    validate(result, Path.cwd())
    return result


def verify_run(directory, root=ROOT):
    """Inspect all actual stages/evidence/drafts, not a cached completion flag."""
    result = publication.verify_bundle(directory, root=root)
    chain = []
    current = result
    upstream = set()
    while True:
        validate(current, root)
        chain.append(current)
        if current['predecessor'] is None:
            break
        parent = current['predecessor']
        raw = Path(parent['path']).read_bytes()
        if digest(raw) != parent['sha256']:
            raise ValueError('Snapshot chain hash mismatch')
        previous = json.loads(raw)
        if previous['snapshot_id'] != parent['snapshot_id'] or previous['sequence'] != current['sequence'] - 1:
            raise ValueError('Snapshot chain identity/order mismatch')
        current = previous
    if len(chain) != 7 or len({s['run_id'] for s in chain}) != 1:
        raise ValueError('Seven stages with one run ID required')
    for stage in reversed(chain):
        produced = set(stage['produced_record_ids'])
        present = {r['id'] for r in walk(stage) if isinstance(r.get('id'), str)}
        if not produced <= present or not set(stage['consumed_record_ids']) <= upstream:
            raise ValueError('Snapshot record linkage mismatch')
        for record in walk(stage):
            if 'evidence_ids' in record and not set(record['evidence_ids']) <= upstream | produced:
                raise ValueError('Dangling evidence reference')
        upstream |= produced
    one = next(s for s in chain if s['sequence'] == 1)
    for item in one['state'].get('frozen_inputs', {}).values():
        if digest(Path(item['path']).read_bytes()) != item['sha256']:
            raise ValueError('Frozen input hash mismatch')
    for item in one['state'].get('history_preservation', []):
        if digest(Path(item['path']).read_bytes()) != item['sha256']:
            raise ValueError('History preservation manifest hash mismatch')
        validate_archive(Path(item['path']))
    two = next(s for s in chain if s['sequence'] == 2)
    config = two['state']['configuration']
    if digest(Path(config['path']).read_bytes()) != config['sha256']:
        raise ValueError('Runtime configuration hash mismatch')
    if {r['source_name'] for r in two['state']['sources']} != capture.NAMES:
        raise ValueError('Missing required source attempt')
    for source in two['state']['sources']:
        if source['local_reference']:
            if digest(Path(source['local_reference']).read_bytes()) != source['content_hash']:
                raise ValueError('Raw source hash mismatch')
        elif source['content_hash'] is not None:
            raise ValueError('Hash without captured bytes')
    return result


def execute(reason, root=ROOT, config_path=CONFIG, retry_run=None, transport=None):
    """Only tests inject transport; the operator CLI always uses fresh live retrieval."""
    if not reason or not reason.strip():
        raise ValueError('An explicit change/retry reason is required')
    root = root.resolve()
    with workspace(root), locked():
        previous = discover_previous()
        run_id = 'run-' + str(uuid4())
        run = Path('deliverables/runs') / run_id
        run.mkdir(parents=True, exist_ok=False)
        started = {'run_id': run_id, 'started_at': now(), 'reason': reason, 'retry_of_run_id': retry_run,
                   'previous_run_id': previous['run_id'] if previous else None,
                   'retrieval_mode': 'live-network' if transport is None else 'controlled-test-transport',
                   'path_convention': 'repository-relative'}
        write(run / 'started.json', started)
        stage, completed, archives = 'preservation', [], []
        event_number = 0
        def mark(name):
            nonlocal event_number
            event_number += 1
            write(run / 'events' / f'{event_number:02}.json',
                  {'run_id': run_id, 'stage': name, 'started_at': now(), 'completed_stages': list(completed)})
        try:
            mark(stage)
            if retry_run:
                if not re.fullmatch(r'run-[A-Za-z0-9-]+', retry_run):
                    raise ValueError('Invalid retry run ID')
                retry_dir = Path('deliverables/runs') / retry_run
                retry_start = read(retry_dir / 'started.json')
                try:
                    retry_outcome = read(retry_dir / 'result.json').get('outcome')
                except (OSError, ValueError, TypeError):
                    retry_outcome = None  # Preserve damaged metadata rather than treating it as approval/completion.
                if retry_outcome == 'completed':
                    raise ValueError('Completed runs require a new run reason, not --retry-run')
                if retry_start['run_id'] != retry_run:
                    raise ValueError('Retry identity mismatch')
                archives.append(archive({'run_id': retry_run, 'directory': retry_dir, 'legacy': False}, run_id))
            if previous:
                archives.append(archive(previous, run_id))
            stage = 'inputs'
            mark(stage)
            copies, effective = snapshot_inputs(run, Path(config_path))
            stage = NAMES[0]
            mark(stage)
            first = scope_for_run(run_id, reason, previous, retry_run, archives, copies)
            paths = [run / 'snapshots' / name for name in NAMES]
            write(paths[0], first)
            completed.append(stage)
            stage = NAMES[1]
            mark(stage)
            kwargs = {} if transport is None else {'transport': transport}
            capture.capture(paths[0], effective, run / 'sources', root=root, output_path=paths[1], **kwargs)
            completed.append(stage)
            for index, builder in enumerate((authority.build, reconcile.build, impact.build, actions.build), 2):
                stage = NAMES[index]
                mark(stage)
                snapshot = builder(paths[index - 1], root=root)
                write(paths[index], snapshot)
                completed.append(stage)
            stage = NAMES[6]
            mark(stage)
            publication.generate(paths[5], run, root=root)
            completed.append(stage)
            stage = 'final-integrity-validation'
            mark(stage)
            final = verify_run(run, root)
            status = {'run_id': run_id, 'outcome': 'completed', 'finished_at': now(),
                      'publication_status': final['state']['publication_status'], 'approval_status': 'pending',
                      'draft_validation_status': 'passed', 'stage07_path': str(paths[6]),
                      'stage07_sha256': digest(paths[6].read_bytes()), 'completed_stages': completed,
                      'history_preservation': archives, 'retry_of_run_id': retry_run,
                      'supersedes_run_id': first['state']['supersedes_run_id'], 'reason': reason,
                      'files': inventory(run)}
            write(run / 'result.json', status)
            return status
        except BaseException as error:
            # Preserve partial captures/stages. Do not erase, resume or claim the old package is new.
            diagnostic = {'run_id': run_id, 'outcome': 'failed', 'finished_at': now(), 'failed_stage': stage,
                          'error_type': type(error).__name__, 'reason': reason, 'completed_stages': completed,
                          'affected_output': str(run / 'snapshots' / stage) if stage in NAMES else str(run),
                          'previous_run_id': previous['run_id'] if previous else None, 'retry_of_run_id': retry_run,
                          'history_preservation': archives, 'files': inventory(run),
                          'diagnostic': str(error)[:1500] if isinstance(error, (ValueError, FileNotFoundError)) else 'Inspect retained stage/attempt records; unexpected failure details are not copied to avoid credential leakage.',
                          'validation_path': list(getattr(error, 'absolute_path', [])),
                          'next_owner': 'Operator / source owner; Legal for changed legal or operating meanings',
                          'recovery_action': 'Repair the reported cause, then run the workflow with --retry-run ' + run_id + ' --reason describing the repair. All required sources will be attempted afresh.'}
            write(run / 'result.json', diagnostic)
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reason', help='Required explanation for a new run or retry')
    parser.add_argument('--retry-run', help='Actual failed/interrupted run ID to retain and supersede')
    parser.add_argument('--config', type=Path, default=CONFIG)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--validate-run', type=Path, help='Read-only validation; no capture or new run')
    args = parser.parse_args()
    if args.validate_run:
        selected_root = args.root.resolve()
        with workspace(selected_root):
            snapshot = verify_run(args.validate_run, selected_root)
        print('Actual seven-stage package verified; publication ' + snapshot['state']['publication_status'])
        return
    if not args.reason:
        parser.error('--reason is required for a fresh run or retry')
    result = execute(args.reason, args.root, args.config, args.retry_run)
    print(f"New run {result['run_id']} completed local DRAFT validation; publication {result['publication_status']}. "
          f"Files: deliverables/runs/{result['run_id']}/. Requests remain pending and unsent.")


if __name__ == '__main__':
    main()
