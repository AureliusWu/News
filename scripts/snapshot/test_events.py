import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'backend'))
from app.services.event_index import build_event_index, identity, signature, similarity, validate_registry, merge_reviewed_events, MATCHER_VERSION

NOW = '2026-09-30T07:00:00Z'


def article(number, title='Japan central bank raises interest rates after inflation reaches 3 percent', publisher='One', language='en', date=NOW):
    return {'url': f'https://example.org/story/{number}', 'title': title, 'language': language,
            'published_at': date, 'source': {'publisher': publisher, 'name': publisher + ' Feed'}}


class EventTests(unittest.TestCase):
    def test_groups_equivalent_headlines_and_counts_publishers_not_feeds(self):
        articles = [article(1), article(2, publisher='One'), article(3, publisher='Two')]
        index, _ = build_event_index(articles, NOW)
        self.assertEqual(len(index['events']), 1)
        self.assertEqual(index['events'][0]['publisher_count'], 2)
        self.assertEqual(index['events'][0]['article_count'], 3)

    def test_stable_after_seed_disappears_and_new_article_arrives(self):
        articles = [article(1), article(2)]
        first, state = build_event_index(articles, NOW)
        second, _ = build_event_index([article(2), article(3)], NOW, state)
        self.assertEqual(first['events'][0]['event_id'], second['events'][0]['event_id'])

    def test_state_round_trip_not_process_cache(self):
        import json
        first, state = build_event_index([article(1), article(2)], NOW)
        restored = json.loads(json.dumps(state))
        second, _ = build_event_index([article(2)], NOW, restored)
        self.assertEqual(first['events'][0]['event_id'], second['events'][0]['event_id'])

    def test_opposite_actions_are_not_merged(self):
        index, _ = build_event_index([article(1), article(2, title=article(1)['title'].replace('raises', 'cuts'))], NOW)
        self.assertEqual(len(index['events']), 2)

    def test_different_numbers_are_not_merged(self):
        index, _ = build_event_index([article(1), article(2, title=article(1)['title'].replace('3 percent', '4 percent'))], NOW)
        self.assertEqual(len(index['events']), 2)

    def test_different_language_and_distant_dates_are_not_merged(self):
        old = (datetime.fromisoformat(NOW.replace('Z', '+00:00')) - timedelta(days=3)).isoformat()
        index, _ = build_event_index([article(1), article(2, language='ja'), article(3, date=old)], NOW)
        self.assertEqual(len(index['events']), 3)

    def test_complete_link_does_not_accept_a_bridge(self):
        a = signature('alpha bravo charlie delta echo foxtrot golf hotel india', 'en', NOW)
        b = signature('alpha bravo charlie delta echo foxtrot golf hotel juliet', 'en', NOW)
        c = signature('alpha bravo charlie delta echo foxtrot golf kilo juliet', 'en', NOW)
        self.assertGreaterEqual(similarity(a, b), .8)
        self.assertLess(similarity(a, c), .82)
        titles = [a['title'], b['title'], c['title']]
        index, _ = build_event_index([article(i, title=t) for i, t in enumerate(titles)], NOW)
        self.assertGreaterEqual(len(index['events']), 2)

    def test_corrupt_state_rejected_instead_of_reset(self):
        _, state = build_event_index([article(1)], NOW)
        bad = deepcopy(state); bad['method_version'] = 'other'
        with self.assertRaises(ValueError): validate_registry(bad)
        bad = deepcopy(state); bad['articles'][identity(article(1)['url'])]['event_id'] = 'unknown'
        with self.assertRaises(ValueError): validate_registry(bad)

    def test_inputs_state_not_mutated_and_registry_is_bounded(self):
        _, state = build_event_index([article(1)], NOW)
        saved = deepcopy(state)
        _, result = build_event_index([article(2)], NOW, state)
        self.assertEqual(state, saved)
        self.assertLessEqual(len(result['events']), 5000)
        self.assertLessEqual(len(result['articles']), 10000)

    def test_independent_synthetic_rewritten_headlines(self):
        left = 'Canadian court approves coastal wind project after review'
        right = 'Coastal wind project gets approval from Canadian court'
        index, _ = build_event_index([article(1, left), article(2, right)], NOW)
        self.assertEqual(len(index['events']), 1)
        self.assertEqual(index['matcher_version'], MATCHER_VERSION)

    def test_country_conflict_blocks_near_identical_headlines(self):
        left = 'Canada central bank raises interest rates after inflation reaches 3 percent'
        right = left.replace('Canada', 'Australia')
        self.assertEqual(similarity(signature(left, 'en', NOW), signature(right, 'en', NOW)), 0)

    def test_person_conflict_blocks_same_event_template(self):
        left = 'Riley Morgan opens Cedar Arts Festival with surprise performance'
        right = left.replace('Riley Morgan', 'Jamie Parker')
        self.assertEqual(similarity(signature(left, 'en', NOW), signature(right, 'en', NOW)), 0)

    def test_roundup_and_promotional_templates_are_not_events(self):
        for title in ['Latest news bulletin September Morning', 'Target Promo Codes October 2026', 'Can you solve it? Tower puzzle']:
            sig = signature(title, 'en', NOW)
            self.assertEqual(similarity(sig, sig), 0)

    def test_negation_and_ordinal_conflicts_are_preserved(self):
        title = 'Canadian court approves coastal wind project after first review'
        for other in [title.replace('approves', 'does not approve'), title.replace('first', 'second')]:
            self.assertEqual(similarity(signature(title, 'en', NOW), signature(other, 'en', NOW)), 0)

    def test_reviewed_migration_retains_old_urls_as_direct_aliases(self):
        _, first = build_event_index([article(1)], NOW)
        _, second = build_event_index([article(2)], NOW)
        first['events'].update(second['events']); first['articles'].update(second['articles'])
        original = deepcopy(first)
        merged = merge_reviewed_events(first, list(first['events']), NOW, {'label_origin':'ai', 'reference':'isolated-test'})
        self.assertEqual(first, original)
        self.assertEqual(len(merged['events']), 1)
        self.assertEqual(len(merged['aliases']), 1)
        index, _ = build_event_index([article(1), article(2)], NOW, merged)
        self.assertEqual(len(index['events']), 1)
        self.assertTrue(index['aliases'])

    def test_migration_cannot_force_conflicting_events_or_fake_evidence(self):
        _, first = build_event_index([article(1)], NOW)
        _, second = build_event_index([article(2, article(1)['title'].replace('raises', 'cuts'))], NOW)
        first['events'].update(second['events']); first['articles'].update(second['articles'])
        with self.assertRaises(ValueError):
            merge_reviewed_events(first, list(first['events']), NOW, {'label_origin':'ai', 'reference':'test'})
        with self.assertRaises(ValueError):
            merge_reviewed_events(first, list(first['events']), NOW, {'label_origin':'unreviewed', 'reference':'test'})

    def test_alias_chain_and_cycle_are_rejected(self):
        _, state = build_event_index([article(1)], NOW)
        old = 'e_' + 'a' * 24
        state['aliases'][old] = old
        with self.assertRaises(ValueError): validate_registry(state)


if __name__ == '__main__': unittest.main()
