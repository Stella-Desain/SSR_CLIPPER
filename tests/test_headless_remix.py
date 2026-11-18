import argparse
import copy
from pathlib import Path
import tempfile
import unittest

from services.storage import WorkflowStore
from tools.remix_headless_outputs import commit_pending_revisions, music_volume


class HeadlessRemixTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = WorkflowStore(Path(self.tmp.name) / 'workflow.sqlite3')
        self.parents = {}
        self.revised = []
        for identifier in ('a', 'b'):
            clip = {'id': identifier, 'revision_id': 'old-' + identifier,
                    'file_hash': 'old-hash', 'review_status': 'pending', 'path': 'original.mp4'}
            self.parents[identifier] = clip
            self.store.put('clip', identifier, clip)
            self.store.put('clip_revision', clip['revision_id'], clip)
            self.revised.append({**clip, 'revision_id': 'new-' + identifier,
                                 'file_hash': 'new-hash', 'path': 'remixed.mp4'})

    def test_updates_pending_clips_without_duplicate_ids_or_destroying_history(self):
        commit_pending_revisions(self.store, self.parents, self.revised, 'job', {'volume': .2})
        self.assertEqual(len(self.store.list('clip')), 2)
        self.assertEqual(self.store.get('clip', 'a')['revision_id'], 'new-a')
        self.assertEqual(self.store.get('clip_revision', 'old-a'), self.parents['a'])
        self.assertEqual(self.store.get('clip', 'a')['review_status'], 'pending')

    def test_stale_second_clip_prevents_any_updates(self):
        self.store.update('clip', 'b', {'revision_id': 'user-edit'})
        with self.assertRaises(ValueError):
            commit_pending_revisions(self.store, self.parents, self.revised, 'job', {})
        self.assertEqual(self.store.get('clip', 'a'), self.parents['a'])

    def test_approved_clip_is_not_replaced(self):
        self.store.update('clip', 'a', {'review_status': 'approved'})
        before = copy.deepcopy(self.store.list('clip'))
        with self.assertRaises(ValueError):
            commit_pending_revisions(self.store, self.parents, self.revised, 'job', {})
        self.assertEqual(self.store.list('clip'), before)

    def test_existing_publication_is_not_replaced(self):
        self.store.save_publication({'id': 'p', 'dedupe_key': 'p', 'clip_id': 'a', 'account_id': 'account',
            'local_day': '2026-10-14', 'scheduled_at': '2026-10-14T12:00:00Z', 'status': 'queued'})
        with self.assertRaises(ValueError):
            commit_pending_revisions(self.store, self.parents, self.revised, 'job', {})
        self.assertEqual(self.store.get('clip', 'a'), self.parents['a'])

    def test_invalid_volume_is_rejected(self):
        for value in (0, -1, float('nan'), float('inf'), 2.1):
            with self.subTest(value=value), self.assertRaises(argparse.ArgumentTypeError):
                music_volume(value)
        self.assertEqual(music_volume('0.2'), .2)


if __name__ == '__main__':
    unittest.main()
