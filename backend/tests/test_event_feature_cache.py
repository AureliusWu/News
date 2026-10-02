from app.services import event_evidence
from app.services.event_index import build_event_index, signature, similarity


def test_memo_is_bounded_and_projection_local(monkeypatch):
    monkeypatch.setattr(event_evidence, 'MAX_DERIVED_FEATURES', 2)
    one = event_evidence.SummaryContext({}, {}, 0)
    two = event_evidence.SummaryContext({}, {}, 0)
    calls = []
    for key in ('zero', 'zero', 'one', 'overflow', 'overflow'):
        event_evidence.cached(one, 'test', key, lambda: calls.append(key) or 0)
    assert calls == ['zero', 'one', 'overflow', 'overflow']
    assert len(one.derived) == 2
    assert not two.derived


def test_context_reuse_does_not_change_public_similarity():
    now = '2026-10-01T15:00:00Z'
    titles = ['Canadian court approves coastal wind project after review',
              'Coastal wind project gets approval from Canadian court',
              'Canadian court rejects coastal wind project after review',
              'Riley Morgan opens Cedar Arts Festival with surprise performance',
              'Jamie Parker opens Cedar Arts Festival with surprise performance',
              'Latest news bulletin September Morning']
    rows = [signature(title, 'en', now) for title in titles]
    context = event_evidence.SummaryContext({}, {}, 0)
    for left in rows:
        for right in rows:
            assert similarity(left, right, {}, context) == similarity(left, right)


def test_derived_features_never_enter_registry_or_articles():
    articles = [{'url': 'https://capacity.invalid/one', 'title': 'Canadian court approves coastal wind project after review',
                 'language': 'en', 'published_at': '2026-10-01T15:00:00Z',
                 'source': {'publisher': 'One', 'name': 'One'}}]
    _, state = build_event_index(articles, '2026-10-01T15:00:00Z')
    assert 'derived' not in state
    assert 'derived' not in articles[0]
