import unittest

from tools.verify_headless_outputs import editorial_notes


class EditorialNotesTests(unittest.TestCase):
    def setUp(self):
        self.flags = [
            {'type': 'music', 'note': 'Review music rights.'},
            {'decision_id': 'c07', 'note': 'Review source numeric claim.'},
            {'decision_ids': ['c01', 'c07'], 'note': 'Speaker opinion.'},
        ]

    def test_shared_notes_are_separate_from_clip_notes(self):
        self.assertEqual(editorial_notes(self.flags), ['Review music rights.'])

    def test_targets_decision_not_render_order(self):
        self.assertEqual(editorial_notes(self.flags, 'c07'), [
            'Review source numeric claim.', 'Speaker opinion.',
        ])

    def test_does_not_flag_other_decisions(self):
        self.assertEqual(editorial_notes(self.flags, 'c10'), [])


if __name__ == '__main__':
    unittest.main()
