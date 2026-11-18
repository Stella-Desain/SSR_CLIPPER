"""Retry transport failures without creating duplicate social schedules."""
import contextlib
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import manage_ironman_approved_batch as batch


class StorageRetryTests(unittest.TestCase):
    def run_case(self, prior):
        store = MagicMock()
        store.publications.return_value = [prior]
        store.update_publication.side_effect = lambda identity, fields, **kw: {**prior, **fields}
        store.publication.return_value = {**prior, 'status':'scheduled', 'schedule_id':'existing-reservation-result'}
        api = MagicMock()
        api._get_store.return_value = store
        api._get_cfg.return_value = {'repliz':{'access_key':'test','secret_key':'test'}}
        client = MagicMock()
        client.get.return_value = {'docs':[{'_id':batch.ACCOUNT, 'username':'anak.clip0',
            'name':'Anak.clipo','type':'instagram','isConnected':True}]}
        def read(path):
            if Path(path).name=='registered-clips.json':
                return [{'index':1,'clip_id':'clip-test','sha256':'hash-test'}]
            return {'publication_order':[1]}
        with patch.object(batch,'quality'), patch.object(batch,'api_instance',return_value=api), \
             patch.object(batch,'ReplizClient',return_value=client), patch.object(batch,'read',side_effect=read), \
             patch.object(batch,'sync'), contextlib.redirect_stdout(io.StringIO()):
            try:
                batch.publish()
                error = None
            except ValueError as exc:
                error = exc
        return api, store, error

    def prior(self, **fields):
        return {'id':'pub-test','clip_id':'clip-test','account_id':batch.ACCOUNT,
            'status':'failed','file_hash':'hash-test','schedule_id':None,
            'uncertain_submission':False,'error':'Exception saat upload ke storage: connection reset',**fields}

    def test_known_storage_failure_reuses_reservation_once(self):
        api, store, error = self.run_case(self.prior())
        self.assertIsNone(error)
        store.reserve_publications.assert_not_called()
        args, kwargs = store.update_publication.call_args
        self.assertEqual(args[0],'pub-test')
        self.assertEqual(args[1]['safe_storage_retry_count'],1)
        self.assertEqual(kwargs['expected_status'],('failed',))
        api._send_publication.assert_called_once()

    def test_uncertain_or_already_submitted_schedule_is_not_resent(self):
        for fields in [{'uncertain_submission':True},{'uncertain_submission':None},
                       {'schedule_id':'remote-schedule'}, {'error':'Provider failed publishing'}]:
            with self.subTest(fields=fields):
                api, store, error = self.run_case(self.prior(**fields))
                self.assertIsNotNone(error)
                api._send_publication.assert_not_called()
                store.reserve_publications.assert_not_called()

    def test_repeat_retry_and_changed_file_are_refused(self):
        for fields in [{'safe_storage_retry_count':1},{'file_hash':'different-file'}]:
            with self.subTest(fields=fields):
                api, store, error = self.run_case(self.prior(**fields))
                self.assertIsNotNone(error)
                api._send_publication.assert_not_called()


if __name__=='__main__':
    unittest.main()
