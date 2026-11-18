from datetime import datetime, timezone, timedelta
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from test_workflow import Harness
from services.campaigns import merge_extractions, normalize_campaign
from services.publishing import ReplizClient, matches_publication
from services.storage import WorkflowStore


class WorkflowRegressionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.api=Harness(self.root)
        self.c=self.api.save_campaign_workspace(None,{'name':'Film','audience_scope':'film','account_ids':['a'],'brief':{'hashtags':['#film'],'max_clips_per_day':2}})['campaign']
        self.api.save_account_profile('a',{'audience_scope':'film','daily_limit':2})
        self.path=self.root/'master.mp4';self.path.write_bytes(b'render')
        self.clip=self.api._register_clip(self.path,{'title':'Cerita','caption':'Cerita #film','campaign_id':self.c['id'],'campaign_snapshot':self.c})
        self.api.review_clip(self.clip['id'],{'action':'approve'})
    def tearDown(self):self.tmp.cleanup()
    def queue(self):
        preview=self.api.preview_distribution([self.clip['id']]);self.assertEqual(preview['status'],'ok',preview)
        result=self.api.confirm_distribution(preview['preview_id']);self.assertEqual(result['status'],'ok',result)
        return self.api._get_store().publications()[-1]
    def test_cancelled_item_can_be_planned_again(self):
        first=self.queue();self.assertEqual(self.api.control_publication(first['id'],'cancel')['status'],'ok')
        self.queue();self.assertEqual(len(self.api._get_store().publications()),2)
        self.assertEqual(sum(p['status']=='queued' for p in self.api._get_store().publications()),1)
    def test_profile_changes_invalidate_preview(self):
        preview=self.api.preview_distribution([self.clip['id']])
        self.api.save_account_profile('a',{'audience_scope':'film','daily_limit':1})
        self.assertEqual(self.api.confirm_distribution(preview['preview_id'])['status'],'error')
    def test_cancel_does_not_override_worker_claim(self):
        pub=self.queue();store=self.api._get_store();store.claim_publication()
        with self.assertRaises(ValueError):store.update_publication(pub['id'],{'status':'cancelled'},expected_status=('queued',))
        self.assertEqual(store.publication(pub['id'])['status'],'uploading')
    def test_partial_hashtag_does_not_meet_requirement(self):
        self.assertEqual(self.api.review_clip(self.clip['id'],{'action':'approve','caption':'#filming'})['status'],'error')
    def test_restart_during_storage_upload_can_retry_without_schedule_reconciliation(self):
        pub=self.queue();store=self.api._get_store();store.claim_publication();store.recover_interrupted()
        self.assertEqual(store.publication(pub['id'])['status'],'failed')
        self.assertFalse(store.publication(pub['id'])['uncertain_submission'])
        self.assertEqual(self.api.control_publication(pub['id'],'retry')['status'],'ok')
    def test_ambiguous_submit_keeps_media_and_does_not_retry(self):
        pub=self.queue();uploader=Mock();uploader.upload_video_to_storage.return_value=(True,'https://storage.test/final.mp4');uploader.create_schedule.return_value=(False,'timeout')
        self.api._make_uploader=lambda *_:uploader
        self.api._send_publication(pub)
        current=self.api._get_store().publication(pub['id']);self.assertEqual(current['status'],'needs_attention')
        self.assertTrue(current['uncertain_submission']);self.assertEqual(current['media_url'],'https://storage.test/final.mp4')
        self.assertEqual(self.api.control_publication(pub['id'],'retry')['status'],'error')
        uploader.create_schedule.assert_called_once()
    def test_resume_finalization_preserves_review_and_caption(self):
        clip=self.api._get_store().get('clip',self.clip['id'])
        clip.update(render_key='key',final_sha256=clip['file_hash'])
        self.api._get_store().put('clip',clip['id'],clip)
        metadata={**clip,'clip_id':clip['id'],'caption':'Old original'}
        result=self.api._finalize_workflow_clip(self.root,metadata,{'campaign':self.c})
        self.assertEqual(result['caption'],'Cerita #film');self.assertEqual(result['review_status'],'approved')


class ProviderTests(unittest.TestCase):
    def test_paginated_reconciliation_matches_content_and_account(self):
        when=datetime.now(timezone.utc).isoformat()
        pub={'account_id':'a','scheduled_at':when,'media_url':'https://test/file','caption':'One'}
        item={'_id':'schedule','accountId':'a','scheduleAt':when,'medias':[{'url':'https://test/file'}],'description':'One','status':'pending'}
        session=Mock();response1=Mock();response1.json.return_value={'docs':[{**item,'accountId':'b'}],'hasNextPage':True}
        response2=Mock();response2.json.return_value={'docs':[item],'hasNextPage':False};session.get.side_effect=[response1,response2]
        result=ReplizClient('a','s',session).reconcile(pub)
        self.assertEqual(result['schedule_id'],'schedule');self.assertEqual(result['status'],'scheduled');self.assertEqual(session.get.call_count,2)
    def test_duplicate_matches_remain_uncertain(self):
        when=datetime.now(timezone.utc).isoformat();pub={'account_id':'a','scheduled_at':when,'media_url':'https://test/file','caption':'One'}
        item={'_id':'s','accountId':'a','scheduleAt':when,'medias':[{'url':'https://test/file'}],'description':'One'}
        session=Mock();session.get.return_value.json.return_value={'docs':[item,item],'hasNextPage':False}
        with self.assertRaises(ValueError):ReplizClient('a','s',session).reconcile(pub)
    def test_retry_accepts_empty_204_response(self):
        session=Mock();session.put.return_value.status_code=204
        ReplizClient('a','s',session).retry('schedule/id')
        session.put.return_value.json.assert_not_called();self.assertIn('schedule%2Fid/retry',session.put.call_args.args[0])


class CampaignTests(unittest.TestCase):
    def test_template_selection_is_bounded_and_manual_choice_wins(self):
        from services.editing import build_clip_plan
        source={'path':'unused','source_id':'s'};highlight={'start_time':'00:00:00','end_time':'00:00:15','template_id':'bold'}
        fixed=build_clip_plan(source,highlight,{'editing':{'template_id':'clean','template_mode':'fixed'}})
        automatic=build_clip_plan(source,highlight,{'editing':{'template_id':'clean','template_mode':'ai_select'}})
        self.assertEqual(fixed['template']['id'],'clean');self.assertEqual(automatic['template']['id'],'bold')
        invalid=build_clip_plan(source,{**highlight,'template_id':'execute-code'},{'editing':{'template_id':'clean','template_mode':'ai_select'}})
        self.assertEqual(invalid['template']['id'],'clean');self.assertTrue(invalid['template_selection']['fallback'])
    def test_sources_keep_conflict_and_provenance(self):
        result=merge_extractions([{'id':'a','name':'A','extracted':{'brief':{'durasi_max':60,'hashtags':['#film']}}},
                                  {'id':'b','name':'B','extracted':{'brief':{'durasi_max':90,'hashtags':['#ibu']}}}],{'brief':{'durasi_max':45}})
        self.assertEqual(result['extracted']['brief']['durasi_max'],45)
        self.assertEqual(result['extracted']['brief']['hashtags'],['#film','#ibu']);self.assertEqual(len(result['conflicts']),2)
        self.assertEqual(len(result['provenance']['brief.durasi_max']),2)
    def test_required_asset_wins_over_stale_flags(self):
        value=normalize_campaign({'assets':[{'path':'music.wav','role':'music','required':True}], 'editing':{'music':{'policy':'none','required':False}}})
        self.assertTrue(value['rules']['music_required']);self.assertEqual(value['editing']['music']['policy'],'local')
    def test_extraction_cannot_enable_automatic_upload_or_assign_accounts(self):
        result=merge_extractions([{'id':'a','name':'A','extracted':{'account_ids':['unwanted'],'editing':{'review_mode':'automatic'},'rules':{'music_required':True}}}])
        self.assertNotIn('editing',result['extracted']);self.assertNotIn('account_ids',result['extracted'])


class DesktopBridgeTests(unittest.TestCase):
    def test_only_one_worker_owns_a_workspace_and_next_can_take_over(self):
        from services.worker_lease import WorkerLease
        with tempfile.TemporaryDirectory() as folder:
            first=WorkerLease(Path(folder)/'worker.lock');second=WorkerLease(Path(folder)/'worker.lock')
            try:
                self.assertTrue(first.acquire());self.assertFalse(second.acquire())
                first.close();self.assertTrue(second.acquire())
            finally:first.close();second.close()
    def test_float_campaign_duration_reaches_core_and_worker_ownership_survives_run(self):
        import app
        api=app.WebAPI.__new__(app.WebAPI);api._get_cfg=lambda:{'campaigns':[{'id':'c','brief':{'durasi_min':15.5,'durasi_max':60.5}}]}
        api.current_job=None;api.job_history=[];api.thread=object();worker=api.thread
        api._configure_workflow_core=lambda *_:None
        with patch.object(app,'AutoClipperCore') as constructor:
            api._run('source',1,False,False,'id',False,False,False,'c')
            self.assertEqual(constructor.return_value.process.call_args.kwargs['dur_min'],15.5)
            self.assertEqual(constructor.return_value.process.call_args.kwargs['dur_max'],60.5)
        self.assertIs(api.thread,worker)
        self.assertEqual(app.WebAPI.start_processing.__qualname__,'WorkflowMixin.start_processing')


if __name__=='__main__':unittest.main()
