import unittest
from datetime import datetime, timedelta, timezone

from collect import build_snapshot, normalize, plain_text, public_source, safe_url

NOW = datetime(2026, 9, 21, 6, tzinfo=timezone.utc)


class SnapshotTests(unittest.TestCase):
    def source(self, index=0):
        return public_source({'id': f'source-{index}', 'name': f'Source {index}', 'publisher': f'Publisher {index}',
                              'region': f'region-{index % 7}', 'language': ['en', 'ja'][index % 2],
                              'category': 'world', 'type': 'official_rss', 'feed_url': 'https://example.org/rss'}, index + 1)

    def entry(self, **values):
        return {'title': 'A real title', 'link': 'https://example.org/story?utm_source=rss',
                'summary': '<p>Safe <b>summary</b></p><script>bad()</script>',
                'published_parsed': (NOW - timedelta(minutes=10)).utctimetuple(), **values}

    def test_tracking_and_fragment_removed(self):
        self.assertEqual(safe_url('https://EXAMPLE.org/story?utm_source=rss&keep=1#x'), 'https://example.org/story?keep=1')

    def test_unsafe_urls_rejected(self):
        for url in ('javascript:alert(1)', 'file:///x', 'http://127.0.0.1/a', 'http://169.254.169.254/', 'https://user:secret@example.org/a'):
            self.assertIsNone(safe_url(url))

    def test_html_becomes_bounded_text(self):
        self.assertEqual(plain_text('<script>secret()</script><b>A &amp; B</b>', 10), 'A & B')
        self.assertEqual(len(plain_text('x' * 400, 280)), 280)

    def test_normalizes_public_contract(self):
        article = normalize(self.entry(), self.source(), 'https://example.org/rss', NOW)
        self.assertEqual(article['summary'], 'Safe summary')
        self.assertEqual(article['url'], 'https://example.org/story')
        self.assertLess(article['id'], 2 ** 53)
        self.assertNotIn('miniflux_entry_id', article)

    def test_missing_publication_not_replaced_with_now(self):
        self.assertIsNone(normalize(self.entry(published_parsed=None, updated_parsed=NOW.utctimetuple()), self.source(), '', NOW))

    def test_old_and_future_entries_rejected(self):
        for date in (NOW - timedelta(days=8), NOW + timedelta(hours=2)):
            self.assertIsNone(normalize(self.entry(published_parsed=date.utctimetuple()), self.source(), '', NOW))

    def test_missing_url_rejected(self):
        self.assertIsNone(normalize(self.entry(link=''), self.source(), 'https://example.org/rss', NOW))

    def test_image_requires_safe_https(self):
        article = normalize(self.entry(media_thumbnail=[{'url': 'javascript:bad()'}, {'url': 'https://example.org/image.jpg'}]), self.source(), '', NOW)
        self.assertEqual(article['image_url'], 'https://example.org/image.jpg')

    def test_coverage_and_freshness_gate(self):
        results = []
        for index in range(25):
            source = self.source(index); source['health_status'] = 'ok'
            articles = [normalize(self.entry(link=f'https://example.org/{index}/{j}'), source, '', NOW) for j in range(4)]
            results.append((source, articles, {'health': 'PASS'}))
        snapshot, report = build_snapshot(results, NOW)
        self.assertTrue(report['summary']['gate_pass'])
        self.assertEqual(snapshot['meta']['article_count'], 100)
        self.assertFalse(build_snapshot(results[:5], NOW)[1]['summary']['gate_pass'])
        self.assertFalse(build_snapshot(results, NOW + timedelta(hours=7))[1]['summary']['gate_pass'])

    def test_canonical_deduplication(self):
        source = self.source(); source['health_status'] = 'ok'
        articles = [normalize(self.entry(link=url), source, '', NOW) for url in
                    ('https://example.org/a?utm_source=one', 'https://example.org/a?utm_source=two')]
        self.assertEqual(len(build_snapshot([(source, articles, {'health': 'PASS'})], NOW)[0]['articles']), 1)

    def test_source_attribution_required(self):
        with self.assertRaises(ValueError):
            public_source({'id': 'missing'}, 1)


if __name__ == '__main__':
    unittest.main()
