from collections import Counter
from datetime import datetime, timedelta, timezone
import unittest

from tools.schedule_timothy_13 import ACCOUNTS, TIMES, ZONE, available_slots, clean_caption, split_clips, spread


class ThirteenClipScheduleTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 21, 15, tzinfo=ZONE)
        self.remote = [
            {'accountId': aid, 'status': status, 'scheduleAt': f'2026-10-21T{hour}:00+08:00'}
            for aid, times in zip(ACCOUNTS, [[('07:00', 'success'), ('19:00', 'pending')],
                                          [('08:00', 'success'), ('20:00', 'pending')]])
            for hour, status in times]

    def test_earliest_slots_and_daily_totals_include_existing_posts(self):
        for aid, count, first in zip(ACCOUNTS, [7, 6], ['19:30', '19:00']):
            slots = available_slots(aid, count, self.remote, self.now)
            self.assertEqual(len(slots), count)
            self.assertEqual(slots[0].strftime('%Y-%m-%d %H:%M'), '2026-10-21 ' + first)
            self.assertEqual(len(set(slots)), count)
            days = Counter(t.date() for t in slots)
            for day, number in days.items():
                existing = sum(r['accountId'] == aid and datetime.fromisoformat(r['scheduleAt']).date() == day
                               for r in self.remote)
                self.assertIn(number + existing, [3, 4])
            self.assertTrue(all(t.strftime('%H:%M') in TIMES for t in slots))
        earliest = available_slots(ACCOUNTS[1], 6, self.remote, self.now)[0]
        self.assertEqual(earliest.astimezone(timezone.utc).isoformat(), '2026-10-21T11:00:00+00:00')

    def test_lead_time_and_existing_exact_minute_are_respected(self):
        now = self.now.replace(hour=18, minute=50)
        for aid in ACCOUNTS:
            slots = available_slots(aid, 6, self.remote, now)
            self.assertTrue(all(t >= now + timedelta(minutes=30) for t in slots))
            occupied = {datetime.fromisoformat(r['scheduleAt']) for r in self.remote if r['accountId'] == aid}
            self.assertFalse(set(slots) & occupied)

    def test_exhausted_capacity_does_not_overbook(self):
        remote = [{'accountId': ACCOUNTS[0], 'status': 'pending',
                   'scheduleAt': (self.now.replace(hour=7, minute=0) + timedelta(days=day, minutes=minute)).isoformat()}
                  for day in range(15) for minute in [0, 30, 720, 750]]
        with self.assertRaises(ValueError):
            available_slots(ACCOUNTS[0], 7, remote, self.now)

    def test_balanced_split_keeps_all_edits_once_and_separates_related_material(self):
        clips = [{'id': str(i), 'source_ranges': [{'source_id': 'source', 'start_seconds': 0 if i < 4 else i*100,
                                                  'end_seconds': 30 if i < 4 else i*100+30}]}
                 for i in range(13)]
        groups = split_clips(clips)
        self.assertEqual([len(g) for g in groups], [7, 6])
        self.assertEqual(Counter(c['id'] for g in groups for c in g), Counter(c['id'] for c in clips))
        self.assertEqual([sum(int(c['id']) < 4 for c in g) for g in groups], [2, 2])

    def test_related_edits_use_the_farthest_slots(self):
        clips = [{'id': str(i), 'source_ranges': [{'source_id': 'source', 'start_seconds': 0 if i < 2 else 100,
                                                  'end_seconds': 30 if i < 2 else 130}]} for i in range(3)]
        slots = [self.now, self.now+timedelta(minutes=30), self.now+timedelta(hours=12)]
        ordered = spread(clips, slots)
        self.assertEqual(ordered[1]['id'], '2')

    def test_caption_cleanup_retains_unique_tags_and_music_credit(self):
        original = 'Kalimat #TimothyRonald\n\n#timothyronald #AkademiCrypto\n\nMusik: original sound — Footyshirts'
        cleaned = clean_caption(original)
        self.assertEqual(cleaned.casefold().count('#timothyronald'), 1)
        self.assertIn('#AkademiCrypto', cleaned)
        self.assertTrue(cleaned.endswith('Musik: original sound — Footyshirts'))
        self.assertEqual(clean_caption(cleaned), cleaned)


if __name__ == '__main__':
    unittest.main()
