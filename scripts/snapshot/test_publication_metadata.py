"""Original article timestamps must not become generic updated-date fallbacks."""
import json
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch

import feedparser
import httpx

from collect import (MAX_PUBLICATION_LOOKUPS, fetch_source,
                     original_publication_from_html)

NOW = datetime(2026, 11, 1, 3, tzinfo=timezone.utc)
URL = 'https://publisher.example/story'


def html(item, canonical=URL):
    return (f'<link rel="canonical" href="{canonical}">'
            f'<script type="application/ld+json">{json.dumps(item)}</script>').encode()


def article(**overrides):
    return {'@type': 'NewsArticle', 'url': URL,
            'datePublished': '2026-11-01T01:00:00Z', **overrides}


class OriginalPublicationTests(unittest.TestCase):
    def test_uses_published_not_newer_modified(self):
        result = original_publication_from_html(html(article(dateModified='2026-11-01T02:00:00Z')), URL)
        self.assertEqual(result, NOW - timedelta(hours=2))

    def test_modified_alone_is_not_a_publication_date(self):
        value = article(dateModified='2026-11-01T02:00:00Z')
        value.pop('datePublished')
        self.assertIsNone(original_publication_from_html(html(value), URL))

    def test_date_or_timezone_cannot_be_invented(self):
        for value in ('2026-11-01', '2026-11-01T01:00:00', '2026-02-30T00:00:00Z', 123):
            with self.subTest(value=value):
                self.assertIsNone(original_publication_from_html(html(article(datePublished=value)), URL))

    def test_publisher_declared_midnight_is_preserved(self):
        self.assertEqual(original_publication_from_html(html(article(datePublished='2026-11-01T00:00:00Z')), URL),
                         NOW - timedelta(hours=3))

    def test_only_matching_article_and_canonical_are_accepted(self):
        self.assertIsNone(original_publication_from_html(html(article(url=URL + '-other')), URL))
        self.assertIsNone(original_publication_from_html(html(article(), URL + '-other'), URL))
        self.assertIsNone(original_publication_from_html(html(article(url=URL + '?id=another')), URL))

    def test_unicode_and_rss_campaign_match_without_losing_article_identity(self):
        url = 'https://publisher.example/über?maca=rss'
        value = article(url='https://publisher.example/%C3%BCber')
        self.assertIsNotNone(original_publication_from_html(html(value, value['url']), url))

    def test_conflicting_original_dates_are_rejected(self):
        self.assertIsNone(original_publication_from_html(html([article(), article(datePublished='2026-11-01T02:00:00Z')]), URL))

    def test_related_articles_do_not_supply_page_time(self):
        value = {'@type': 'WebPage', 'relatedLink': article()}
        self.assertIsNone(original_publication_from_html(html(value), URL))

    def test_primary_article_can_inherit_its_canonical_page_identity(self):
        value = article(); value.pop('url')
        self.assertIsNotNone(original_publication_from_html(html({'@type': 'WebPage', 'mainEntity': value}), URL))
        self.assertIsNone(original_publication_from_html(html(value), URL))
        self.assertIsNone(original_publication_from_html(html({'@type': 'WebPage', 'url': URL + '-other', 'mainEntity': value}), URL))

    def test_graph_and_malformed_types_do_not_break_other_article_records(self):
        value = {'@graph': [{'@type': {'invalid': True}}, article()]}
        self.assertIsNotNone(original_publication_from_html(html(value), URL))


class FeedMetadataTests(unittest.TestCase):
    def definition(self, **overrides):
        return {'id': 'publisher', 'name': 'Publisher', 'publisher': 'Publisher',
                'homepage': 'https://publisher.example', 'region': 'world', 'language': 'en',
                'category': 'world', 'source_type': 'official_rss', 'feed_url': 'https://publisher.example/feed',
                'publication_metadata': 'json_ld_date_published', **overrides}

    def run_source(self, feed, pages, definition=None):
        calls = []
        def handler(request):
            calls.append(str(request.url))
            if request.url.path == '/feed':
                return httpx.Response(200, content=feed)
            self.assertTrue(request.headers['accept'].startswith('text/html'))
            return pages(request)
        client = httpx.Client(transport=httpx.MockTransport(handler))
        with patch('collect.httpx.Client', return_value=client):
            result = fetch_source(definition or self.definition(), 1, NOW)
        return result, calls

    def feed(self, count=1, publication=''):
        items = ''.join(f'<item><title>Original news {i}</title><link>{URL}{i}</link>'
                        f'<dc:date>2026-11-01T02:30:00Z</dc:date>{publication}</item>' for i in range(count))
        return (f'<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/"><channel>{items}</channel></rss>').encode()

    def page(self, request, **overrides):
        url = str(request.url)
        return httpx.Response(200, content=html(article(url=url, **overrides), url))

    def test_missing_rss_publication_can_use_same_article_original_metadata(self):
        (source, articles, row), calls = self.run_source(self.feed(), self.page)
        self.assertEqual(row['health'], 'PASS')
        self.assertEqual(articles[0]['published_at'], '2026-11-01T01:00:00Z')
        self.assertEqual(row['publication_metadata']['accepted'], 1)
        self.assertEqual(len(calls), 2)

    def test_no_opt_in_keeps_original_missing_date_failure(self):
        (_, articles, row), calls = self.run_source(self.feed(), self.page, self.definition(publication_metadata=None))
        self.assertEqual(row['health'], 'FAIL'); self.assertEqual(articles, [])
        self.assertEqual(len(calls), 1)

    def test_requests_are_capped_and_invalid_metadata_stays_failed(self):
        (_, articles, row), calls = self.run_source(self.feed(20), lambda r: self.page(r, datePublished='2026-11-01'))
        self.assertEqual(row['health'], 'FAIL'); self.assertEqual(articles, [])
        self.assertEqual(row['publication_metadata']['lookups'], MAX_PUBLICATION_LOOKUPS)
        self.assertEqual(len(calls), MAX_PUBLICATION_LOOKUPS + 1)

    def test_budget_exhaustion_stops_new_article_requests(self):
        with patch('collect.PUBLICATION_LOOKUP_BUDGET', 0):
            (_, _, row), calls = self.run_source(self.feed(20), self.page)
        self.assertEqual(row['health'], 'FAIL'); self.assertEqual(len(calls), 1)

    def test_cross_host_links_and_redirects_are_not_followed(self):
        feed = self.feed().replace(b'publisher.example/story0', b'other.example/story0')
        (_, _, row), calls = self.run_source(feed, self.page)
        self.assertEqual(row['health'], 'FAIL'); self.assertEqual(len(calls), 1)
        for location in ('https://other.example/story', 'http://publisher.example/story', 'https://publisher.example:8443/story'):
            with self.subTest(location=location):
                (_, _, row), calls = self.run_source(self.feed(), lambda r: httpx.Response(302, headers={'Location': location}))
                self.assertEqual(row['health'], 'FAIL'); self.assertEqual(len(calls), 2)

    def test_old_or_future_original_dates_do_not_get_refreshed_from_page(self):
        for value in ('Fri, 01 Jan 2010 00:00:00 GMT', 'Sun, 01 Nov 2026 09:00:00 GMT'):
            with self.subTest(value=value):
                (_, _, row), calls = self.run_source(self.feed(publication=f'<pubDate>{value}</pubDate>'), self.page)
                self.assertEqual(row['health'], 'FAIL'); self.assertEqual(len(calls), 1)

    def test_old_or_future_html_publications_still_fail_freshness(self):
        for value in ('2010-01-01T00:00:00Z', '2026-11-01T09:00:00Z'):
            with self.subTest(value=value):
                (_, _, row), _ = self.run_source(self.feed(), lambda r: self.page(r, datePublished=value))
                self.assertEqual(row['health'], 'FAIL')


if __name__ == '__main__':
    unittest.main()
