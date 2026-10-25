"""Lossless source-dictionary wire encoding; the legacy snapshot remains available."""
import json


def compact_snapshot(snapshot):
    sources = snapshot['sources']
    lookup = {source['slug']: i for i, source in enumerate(sources)}
    if len(lookup) != len(sources):
        raise ValueError('Duplicate compact source identity.')
    articles = []
    for article in snapshot['articles']:
        source_index = lookup[article['source']['slug']]
        if article['source'] != sources[source_index] or 'source_index' in article:
            raise ValueError('Compact encoding must preserve every source field.')
        articles.append({**{key: value for key, value in article.items() if key != 'source'}, 'source_index': source_index})
    return {'wire_schema_version': 1, 'snapshot': {**snapshot, 'articles': articles}}


def home_preview(wire):
    return {**wire, 'view': 'home-preview-v1', 'total_articles': len(wire['snapshot']['articles']),
            'snapshot': {**wire['snapshot'], 'articles': wire['snapshot']['articles'][:30]}}


def write_compact(snapshot, path):
    wire = compact_snapshot(snapshot)
    path.write_text(json.dumps(wire, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    preview = home_preview(wire)
    path.with_name('news.home.json').write_text(json.dumps(preview, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
