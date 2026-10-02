"""Generate an isolated reviewed split candidate, never replace published data."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'backend'))
from app.services.event_index import split_reviewed_event, validate_registry


def bounded_json(path, limit):
    raw = path.read_bytes()
    if len(raw) > limit:
        raise ValueError('Correction input exceeds its size bound.')
    return json.loads(raw.decode('utf-8'))


def correct(state, snapshot, request):
    if not snapshot.get('snapshot_id') or request.get('snapshot_id') != snapshot['snapshot_id'] or request.get('content_sha256') != snapshot.get('content_sha256'):
        raise ValueError('Correction request must identify the exact evidence generation.')
    if state.get('snapshot_id') != snapshot['snapshot_id']:
        raise ValueError('Correction registry and evidence must belong to the same generation.')
    result = split_reviewed_event(state, request['event_id'], request['groups'], snapshot['articles'],
        request['reviewed_at'], {'label_origin': request['label_origin'], 'reference': request['reference']})
    return result, {'schema_version': 1, 'operation': 'reviewed-split',
        'snapshot_id': snapshot['snapshot_id'], 'content_sha256': snapshot['content_sha256'],
        'old_url_retained_for_first_group': request['event_id'],
        'label_origin': request['label_origin'], 'reference': request['reference'],
        'reviewed_at': request['reviewed_at'], 'new_event_ids': sorted(set(result['events']) - set(state['events'])),
        'published': False, 'requires_new_paired_snapshot': True, 'human_gate_pass': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output must be a new isolated directory; existing files are never replaced.')
    state = validate_registry(bounded_json(args.state, 4 * 1024 * 1024))
    snapshot = bounded_json(args.snapshot, 8 * 1024 * 1024)
    request = bounded_json(args.request, 64 * 1024)
    state, audit = correct(state, snapshot, request)
    args.output.mkdir(parents=True, exist_ok=False)
    for name, value in [('corrected-registry.json', state), ('correction-audit.json', audit)]:
        (args.output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(audit, ensure_ascii=False))
