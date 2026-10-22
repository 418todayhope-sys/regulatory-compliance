"""Export/verify an offline assessment view; never substitute for full raw validation."""
import argparse
import json
from pathlib import Path
import re

import actions
import authority
import capture
import impact
import portable
import publication
import reconcile
import registers
import scope
import workflow
from capture import digest

MANIFEST = 'public-evidence.json'
FORMAT = 'project-b-public-evidence/1'
METHOD = 'google-grid-claim-extract/1'
KEY_SHAPE = re.compile(rb'AIza[A-Za-z0-9_-]{35}')
LIMIT = ('Original HTML bytes unavailable in this public view: their recorded hashes are '
         'provenance commitments, not recomputed verification. Retained extracts are '
         'source-reported claims, not independent corroboration or approval. Hidden tabs '
         'and original response completeness cannot be established from these extracts.')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(path.read_bytes())


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False)
        handle.write('\n')


def inside(root, relative):
    path = Path(relative)
    require(not path.is_absolute() and '..' not in path.parts and str(path) != '.',
            'Expected normalized repository-relative file path')
    target = root / path
    require(not any(p.is_symlink() for p in [target, *target.parents] if p != root.parent),
            'Symlinks are not permitted in assessment files')
    require(target.resolve().is_relative_to(root), 'Assessment path escapes package')
    return target


def relative(original, prefix):
    path = Path(original)
    if path.is_absolute():
        try:
            path = path.relative_to(prefix)
        except ValueError:
            raise ValueError('Recorded reference outside original repository') from None
    require('..' not in path.parts, 'Unsafe recorded reference')
    return str(path)


def assessment_files(root):
    """Only the root Git administrative entry is outside the assessment inventory.

    Never traverse .git directories or follow worktree pointers. Assessment
    symlinks (including a symlink named .git) remain errors. Git history/hooks
    require a separate pre-publication audit; they are not source evidence.
    """
    def visit(directory):
        for path in directory.iterdir():
            require(not path.is_symlink(), 'Symlink in public package')
            if path == root / '.git':
                if path.is_file():
                    pointer = path.read_text(encoding='utf-8')
                    require(re.fullmatch(r'gitdir: [^\r\n]+\n?', pointer) is not None,
                            'Root .git file is not a worktree pointer')
                else:
                    require(path.is_dir(), 'Unsupported root Git metadata entry')
                continue
            require(path.name != '.git', 'Nested Git metadata is not assessment evidence')
            if path.is_dir():
                yield from visit(path)
            else:
                require(path.is_file(), 'Unsupported assessment file type')
                yield path
    yield from visit(root)


def omissions(root, prefix):
    """Derive allowed substitutions from original snapshot/ledger identities, not manifest assertions."""
    result = {}
    for snapshot_path in sorted((root / 'deliverables/snapshots').glob('02-*.json')):
        snapshot = read(snapshot_path)
        for source in snapshot['state']['sources']:
            if source['source_name'] not in registers.HEADERS or source.get('route_type') == 'csv-export':
                continue
            if not source['local_reference'] or 'html' not in source['content_type']:
                continue
            name = relative(source['local_reference'], prefix)
            # Only the 12 diagnosed original HTML reads qualify, never legal/CSV/manual evidence.
            require(name.endswith('.response') and source.get('requested_url', source['locator']) == source.get('original_url', source['locator']),
                    'Unapproved HTML substitution route')
            ledger = name[:-len('.response')] + '.attempt.json'
            require(read(inside(root, ledger)) == source, 'Attempt ledger/snapshot mismatch')
            require(name not in result, 'Repeated original capture identity')
            result[name] = {'snapshot': str(snapshot_path.relative_to(root)),
                            'snapshot_sha256': digest(snapshot_path.read_bytes()),
                            'attempt': ledger, 'attempt_sha256': digest(inside(root, ledger).read_bytes()),
                            'source': source}
    require(len(result) == 12, 'This export format requires the 12 diagnosed HTML responses')
    return result


def claim_extract(source, body):
    name = source['source_name']
    tables, discovered = registers.extract(name, body, source['content_type'],
                                          [{'gid': '0', 'name': registers.TABS[name]}])
    require(len(tables) == 1 and tables[0]['valid'], 'Expected one valid exposed register grid')
    require(discovered == [{'gid': '0', 'name': registers.TABS[name]}], 'Unverified exposed tab identity')
    return claim_envelope(source, tables, discovered)


def claim_envelope(source, tables, discovered):
    """Exact metadata contract shared by actual extraction and offline verification."""
    name = source['source_name']
    return {'format': METHOD, 'source_id': source['id'], 'source_name': name,
            'original_url': source.get('original_url', source['locator']), 'requested_url': source.get('requested_url'),
            'retrieval_url': source['final_url'], 'retrieved_at': source['retrieved_at'],
            'completed_at': source['completed_at'], 'retrieval_status': source['retrieval_status'],
            'original_sha256': source['content_hash'],
            'workbook_id': registers.workbook_id(source.get('original_url', source['locator'])),
            'discovered_tabs': discovered, 'tables': tables,
            'limitations': LIMIT, 'original_html_byte_verification': 'unavailable',
            'independently_corroborated': False, 'approval_verified': False}


def export(root, destination):
    root = Path(root).resolve()
    destination = Path(destination).absolute()
    require(not destination.exists(), 'Export destination must be absent')
    require(not root.is_relative_to(destination), 'Destination cannot contain the original repository')
    seven = read(root / 'deliverables/snapshots/07-publication-validation.json')
    prefix = Path(seven['predecessor']['path']).parents[2]
    # Export is not a new review run or retrieval. All original strict checks must pass first.
    portable.verify(root, prefix)
    omitted = omissions(root, prefix)
    destination.mkdir(parents=True, exist_ok=False)
    manifest = {'format': FORMAT, 'run_id': seven['run_id'], 'original_root': str(prefix),
                'export_kind': 'offline-view-of-existing-run', 'retrieval_performed': False,
                'original_html_byte_verification': 'unavailable', 'limitations': LIMIT,
                'omitted_originals': [], 'excluded_local_tests': [], 'files': []}
    paths = [root / p for p in ('README.md', 'snapshot.schema.json',
             'Project_B_Learner_Assignment_Codex.md', '.catalyte/challenge.json')]
    # Include the offline evaluator entry point when supplied; legacy inputs remain valid.
    if (root / 'EVALUATOR.md').is_file():
        paths.append(root / 'EVALUATOR.md')
    for name in ('interviews', 'references', 'deliverables', 'regulatory-change-impact-brief',
                 'review-evidence/portable-review'):
        paths += [p for p in (root / name).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    for path in sorted(paths):
        name = str(path.relative_to(root))
        if name in omitted:
            continue
        # Original tests require raw fixtures. Ship the public offline suite explicitly instead.
        if '/tests/' in name and path.name != 'test_public_evidence.py':
            manifest['excluded_local_tests'].append({'path':name, 'sha256':digest(path.read_bytes()),
                'reason':'Raw-fixture development suite retained locally; public offline suite is shipped instead.'})
            continue
        raw = inside(root, name).read_bytes()
        require(not KEY_SHAPE.search(raw), 'Unexpected key-shaped content outside approved omissions: ' + name)
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as handle:
            handle.write(raw)
    for name, basis in omitted.items():
        source = basis['source']
        raw = inside(root, name).read_bytes()
        require(digest(raw) == source['content_hash'] and KEY_SHAPE.search(raw),
                'Omitted original differs from preserved capture or lacks diagnosed browser configuration')
        extract = claim_extract(source, raw)
        target = 'deliverables/public-extracts/' + name.removeprefix('deliverables/sources/').replace('.response', '.claims.json')
        save(destination / target, extract)
        manifest['omitted_originals'].append({k: v for k, v in basis.items() if k != 'source'} | {
            'original_path': name, 'original_sha256': source['content_hash'], 'source_id': source['id'],
            'extract_path': target, 'extract_sha256': digest((destination / target).read_bytes()),
            'method': METHOD, 'original_html_byte_verification': 'unavailable'})
    for path in sorted(destination.rglob('*')):
        if path.is_file():
            manifest['files'].append({'path': str(path.relative_to(destination)),
                                      'sha256': digest(path.read_bytes()), 'size': path.stat().st_size})
    save(destination / MANIFEST, manifest)
    return verify(destination)


def verify(root, expected_manifest=None):
    """No network/passwords; explicit extract verification, never fallback from strict mode."""
    root = Path(root).resolve()
    raw_manifest = inside(root, MANIFEST).read_bytes()
    require(not KEY_SHAPE.search(raw_manifest), 'Key-shaped content in public manifest')
    if expected_manifest:
        require(digest(raw_manifest) == expected_manifest, 'Trusted manifest hash mismatch')
    manifest = json.loads(raw_manifest)
    require(manifest['format'] == FORMAT and manifest['export_kind'] == 'offline-view-of-existing-run'
            and manifest['retrieval_performed'] is False and manifest['limitations'] == LIMIT
            and manifest['original_html_byte_verification'] == 'unavailable', 'Invalid public assessment mode')
    prefix = Path(manifest['original_root'])
    require(prefix.is_absolute() and '..' not in prefix.parts, 'Invalid original-root mapping')
    expected_files = {r['path']: r for r in manifest['files']}
    require(len(expected_files) == len(manifest['files']), 'Duplicate public inventory paths')
    require(all('.git' not in Path(name).parts for name in expected_files),
            'Git metadata cannot be declared as assessment evidence')
    actual = {str(path.relative_to(root)) for path in assessment_files(root)}
    require(actual == set(expected_files) | {MANIFEST}, 'Public inventory missing or unexpected files')
    for name, item in expected_files.items():
        raw = inside(root, name).read_bytes()
        require(len(raw) == item['size'] and digest(raw) == item['sha256'], 'Public file hash/size mismatch: ' + name)
        require(not KEY_SHAPE.search(raw), 'Key-shaped content in public package: ' + name)
    allowed = omissions(root, prefix)
    entries = {e['original_path']: e for e in manifest['omitted_originals']}
    require(len(entries) == len(manifest['omitted_originals']) and set(entries) == set(allowed),
            'Missing, duplicate or unapproved original substitution')
    extracts = {}
    for name, basis in allowed.items():
        source = basis['source']; entry = entries[name]
        require(not (root / name).exists(), 'Omitted HTML unexpectedly present')
        for key in ('snapshot', 'snapshot_sha256', 'attempt', 'attempt_sha256'):
            require(entry[key] == basis[key], 'Substitution provenance mismatch: ' + key)
        require(entry['source_id'] == source['id'] and entry['original_sha256'] == source['content_hash']
                and entry['method'] == METHOD and entry['original_html_byte_verification'] == 'unavailable',
                'Original capture identity/hash or method mismatch')
        data = inside(root, entry['extract_path']).read_bytes()
        require(digest(data) == entry['extract_sha256'], 'Extract hash mismatch')
        extract = json.loads(data)
        # Reconstruct the permitted structure from rows, validating headers, IDs and locators.
        table = extract['tables'][0]
        rows = [table['headers']] + [[r['values'].get(h, '') for h in table['headers']] for r in table['records']]
        verified = registers.table(source['source_name'], rows, '0', registers.TABS[source['source_name']])
        require(verified['valid'] and verified == table and len(extract['tables']) == 1,
                'Invalid extract rows, headers, IDs, locators or tab')
        require(extract == claim_envelope(source, [verified],
                [{'gid':'0', 'name':registers.TABS[source['source_name']]}]), 'Extract provenance/limitations changed')
        extracts[name] = extract

    with workflow.workspace(root), portable.relocated_paths(root, prefix) as logical:
        chain = {}; paths = {}; raw_by_stage = {}
        path = logical(prefix / 'deliverables/snapshots/07-publication-validation.json')
        while True:
            raw = path.read_bytes(); stage = json.loads(raw); scope.validate(stage, logical(prefix))
            seq = stage['sequence']; require(seq not in chain, 'Cycle in snapshot chain')
            chain[seq], paths[seq], raw_by_stage[seq] = stage, path, raw
            parent = stage['predecessor']
            if parent is None: break
            path = logical(parent['path']); parent_raw = path.read_bytes(); previous = json.loads(parent_raw)
            require(digest(parent_raw) == parent['sha256'] and previous['snapshot_id'] == parent['snapshot_id']
                    and previous['sequence'] == seq - 1, 'Predecessor hash/identity/order mismatch')
        require(set(chain) == set(range(1, 8)) and {s['run_id'] for s in chain.values()} == {manifest['run_id']},
                'Seven stages with the recorded common run ID required')
        upstream = set()
        for seq in range(1, 8):
            stage = chain[seq]; produced = set(stage['produced_record_ids'])
            present = {r['id'] for r in workflow.walk(stage) if isinstance(r.get('id'), str)}
            require(produced <= present and set(stage['consumed_record_ids']) <= upstream, 'Record linkage mismatch')
            for record in workflow.walk(stage):
                if 'evidence_ids' in record:
                    require(set(record['evidence_ids']) <= upstream | produced, 'Dangling evidence reference')
            upstream |= produced
        for path in (root / 'deliverables/snapshots').glob('*.json'):
            scope.validate(read(path), logical(prefix))
        for record in chain[1]['state']['evidence_records']:
            require(digest(logical(record['path']).read_bytes()) == record['sha256'], 'Scope input hash mismatch')
        unavailable_configs = []
        for snapshot_path in (root / 'deliverables/snapshots').glob('02-*.json'):
            snapshot = read(snapshot_path)
            config = snapshot['state']['configuration']
            routes, observed = capture.load_config(logical(config['path']), logical(prefix), chain[1])
            if snapshot['snapshot_id'] == chain[2]['snapshot_id']:
                require(config == observed, 'Selected capture configuration binding mismatch')
            elif config != observed:
                unavailable_configs.append(str(snapshot_path.relative_to(root)))
            urls = {name: url for name, url, role in routes}
            require({s['source_name'] for s in snapshot['state']['sources']} == capture.NAMES, 'Missing disclosed source attempt')
            folder = logical(next(s['local_reference'] for s in snapshot['state']['sources'] if s['local_reference'])).parent
            ledger_paths = inside(root, relative(str(folder), prefix)).glob('*.attempt.json')
            ledgers = [read(p) for p in ledger_paths]
            require(len(ledgers) == len(snapshot['state']['sources']) and
                    {s['id']: s for s in ledgers} == {s['id']: s for s in snapshot['state']['sources']},
                    'Retrieval attempt ledger differs from preserved snapshot')
            for source in snapshot['state']['sources']:
                require(source.get('original_url', source['locator']) == urls[source['source_name']], 'Source identity differs from interview')
                ref = source['local_reference']
                if ref and relative(ref, prefix) not in extracts:
                    require(digest(logical(ref).read_bytes()) == source['content_hash'], 'Retained source hash mismatch')
                elif not ref:
                    require(source['content_hash'] is None, 'Hash without retained bytes')
        # Full legal text is retained: re-run the unmodified authority builder.
        rebuilt = authority.build(paths[2], logical(prefix))
        require(all(chain[3][k] == v for k, v in rebuilt.items() if k not in {'snapshot_id', 'created_at'}),
                'Authority/timing differ from retained legal sources')
        tables = chain[2]['state']['register_tables']
        for table in tables:
            stored = read(logical(table['extracted_reference']))
            require(digest(logical(table['extracted_reference']).read_bytes()) == table['extracted_sha256'] and
                    stored == {k:v for k,v in table.items() if k not in {'extracted_reference', 'extracted_sha256'}},
                    'Selected table extract binding mismatch')
            ref = relative(table['raw_reference'], prefix)
            source = next(s for s in chain[2]['state']['sources'] if s['id'] in table['evidence_ids'])
            require(table['raw_reference'] == source['local_reference'] and table['raw_sha256'] == source['content_hash'],
                    'Selected table/source identity mismatch')
            if ref in extracts:
                parsed = extracts[ref]['tables']
            else:
                raw = logical(table['raw_reference']).read_bytes()
                require(digest(raw) == table['raw_sha256'], 'CSV raw hash mismatch')
                parsed, _ = registers.extract(table['source_name'], raw, source['content_type'],
                                              [{'gid':table['gid'], 'name':table['tab_name']}])
            require(len(parsed) == 1 and all(parsed[0][k] == table[k] for k in
                    ('headers','records','record_ids','record_count','gid','tab_name','valid','errors')),
                    'Selected extract business records differ')
        checks = registers.validate_relationships(tables)
        require(checks['valid'] and checks == chain[2]['state']['register_validation'], 'Register join/agreement mismatch')
        # Historical extracts must agree with the retained case records, not just their own manifest.
        for extract in extracts.values():
            canonical = next(t for t in tables if t['source_name'] == extract['source_name'] and t['format'] == 'csv')
            require(all(extract['tables'][0][k] == canonical[k] for k in ('headers','records','record_ids','record_count')),
                    'Historical extract differs from diagnosed same-record captures; new export format/review required')
        early = {n:chain[n] for n in (3, 2, 1)}
        state4 = reconcile.assemble(early, tables, checks, logical(prefix))
        require(all(chain[4]['state'].get(k) == v for k,v in state4.items()), 'Reconciliation differs from extracts')
        state5 = impact.analyze(chain[4], chain[3])
        require(all(chain[5]['state'].get(k) == v for k,v in state5.items()), 'Findings differ from retained evidence')
        basis5 = {'snapshot_id':chain[5]['snapshot_id'], 'path':str(paths[5]), 'sha256':digest(raw_by_stage[5])}
        require(chain[6]['state'] == actions.assemble(chain[5], chain[4], early, basis5), 'Actions/requests mismatch')
        require(chain[5]['unresolved'] == chain[4]['unresolved'] + state5['unresolved_items'] + state5.get('review_blockers', [])
                and chain[6]['unresolved'] == chain[5]['unresolved'] + chain[6]['state']['escalations'], 'Unresolved findings changed')
        data = (chain[6], chain[5], chain[4], early, raw_by_stage[6], paths[6])
        blobs = {name:logical(prefix / 'deliverables' / name).read_bytes() for name in publication.FILES}
        expected = publication.make_snapshot(data, blobs, logical(prefix / 'deliverables'), logical(prefix))
        require(all(chain[7][k] == v for k,v in expected.items() if k not in {'snapshot_id','created_at'}),
                'Final draft bytes/hash bindings mismatch')
    return {'mode': FORMAT, 'run_id':manifest['run_id'], 'retained_evidence_validation':'passed',
            'original_html_byte_verification':'unavailable', 'omitted_original_count':len(entries),
            'publication_status':chain[7]['state']['publication_status'], 'retrieval_performed':False,
            'historical_configuration_bytes_unavailable': sorted(unavailable_configs),
            'manifest_sha256':digest(raw_manifest), 'limitations':LIMIT}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--export', type=Path, help='New standalone destination; original package is untouched')
    mode.add_argument('--validate', type=Path, help='Read-only public assessment root')
    parser.add_argument('--root', type=Path, default=scope.ROOT, help='Original local repository for export')
    parser.add_argument('--expected-manifest-sha256', help='Optional independently retained manifest digest')
    args = parser.parse_args()
    result = export(args.root, args.export) if args.export else verify(args.validate, args.expected_manifest_sha256)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
