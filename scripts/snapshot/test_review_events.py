import unittest
from review_events import evaluate


class ReviewTests(unittest.TestCase):
    def packet(self):
        return {'snapshot_id': 'test', 'content_sha256': 'digest', 'sampling': {},
                'pairs': [{'pair_id': str(i), 'predicted_same': i < 100} for i in range(240)]}

    def labeled(self):
        return {'snapshot_id': 'test', 'content_sha256': 'digest', 'reviewer_name': 'Synthetic unit fixture',
                'label_origin': 'human', 'reviewed_at': '2026-09-30T00:00:00Z',
                'pairs': [{'pair_id': str(i), 'label': 'same' if i < 100 else 'different'} for i in range(240)]}

    def test_unreviewed_and_unnamed_packets_cannot_pass(self):
        data = self.labeled(); data['label_origin'] = 'unreviewed'
        with self.assertRaises(ValueError): evaluate(self.packet(), data)
        data = self.labeled(); data['reviewer_name'] = ''
        with self.assertRaises(ValueError): evaluate(self.packet(), data)

    def test_precision_recall_and_uncertain_count_separated(self):
        data = self.labeled(); data['pairs'][0]['label'] = 'different'; data['pairs'][100]['label'] = 'same'; data['pairs'][239]['label'] = 'uncertain'
        result = evaluate(self.packet(), data)
        self.assertEqual(result['precision'], .99)
        self.assertEqual(result['recall'], .99)
        self.assertEqual(result['counts']['labeled'], 239)
        self.assertEqual(result['counts']['unscored'], 1)

    def test_missing_foreign_or_duplicate_pairs_rejected(self):
        for change in ('missing', 'foreign', 'duplicate'):
            data = self.labeled()
            if change == 'missing': data['pairs'].pop()
            elif change == 'foreign': data['pairs'][0]['pair_id'] = 'foreign'
            else: data['pairs'][0]['pair_id'] = '1'
            with self.assertRaises(ValueError): evaluate(self.packet(), data)

    def test_insufficient_labels_fail(self):
        data = self.labeled()
        for row in data['pairs'][:50]: row['label'] = None
        self.assertFalse(evaluate(self.packet(), data)['gate_pass'])


if __name__ == '__main__': unittest.main()
