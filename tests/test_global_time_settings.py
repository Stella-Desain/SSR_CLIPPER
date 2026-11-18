"""Global clock settings use a temporary config and never create a GUI."""
import unittest
from pathlib import Path
import tempfile
from app import WebAPI
from test_workflow import Harness


class GlobalClockSettingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.api = Harness(Path(self.tmp.name))

    def test_old_config_defaults_to_wita_and_fixed_am_pm(self):
        self.assertEqual(WebAPI.get_scheduling_settings(self.api),
                         {"status": "ok", "timezone": "Asia/Makassar", "time_format": "12h"})

    def test_saving_global_zone_preserves_other_settings(self):
        self.api.cfg['campaigns'] = [{'id': 'existing'}]
        result = WebAPI.save_scheduling_settings(self.api, {"timezone": "Asia/Jakarta"})
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(self.api.cfg['campaigns'], [{'id': 'existing'}])
        self.assertEqual(WebAPI.get_scheduling_settings(self.api)['timezone'], 'Asia/Jakarta')

    def test_invalid_zone_does_not_change_config(self):
        for value in (None, {}, {'timezone': []}, {'timezone': 'Mars/Olympus'}):
            with self.subTest(value=value):
                self.assertEqual(WebAPI.save_scheduling_settings(self.api, value)['status'], 'error')
                self.assertNotIn('timezone', self.api.cfg)


if __name__ == '__main__':
    unittest.main()
