"""Synthetic checks for conservative actor evidence and explicit event splits."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'backend'))
from app.services.event_index import build_event_index, comparison_tokens, identity, signature, similarity, split_reviewed_event
from app.services.event_evidence import build_summary_context
from correct_event import correct

NOW = '2026-10-01T12:00:00Z'
SUMMARY = 'Riley Morgan survived the Lakeside execution attempt and was taken to hospital.'


def article(number, title='Lakeside inmate Riley Morgan survives execution attempt', summary=SUMMARY):
    return {'url': f'https://example.org/correction/{number}', 'title': title, 'summary': summary,
        'published_at': NOW, 'language': 'en', 'source': {'name': 'Synthetic', 'publisher': 'Synthetic'}}


class ActorEvidenceTests(unittest.TestCase):
    def score(self, left, right):
        context = build_summary_context([left, right], comparison_tokens)
        return similarity(signature(left['title'], left['language'], left['published_at']),
            signature(right['title'], right['language'], right['published_at']), contexts=context)

    def test_same_named_actor_and_execution_action(self):
        self.assertGreaterEqual(self.score(article(1), article(2, 'Riley Morgan in hospital after surviving lethal injections')), .82)

    def test_archival_trial_is_not_current_execution(self):
        self.assertLess(self.score(article(1), article(2, 'Riley Morgan seen during murder trial')), .82)

    def test_opposing_survival_outcomes_are_not_merged(self):
        self.assertEqual(self.score(article(1), article(2, 'Lakeside inmate Riley Morgan died during execution attempt')), 0)

    def test_different_actor_is_not_shared_background(self):
        self.assertEqual(self.score(article(1), article(2, 'Lakeside inmate Jamie Parker survives execution attempt')), 0)

    def test_generic_live_update_heading_is_not_an_event(self):
        index, _ = build_event_index([article(1, "Here's the latest."), article(2, "Here's the latest.")], NOW)
        self.assertEqual(len(index['events']), 2)

    def test_collided_summary_does_not_enable_fallback(self):
        first = article(1)
        other = article(3, first['title'], 'A different summary contradicts this anchor.')
        right = article(2, 'Riley Morgan in hospital after surviving lethal injections')
        context = build_summary_context([first, other, right], comparison_tokens)
        self.assertLess(similarity(signature(first['title'], 'en', NOW), signature(right['title'], 'en', NOW), contexts=context), .82)


class SplitTests(unittest.TestCase):
    def setUp(self):
        self.articles = [article(i) for i in range(1, 4)]
        _, self.state = build_event_index(self.articles, NOW)
        self.event = next(iter(self.state['events']))
        self.groups = [[self.articles[0]['article_id']], [row['article_id'] for row in self.articles[1:]]]
        self.evidence = {'label_origin': 'ai', 'reference': 'synthetic reviewed split'}

    def split(self, groups=None, articles=None, evidence=None):
        return split_reviewed_event(self.state, self.event, groups if groups is not None else self.groups,
            articles if articles is not None else self.articles, NOW, evidence if evidence is not None else self.evidence)

    def test_split_preserves_old_id_without_mutating_input(self):
        before = deepcopy(self.state)
        result = self.split()
        self.assertEqual(self.state, before)
        self.assertEqual(len(result['events']), 2)
        self.assertEqual(result['articles'][self.groups[0][0]]['event_id'], self.event)
        self.assertNotEqual(result['articles'][self.groups[1][0]]['event_id'], self.event)
        self.assertEqual(result['events'][self.event]['split_review']['label_origin'], 'ai')

    def test_roundtrip_and_later_collection_preserve_correction(self):
        import json
        result = json.loads(json.dumps(self.split()))
        index, result = build_event_index(deepcopy(self.articles), NOW, result)
        self.assertEqual(len(index['events']), 2)
        self.assertEqual(result['articles'][self.groups[0][0]]['event_id'], self.event)

    def test_child_identity_is_order_independent(self):
        a = self.split()
        b = self.split([self.groups[0], list(reversed(self.groups[1]))])
        self.assertEqual(set(a['events']), set(b['events']))

    def test_old_alias_still_resolves_to_retained_group(self):
        old = 'e_' + 'f' * 24
        self.state['aliases'][old] = self.event
        self.assertEqual(self.split()['aliases'][old], self.event)

    def test_missing_duplicate_and_foreign_members_are_rejected(self):
        for groups in [[self.groups[0], [self.groups[1][0]]], [self.groups[0], self.groups[1] + self.groups[0]], [self.groups[0], self.groups[1] + ['a_' + 'f' * 24]]]:
            with self.assertRaises(ValueError):
                self.split(groups)

    def test_missing_history_and_fake_origin_are_rejected(self):
        with self.assertRaises(ValueError):
            self.split(articles=self.articles[:2])
        with self.assertRaises(ValueError):
            self.split(evidence={'label_origin': 'unreviewed', 'reference': 'fake'})

    def test_incompatible_child_group_is_rejected(self):
        changed = deepcopy(self.articles)
        changed[2]['title'] = 'Lakeside appoints Jamie Parker project director'
        with self.assertRaises(ValueError):
            self.split(articles=changed)

    def test_cli_core_rejects_cross_generation_request(self):
        snapshot = {'snapshot_id': 'a' * 24, 'content_sha256': 'b' * 64, 'articles': self.articles}
        self.state['snapshot_id'] = snapshot['snapshot_id']
        request = dict(self.evidence, snapshot_id='c' * 24, content_sha256=snapshot['content_sha256'], event_id=self.event, groups=self.groups, reviewed_at=NOW)
        with self.assertRaises(ValueError):
            correct(self.state, snapshot, request)

    def test_cli_core_retains_unpublished_evidence(self):
        snapshot = {'snapshot_id': 'a' * 24, 'content_sha256': 'b' * 64, 'articles': self.articles}
        self.state['snapshot_id'] = snapshot['snapshot_id']
        request = dict(self.evidence, snapshot_id=snapshot['snapshot_id'], content_sha256=snapshot['content_sha256'], event_id=self.event, groups=self.groups, reviewed_at=NOW)
        _, audit = correct(self.state, snapshot, request)
        self.assertFalse(audit['published'])
        self.assertTrue(audit['requires_new_paired_snapshot'])


if __name__ == '__main__':
    unittest.main()
