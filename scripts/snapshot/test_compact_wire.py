import unittest
from compact_wire import compact_snapshot, home_preview


class CompactWireTests(unittest.TestCase):
    def test_home_subset_keeps_full_generation_total_and_original_order(self):
        source = {'slug': 'one'}
        snapshot = {'sources': [source], 'articles': [{'id': i, 'source': source} for i in range(35)],
                    'meta': {'article_count': 35}, 'content_sha256': 'original', 'generated_at': 'original-time'}
        wire = compact_snapshot(snapshot)
        preview = home_preview(wire)
        self.assertEqual(preview['total_articles'], 35)
        self.assertEqual([item['id'] for item in preview['snapshot']['articles']], list(range(30)))
        self.assertEqual(len(wire['snapshot']['articles']), 35)
        self.assertEqual(preview['snapshot']['content_sha256'], 'original')
        self.assertEqual(preview['snapshot']['generated_at'], 'original-time')
    def test_lossless_dictionary_with_original_metadata_and_zero_id(self):
        source = {'slug': 'one', 'enabled': False, 'publisher': 'Original'}
        snapshot = {'sources': [source], 'articles': [{'id': 0, 'summary': None, 'source': dict(source)}],
                    'generated_at': '2026-10-25T00:00:00Z', 'content_sha256': 'original'}
        wire = compact_snapshot(snapshot)
        self.assertEqual(wire['snapshot']['articles'], [{'id': 0, 'summary': None, 'source_index': 0}])
        self.assertEqual(wire['snapshot']['generated_at'], snapshot['generated_at'])
        self.assertEqual(wire['snapshot']['content_sha256'], 'original')
        self.assertIn('source', snapshot['articles'][0])

    def test_inconsistent_or_duplicate_sources_fail_closed(self):
        source = {'slug': 'one', 'publisher': 'Original'}
        for snapshot in ({'sources': [source, source], 'articles': []},
                         {'sources': [source], 'articles': [{'source': {**source, 'publisher': 'Other'}}]},
                         {'sources': [source], 'articles': [{'source': source, 'source_index': 0}]}):
            with self.assertRaises(ValueError):
                compact_snapshot(snapshot)
