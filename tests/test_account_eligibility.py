import unittest

from services.publishing import eligible_accounts


class AccountEligibilityTests(unittest.TestCase):
    def setUp(self):
        self.campaign = {'audience_scope': 'Motivasi', 'account_ids': ['a'],
                         'brief': {'platforms': ['tiktok']}, 'language': 'id'}
        self.account = {'_id': 'a', 'name': 'Channel A', 'type': 'tiktok', 'isConnected': True}
        self.profile = {'account_id': 'a', 'audience_scope': 'motivasi',
                        'language': 'id', 'timezone': 'Asia/Makassar'}

    def test_missing_profile_identifies_required_action(self):
        with self.assertRaisesRegex(ValueError, 'Channel A: isi dan simpan profil audiens'):
            eligible_accounts(self.campaign, [], [self.account])

    def test_mismatch_reports_both_scopes_without_bypassing_policy(self):
        with self.assertRaisesRegex(ValueError, "audiens akun 'Gaming' berbeda dari campaign 'Motivasi'"):
            eligible_accounts(self.campaign, [{**self.profile, 'audience_scope': 'Gaming'}], [self.account])

    def test_disconnected_and_missing_accounts_explain_reconnection(self):
        with self.assertRaisesRegex(ValueError, 'koneksi akun terputus'):
            eligible_accounts(self.campaign, [self.profile], [{**self.account, 'isConnected': False}])
        with self.assertRaisesRegex(ValueError, 'tidak ditemukan di Repliz'):
            eligible_accounts(self.campaign, [self.profile], [])

    def test_valid_account_remains_eligible_when_another_is_incompatible(self):
        self.campaign['account_ids'].append('b')
        accounts = [self.account, {**self.account, '_id': 'b', 'isConnected': False}]
        self.assertEqual(eligible_accounts(self.campaign, [self.profile], accounts), [(self.account, self.profile)])

    def test_no_assignment_gives_campaign_action(self):
        self.campaign['account_ids'] = []
        with self.assertRaisesRegex(ValueError, 'Pilih akun tujuan'):
            eligible_accounts(self.campaign, [self.profile], [self.account])


if __name__ == '__main__':
    unittest.main()
