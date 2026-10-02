"""Differential evidence against the saved pre-repair matcher, not new labels."""
import argparse
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
import types

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from app.services.event_index import build_event_index, identity
from replay_ai_review import scores


def district(number):
    value, result = number, ''
    while True:
        result = chr(97 + value % 26) + result
        value = value // 26 - 1
        if value < 0:
            return result


def fixture(count, dense=False, generated_at='2026-10-01T15:00:00+00:00'):
    now = datetime.fromisoformat(generated_at.replace('Z', '+00:00'))
    return [{'url': f'https://capacity.invalid/story/{i}',
             'title': ('Canadian court approves coastal wind project after review' if dense
                       else f'District {district(i)} opens community center for residents'),
             'summary': 'Local officials confirmed the opening and shared details with residents.',
             'language': 'en', 'published_at': (now - timedelta(hours=(i % 12) * .75, seconds=60 + i % 120)).isoformat(),
             'source': {'publisher': f'Capacity Publisher {i % 4}', 'name': f'Capacity Feed {i % 4}'}}
            for i in range(count)]


def reference(directory):
    package = types.ModuleType('capacity_reference')
    package.__path__ = [str(directory)]
    sys.modules[package.__name__] = package
    spec = importlib.util.spec_from_file_location(package.__name__ + '.event_index', directory / 'event_index.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run(builder, articles, generated_at, previous=None):
    supplied = deepcopy(articles)
    start = time.perf_counter()
    index, state = builder(supplied, generated_at, deepcopy(previous))
    return {'index': index, 'state': state, 'articles': supplied}, round(time.perf_counter() - start, 6)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    old = reference(out / 'reference')
    generated_at = '2026-10-01T15:00:00+00:00'
    cases = {'generic_256': fixture(256), 'dense_192': fixture(192, True)}
    adversarial = fixture(40)
    titles = ['Riley Morgan opens Cedar Arts Festival with surprise performance',
              'Jamie Parker opens Cedar Arts Festival with surprise performance',
              'Canada central bank raises interest rates after inflation reaches 3 percent',
              'Australia central bank raises interest rates after inflation reaches 3 percent',
              'Canadian court approves coastal wind project after first review',
              'Canadian court does not approve coastal wind project after first review',
              'Canadian court approves coastal wind project after second review',
              'Latest news bulletin September Morning',
              'Prison inmate survived lethal injection', 'Prison inmate was executed by lethal injection',
              '日本中央银行宣布调整利率', '日本中央银行宣布调整利率']
    for article, title in zip(adversarial, titles):
        article['title'] = title
    adversarial[11]['language'] = 'zh'
    adversarial[12]['published_at'] = '2026-09-28T00:00:00Z'
    cases['adversarial'] = adversarial
    report = {'checked_at': datetime.now(timezone.utc).isoformat(), 'synthetic_only_capacity': True,
              'differential': {}, 'formal_release': False}
    for name, articles in cases.items():
        before, before_time = run(old.build_event_index, articles, generated_at)
        after, after_time = run(build_event_index, articles, generated_at)
        assert before == after, f'{name}: output or article identities changed'
        retained_before, _ = run(old.build_event_index, articles[1:], generated_at, before['state'])
        retained_after, _ = run(build_event_index, articles[1:], generated_at, after['state'])
        assert retained_before == retained_after, f'{name}: retained identities changed'
        report['differential'][name] = {'exact_output_equal': True, 'retained_output_equal': True,
                                        'before_seconds': before_time, 'after_seconds': after_time}
        print(name, json.dumps(report['differential'][name]), flush=True)
    frozen = ROOT / 'artifacts/v1-m2-holdout-20261001'
    labels_path = frozen / 'review/ai-labels-unseen240.json'
    label_hash = hashlib.sha256(labels_path.read_bytes()).hexdigest()
    assert label_hash == '3245565e55f999ff2adc43646f3871633e3f2a370b0f6f47e547ea58a9045bc0'
    packet = json.loads((frozen / 'review/blind-unseen240-pairs.json').read_text(encoding='utf-8-sig'))
    labels = json.loads(labels_path.read_text(encoding='utf-8-sig'))
    snapshot = json.loads((frozen / 'data/news.json').read_text(encoding='utf-8-sig'))
    before, bt = run(old.build_event_index, snapshot['articles'], snapshot['generated_at'])
    after, at = run(build_event_index, snapshot['articles'], snapshot['generated_at'])
    assert before == after, 'Frozen real-news output changed'
    before_scores = scores(packet, labels, before['articles'])
    after_scores = scores(packet, labels, after['articles'])
    assert before_scores == after_scores, 'Frozen AI evaluation changed'
    report['frozen_ai_regression'] = {'labels_sha256': label_hash, 'labels_unchanged': True,
        'exact_output_equal': True, 'before_seconds': bt, 'after_seconds': at,
        'metrics': after_scores, 'evaluation_origin': 'ai', 'independent_gold': False,
        'untouched_holdout': False}
    for name, dense in [('generic_2000', False), ('dense_2000', True)]:
        result, duration = run(build_event_index, fixture(2000, dense), generated_at)
        assert len(result['articles']) == 2000
        events = result['index']['events']
        expected = {identity(article['url']) for article in result['articles']}
        members = [member for event in events for member in event['article_ids']]
        assert len(expected) == 2000 and len(members) == 2000
        assert len(set(members)) == len(members) and set(members) == expected
        assigned = {article['article_id']: article['event_id'] for article in result['articles']}
        assert all(event['article_count'] == len(event['article_ids']) and
                   all(assigned[member] == event['event_id'] for member in event['article_ids'])
                   for event in events)
        assert 1 <= len(events) <= 2000
        if dense:
            assert len(events) == 1
        report[name] = {'seconds': duration, 'articles': 2000, 'events': len(result['index']['events']),
                        'complete_unique_article_coverage': True,
                        'event_counts_and_assignments_consistent': True,
                        'under_previous_45_second_timeout': duration < 45}
        assert duration < 45, f'{name}: previous timeout boundary still exceeded'
        print(name, json.dumps(report[name]), flush=True)
    report['gate_pass'] = True
    (out / 'matcher-capacity-regression.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
