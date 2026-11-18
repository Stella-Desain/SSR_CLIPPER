from collections import Counter
from datetime import date, timedelta
import unittest
from unittest.mock import patch

from tools.schedule_timothy_12 import ACCOUNTS, assignments


class ScheduleTwelveTests(unittest.TestCase):
    def setUp(self):
        self.start = date.today() + timedelta(days=7)
        self.clips = [{'id': f'clip-{i}', 'title': f'Clip {i}', 'review_status': 'approved',
            'approval_hash': 'approved', 'revision_id': f'rev-{i}', 'caption': 'Caption',
            'source_ranges': []} for i in range(12)]
        self.campaign = {'audience_scope': 'audience'}
        self.profiles = [{'account_id': aid, 'daily_limit': 4, 'upload_times': ['08:20', '19:30']} for aid in ACCOUNTS]
        self.accounts = [{'_id': aid, 'name': aid} for aid in ACCOUNTS]
        mock = patch('tools.schedule_timothy_12.publication_media', return_value={'path': 'master.mp4', 'file_hash': 'hash'})
        mock.start()
        self.addCleanup(mock.stop)

    def plan(self, existing=()):
        return assignments(self.clips, self.campaign, self.profiles, self.accounts, existing, self.start)

    def test_exact_four_daily_six_each_and_wita_conversion(self):
        rows = self.plan()
        self.assertEqual(Counter(r['account_id'] for r in rows), {ACCOUNTS[0]: 6, ACCOUNTS[1]: 6})
        self.assertEqual(sorted(Counter(r['local_day'] for r in rows).values()), [4, 4, 4])
        self.assertTrue(all(count == 2 for count in Counter((r['account_id'], r['local_day']) for r in rows).values()))
        self.assertEqual(rows[0]['scheduled_at'], (self.start - timedelta(days=1)).isoformat() + 'T23:00:00+00:00')
        self.assertEqual(rows[1]['scheduled_at'], self.start.isoformat() + 'T00:00:00+00:00')
        self.assertEqual(rows[2]['scheduled_at'], self.start.isoformat() + 'T11:00:00+00:00')
        self.assertEqual(rows[3]['scheduled_at'], self.start.isoformat() + 'T12:00:00+00:00')
        self.assertEqual(self.profiles[0]['upload_times'], ['08:20', '19:30'])

    def test_conflicting_old_schedule_is_not_overwritten(self):
        existing = {**self.plan()[0], 'clip_id': 'other'}
        with self.assertRaises(ValueError):
            self.plan([existing])

    def test_wrong_count_and_unapproved_clip_are_rejected(self):
        self.clips[0]['review_status'] = 'pending'
        with self.assertRaises(ValueError):
            self.plan()
        self.clips.pop()
        with self.assertRaises(ValueError):
            self.plan()


if __name__ == '__main__':
    unittest.main()
