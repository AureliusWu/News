"""Frozen AI diagnostic replay and explicit, isolated reviewed-ID migration.

Never writes frontend/public or changes the original packet/registry. Fresh
grouping is measured separately from old-ID replay and reviewed migration.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
from itertools import combinations
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'backend'))
from app.services.event_evidence import build_summary_context
from app.services.event_index import comparison_tokens
from app.services.event_index import build_event_index, merge_reviewed_events, similarity, signature, THRESHOLD, MATCHER_VERSION


def scores(packet, labels, articles):
    expected = {row['pair_id']: row for row in packet['pairs']}
    incoming = labels['pairs']
    if labels.get('label_origin') != 'ai' or labels.get('snapshot_id') != packet['snapshot_id'] or labels.get('content_sha256') != packet['content_sha256']:
        raise ValueError('AI review origin or frozen generation differs.')
    if len(incoming) != len(expected) or {row['pair_id'] for row in incoming} != set(expected):
        raise ValueError('AI labels contain missing, foreign or duplicate pairs.')
    mapping = {row['article_id']: row['event_id'] for row in articles}
    counts = dict(tp=0, fp=0, fn=0, tn=0, unscored=0)
    errors = []
    for label in incoming:
        value = label['label']
        if value == 'uncertain': counts['unscored'] += 1; continue
        if value not in ('same', 'different'): raise ValueError('Invalid AI label.')
        pair = expected[label['pair_id']]
        predicted = mapping[pair['left']['article_id']] == mapping[pair['right']['article_id']]
        key = 'tp' if predicted and value == 'same' else 'fp' if predicted else 'fn' if value == 'same' else 'tn'
        counts[key] += 1
        if key in ('fp', 'fn'): errors.append({'pair_id':label['pair_id'], 'n':label.get('n'), 'kind':key})
    return {'counts':counts, 'precision':counts['tp']/(counts['tp']+counts['fp']) if counts['tp']+counts['fp'] else None,
            'recall':counts['tp']/(counts['tp']+counts['fn']) if counts['tp']+counts['fn'] else None, 'errors':errors}


def replay(snapshot, packet, labels, previous):
    contexts = build_summary_context(snapshot['articles'], comparison_tokens)
    if snapshot['snapshot_id'] != packet['snapshot_id'] or snapshot['content_sha256'] != packet['content_sha256']:
        raise ValueError('Replay must use the frozen reviewed snapshot.')
    baseline = scores(packet, labels, snapshot['articles'])
    fresh = deepcopy(snapshot['articles'])
    fresh_index, _ = build_event_index(fresh, snapshot['generated_at'])
    retained = deepcopy(snapshot['articles'])
    build_event_index(retained, snapshot['generated_at'], previous)
    fresh_map = {a['article_id']:a for a in fresh}
    original = {a['article_id']:a for a in snapshot['articles']}
    pairs = {p['pair_id']:p for p in packet['pairs']}
    # Only explicitly reviewed positive edges that also pass fresh grouping can
    # propose a migration; normal collection never uses labels to force merges.
    adjacency = {}
    for label in labels['pairs']:
        if label['label'] != 'same': continue
        pair = pairs[label['pair_id']]
        left, right = (side['article_id'] for side in (pair['left'], pair['right']))
        if fresh_map[left]['event_id'] != fresh_map[right]['event_id']: continue
        old_left, old_right = (previous['articles'][key]['event_id'] for key in (left, right))
        if old_left == old_right: continue
        adjacency.setdefault(old_left, set()).add(old_right)
        adjacency.setdefault(old_right, set()).add(old_left)
    state, migrations, skipped = deepcopy(previous), [], []
    visited = set()
    for root in sorted(adjacency):
        if root in visited: continue
        component, pending = set(), [root]
        while pending:
            current = pending.pop()
            if current in component: continue
            component.add(current); pending.extend(adjacency[current] - component)
        visited.update(component)
        group = [a for a in snapshot['articles'] if previous['articles'][a['article_id']]['event_id'] in component]
        signatures = [signature(a['title'], a['language'], a['published_at']) for a in group]
        if any(similarity(a,b, contexts=contexts) < THRESHOLD for a,b in combinations(signatures,2)):
            skipped.append({'event_ids':sorted(component), 'reason':'current members fail complete-link gate'}); continue
        try:
            state = merge_reviewed_events(state, component, labels['reviewed_at'], {'label_origin':'ai', 'reference':'frozen AI review '+packet['snapshot_id']}, contexts=contexts)
        except ValueError as error:
            skipped.append({'event_ids':sorted(component), 'reason':str(error)}); continue
        migrations.append({'survivor':min(component), 'retired_ids':sorted(component - {min(component)}), 'label_origin':'ai'})
    reviewed = deepcopy(snapshot['articles'])
    reviewed_index, state = build_event_index(reviewed, snapshot['generated_at'], state)
    result = {'schema_version':1, 'snapshot_id':packet['snapshot_id'], 'matcher_version':MATCHER_VERSION,
              'label_origin':'ai', 'independent_gold_standard':False, 'human_gate_pass':False,
              'evaluated_at':datetime.now(timezone.utc).isoformat(), 'baseline':baseline,
              'fresh_grouping':scores(packet,labels,fresh), 'retained_ids_no_migration':scores(packet,labels,retained),
              'reviewed_isolated_migration':scores(packet,labels,reviewed), 'migrations':migrations, 'skipped':skipped,
              'fresh_event_count':len(fresh_index['events']), 'reviewed_event_count':len(reviewed_index['events']),
              'limitation':'Development sample already inspected; not independent validation. Migration result uses reviewed positive edges and is not held-out quality evidence.'}
    return result, reviewed, reviewed_index, state


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--snapshot', type=Path, default=Path('frontend/public/data/news.json'))
    parser.add_argument('--packet', type=Path, default=Path('artifacts/v1-m2/review/pairs.json'))
    parser.add_argument('--labels', type=Path, default=Path('artifacts/v1-m2/review/ai-labels.json'))
    parser.add_argument('--state', type=Path, default=Path('artifacts/v1-m2/event-registry.json'))
    parser.add_argument('--output', type=Path, default=Path('artifacts/v1-m2-recall'))
    args = parser.parse_args()
    snapshot, packet, labels, previous = (json.loads(path.read_text(encoding='utf-8')) for path in (args.snapshot,args.packet,args.labels,args.state))
    result, articles, index, state = replay(snapshot,packet,labels,previous)
    args.output.mkdir(parents=True, exist_ok=True)
    for name, value in [('evaluation.json',result),('reviewed-registry.json',state),('reviewed-events.json',index)]:
        (args.output/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    candidate = deepcopy(snapshot); candidate['articles'] = articles
    digest = hashlib.sha256(json.dumps({'articles':articles,'sources':candidate['sources']},sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    generation = hashlib.sha256((candidate['generated_at']+digest).encode()).hexdigest()[:24]
    candidate.update(content_sha256=digest,snapshot_id=generation,events_file=f'events.{generation}.json',source_health_file=f'source-health.{generation}.json')
    candidate['meta']['evaluation_replay'] = True
    index.update(snapshot_id=generation,content_sha256=digest); state['snapshot_id'] = generation
    health = json.loads((args.snapshot.parent / snapshot['source_health_file']).read_text(encoding='utf-8'))
    health['snapshot_id'] = generation
    data = args.output/'candidate-data'; data.mkdir(exist_ok=True)
    for name,value in [('news.json',candidate),(f'news.{generation}.json',candidate),(candidate['events_file'],index),
                       (candidate['source_health_file'],health),('source-health.json',health),('event-registry.json',state),
                       ('generations.json',{'schema_version':1,'generations':[generation]})]:
        (data/name).write_text(json.dumps(value,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print(json.dumps({key:value for key,value in result.items() if key not in ('migrations','skipped')},ensure_ascii=False,indent=2))
