"""Synthetic adversarial checks for source-summary event support."""

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'backend'))
from app.services.event_evidence import build_summary_context, context_key, evidence_action_conflict, summary_score
from app.services.event_index import build_event_index, comparison_tokens, signature, similarity, validate_registry

NOW = '2026-09-30T07:00:00Z'
SUMMARY = ('Cedar Bay authority approved the Willow wind project following an environmental review. '
           'The council confirmed the development decision and construction plans for the coastal site.')


def article(number, title, summary=SUMMARY, language='en', published_at=NOW):
    return {'url': f'https://example.org/evidence/{number}', 'title': title, 'summary': summary,
            'language': language, 'published_at': published_at,
            'source': {'id': f'test-source-{number}', 'name': f'Source {number}',
                       'publisher': f'Publisher {number}'}, 'region': 'test'}


class SummaryEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.left = article(1, 'Cedar Bay authority approves Willow wind project')
        self.right = article(2, 'Willow wind development moves ahead after Cedar Bay review')

    def score(self, left=None, right=None):
        left, right = left or self.left, right or self.right
        context = build_summary_context([left, right], comparison_tokens)
        a = signature(left['title'], left['language'], left['published_at'])
        b = signature(right['title'], right['language'], right['published_at'])
        return similarity(a, b, contexts=context)

    def test_summary_support_for_reworded_event(self):
        self.assertGreaterEqual(self.score(), 0.82)

    def test_missing_summary_abstains(self):
        context = build_summary_context([self.left, dict(self.right, summary=None)], comparison_tokens)
        a, b = comparison_tokens(self.left), comparison_tokens(self.right)
        self.assertEqual(summary_score(self.left, self.right, a, b, {}, context, comparison_tokens), 0)

    def test_collided_summary_is_not_borrowed(self):
        other = dict(self.left, summary='A separate report supplies a contradictory account of this project.')
        context = build_summary_context([self.left, other, self.right], comparison_tokens)
        self.assertNotIn(context_key(self.left), context.summaries)

    def test_original_numeric_guard_survives_shared_summary(self):
        a = dict(self.left, title=self.left['title'] + ' at 3 percent')
        b = dict(self.right, title=self.right['title'] + ' at 4 percent')
        self.assertEqual(self.score(a, b), 0)

    def test_opposing_outcomes_survive_identical_summary(self):
        a = dict(self.left, title='Cedar Bay appoints Willow project director')
        b = dict(self.right, title='Cedar Bay Willow project director resigns')
        self.assertTrue(evidence_action_conflict(a, b))
        self.assertEqual(self.score(a, b), 0)

    def test_country_guard_survives_summary(self):
        a = dict(self.left, title='Canada council approves Willow coastal wind project')
        b = dict(self.right, title='Australia council approves Willow coastal wind project')
        self.assertEqual(self.score(a, b), 0)

    def test_language_and_time_guards_survive_summary(self):
        self.assertEqual(self.score(right=dict(self.right, language='fr')), 0)
        self.assertEqual(self.score(right=dict(self.right, published_at='2026-09-27T07:00:00Z')), 0)

    def test_generic_topic_without_action_abstains(self):
        left = article(3, 'Cedar Bay weather and coastal outlook', 'Cedar Bay residents describe the coastal weather and local conditions during the week.')
        right = article(4, 'Cedar Bay coastal weather overview', left['summary'])
        context = build_summary_context([left, right], comparison_tokens)
        self.assertEqual(summary_score(left, right, comparison_tokens(left), comparison_tokens(right), {}, context, comparison_tokens), 0)

    def test_existing_registry_is_not_mutated_or_silently_merged(self):
        first, second = deepcopy(self.left), deepcopy(self.right)
        _, state = build_event_index([first], NOW)
        _, separate = build_event_index([dict(second, summary=None)], NOW)
        state['events'].update(separate['events'])
        state['articles'].update(separate['articles'])
        before = deepcopy(state)
        index, returned = build_event_index([deepcopy(self.left), deepcopy(self.right)], NOW, state)
        self.assertEqual(len(index['events']), 2)
        self.assertEqual(state, before)
        self.assertEqual(validate_registry(returned), returned)
        for event in returned['events'].values():
            self.assertNotIn('summary', event['anchor'])

    def test_no_summary_keeps_raw_anchor_contract(self):
        row = dict(self.left, summary=None)
        _, state = build_event_index([row], NOW)
        anchor = next(iter(state['events'].values()))['anchor']
        self.assertEqual(anchor, signature(row['title'], row['language'], row['published_at']))


if __name__ == '__main__':
    unittest.main()
