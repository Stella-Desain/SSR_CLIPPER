import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import threading
import unittest

from services.campaigns import CampaignMixin, normalize_campaign, merge_extractions
from services.storage import WorkflowStore, file_digest
from services.workflow import WorkflowMixin
from services.music_review import MusicReviewMixin
from services.publishing import plan_distribution, validate_reservation, schedule_update
from services.face_tracking import StableFaceTracker, CameraPlanner, Track, scene_changed


class Harness(MusicReviewMixin, WorkflowMixin, CampaignMixin):
    def __init__(self, root):
        self.config_file = str(root / 'config.json')
        self.output_dir = str(root / 'output')
        self.thread = None
        self.cfg = {'campaigns': [], 'repliz': {'access_key': 'test', 'secret_key': 'test'}}
        self.accounts = [{'_id': 'a', 'name': 'A', 'type': 'tiktok', 'isConnected': True}, {'_id': 'b', 'name': 'B', 'type': 'tiktok', 'isConnected': True}]
    def _get_cfg(self):
        return copy.deepcopy(self.cfg)
    def _get_cfg_manager(self):
        return self
    def save_config(self, cfg):
        self.cfg = copy.deepcopy(cfg)
    def get_repliz_accounts(self):
        return {'status': 'ok', 'accounts': self.accounts}
    def _legacy_get_stock_clips(self):
        return []
    def _start_upload_worker(self):
        pass
    def _start_next_job(self):
        pass


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.api = Harness(self.root)
        result = self.api.save_campaign_workspace(None, {'name': 'Film', 'audience_scope': 'Film keluarga', 'account_ids': ['a','b'], 'language': 'id', 'brief': {'hashtags': ['#film']}})
        self.assertEqual(result['status'], 'ok', result)
        self.campaign = result['campaign']
        for aid in ['a','b']:
            result = self.api.save_account_profile(aid, {'audience_scope': 'Film keluarga', 'timezone': 'Asia/Makassar', 'daily_limit': 1, 'language': 'id'})
            self.assertEqual(result['status'], 'ok', result)
        self.path = self.root/'master.mp4'; self.path.write_bytes(b'test-video')
        self.clip = self.api._register_clip(self.path, {'title': 'A story', 'caption': 'A story #film', 'campaign_id': self.campaign['id'],
            'campaign_snapshot': self.campaign, 'campaign_version_id': self.campaign['version_id'],
            'source_ranges': [{'source_id':'source1','start_seconds':0,'end_seconds':10}]})
    def tearDown(self):
        self.tmp.cleanup()
    def approve(self):
        result = self.api.review_clip(self.clip['id'], {'action':'approve'})
        self.assertEqual(result['status'],'ok',result)
        return result['clip']
    def test_version_changes_and_previous_snapshot_survives(self):
        old = self.campaign['version_id']
        result = self.api.save_campaign_workspace(self.campaign['id'], {'name':'New name'})
        self.assertNotEqual(old,result['version_id'])
        self.assertEqual(self.api._get_store().get('campaign_version',old)['campaign']['name'],'Film')
    def test_required_asset_blocks_production_not_draft_save(self):
        result=self.api.save_campaign_workspace(self.campaign['id'],{'editing':{'music':{'policy':'local','required':True}}})
        self.assertEqual(result['status'],'ok')
        self.assertFalse(result['readiness']['production_ready'])
    def test_caption_required_terms_checked(self):
        result=self.api.review_clip(self.clip['id'],{'caption':'No hashtag','action':'approve'})
        self.assertEqual(result['status'],'error')
    def test_file_changed_invalidates_approval(self):
        self.approve();self.path.write_bytes(b'changed-video')
        result=self.api.preview_distribution([self.clip['id']])
        self.assertEqual(result['status'],'error')
        self.assertEqual(self.api._get_store().get('clip',self.clip['id'])['review_status'],'pending')
    def test_caption_edit_invalidates_approval(self):
        self.approve()
        self.api.review_clip(self.clip['id'],{'caption':'New story #film','action':'save'})
        result=self.api.preview_distribution([self.clip['id']])
        self.assertEqual(result['status'],'error')
    def test_unreviewed_clip_cannot_be_distributed(self):
        self.assertEqual(self.api.preview_distribution([self.clip['id']])['status'],'error')
    def test_preview_then_confirm_is_idempotent(self):
        self.approve(); preview=self.api.preview_distribution([self.clip['id']]); self.assertEqual(preview['status'],'ok',preview)
        first=self.api.confirm_distribution(preview['preview_id']);second=self.api.confirm_distribution(preview['preview_id'])
        self.assertEqual(first['total_scheduled'],1);self.assertEqual(second['total_scheduled'],0)
        self.assertEqual(len(self.api._get_store().publications()),1)
        self.assertEqual(self.api._get_store().publications()[0]['status'],'queued')
    def test_changed_review_rejects_stale_preview(self):
        self.approve();preview=self.api.preview_distribution([self.clip['id']])
        self.api.review_clip(self.clip['id'],{'caption':'Edited #film','action':'approve'})
        self.assertEqual(self.api.confirm_distribution(preview['preview_id'])['status'],'error')
    def test_audience_mismatch_never_routes(self):
        clip=self.approve()
        for profile in self.api._get_store().list('account_profile'):
            self.api.save_account_profile(profile['account_id'],{**profile,'audience_scope':'Gaming'})
        self.assertEqual(self.api.preview_distribution([clip['id']])['status'],'error')
    def test_restart_marks_uncertain_submission(self):
        self.approve();preview=self.api.preview_distribution([self.clip['id']]);self.api.confirm_distribution(preview['preview_id'])
        store=self.api._get_store();p=store.claim_publication();self.assertEqual(p['status'],'uploading')
        store.update_publication(p['id'],{'status':'publishing'})
        WorkflowStore(store.path).recover_interrupted()
        self.assertEqual(store.publication(p['id'])['status'],'needs_attention')
        self.assertEqual(self.api.control_publication(p['id'],'retry')['status'],'error')
    def test_resume_preserves_job_payload(self):
        store=self.api._get_store();store.put('job','j',{'id':'j','status':'running','source':'file','checkpoint':{'done':[1,2]}})
        store.recover_interrupted();self.assertEqual(store.get('job','j')['status'],'interrupted')
        self.assertEqual(self.api.control_job('j','resume')['status'],'ok');self.assertEqual(store.get('job','j')['checkpoint']['done'],[1,2])
    def test_claim_job_is_atomic(self):
        store=self.api._get_store();store.put('job','j',{'id':'j','status':'queued'})
        claims=[];threads=[threading.Thread(target=lambda:claims.append(store.claim_job())) for _ in range(5)]
        for thread in threads:thread.start()
        for thread in threads:thread.join()
        self.assertEqual(sum(c is not None for c in claims),1)


class DistributionTests(unittest.TestCase):
    def test_overlapping_sources_get_different_accounts_and_quota_survives_batches(self):
        campaign={'id':'c','status':'active','audience_scope':'Film','account_ids':['a','b'],'brief':{'max_clips_per_day':1}}
        profiles=[{'account_id':a,'audience_scope':'film','daily_limit':1,'timezone':'Asia/Makassar'} for a in ['a','b']]
        accounts=[{'_id':a,'type':'tiktok'} for a in ['a','b']]
        clip={'id':'x','campaign_id':'c','review_status':'approved','file_hash':'hash','path':'file','source_ranges':[{'source_id':'source','start_seconds':0,'end_seconds':10}]}
        now=datetime(2026,9,16,0,0,tzinfo=timezone.utc)
        first=plan_distribution([clip], [campaign], profiles, accounts, [], now)
        second=plan_distribution([{**clip,'id':'y'}], [campaign], profiles, accounts, first, now)
        self.assertNotEqual(first[0]['account_id'],second[0]['account_id'])
        third=plan_distribution([{**clip,'id':'z','source_ranges':[]}], [campaign], profiles, accounts, first+second, now)
        self.assertEqual(third[0]['local_day'],'2026-09-17')
    def test_schedule_created_not_published(self):
        self.assertEqual(schedule_update({'status':'pending'})['status'],'scheduled')
        self.assertEqual(schedule_update({'status':'success','postId':'id'})['post_id'],'id')
        self.assertNotIn('status',schedule_update({'status':'unrecognized'}))


class FaceTests(unittest.TestCase):
    def test_reordered_detections_keep_identity(self):
        tracker=StableFaceTracker();left={'bbox':(.1,.1,.2,.3),'mouth':.1};right={'bbox':(.7,.1,.2,.3),'mouth':.1}
        first=tracker.update([left,right],0);second=tracker.update([right,left],.1)
        self.assertEqual(first[0].id,second[1].id);self.assertEqual(first[1].id,second[0].id)
    def test_scene_cut_discards_identity(self):
        tracker=StableFaceTracker();face={'bbox':(.1,.1,.2,.3)}
        first=tracker.update([face],0)[0].id;second=tracker.update([face],.1,True)[0].id
        self.assertNotEqual(first,second)
    def test_ambiguous_speakers_fit_whole_frame(self):
        planner=CameraPlanner(1920,1080);faces=[Track(1,(.1,.1,.1,.2),0),Track(2,(.7,.1,.1,.2),0)]
        self.assertEqual(planner.update(faces,0)['mode'],'fit')
    def test_scene_change_threshold(self):
        self.assertFalse(scene_changed([20]*16,[22]*16));self.assertTrue(scene_changed([20]*16,[230]*16))


if __name__=='__main__':unittest.main()
