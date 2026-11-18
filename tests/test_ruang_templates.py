"""Reference contract: CTA isolation, editable hooks and persisted asset cues."""
import tempfile
import shutil
import subprocess
from pathlib import Path
import unittest
from unittest.mock import patch
from services.ruang_templates import broll_plan,hook_card,style_options,render_layout
from services.editing import EditingValidationError,build_clip_plan,endcard_settings,probe_media

class RuangTemplateTests(unittest.TestCase):
    def layout_commands(self, template, campaign, duration=2, story=2):
        commands=[]
        asset={'path':'opener.mp4','name':'opener','opener':True,'available_seconds':6,'start_seconds':0}
        info={'duration':duration,'width':1080,'height':1920,'fps':30,'has_audio':True,'has_video':True}
        with (patch('services.ruang_templates.probe_media',side_effect=[info,{**info,'duration':duration+5.2}]),
              patch('services.ruang_templates.checked_broll',return_value=[asset]),
              patch('services.ruang_templates._visual_segments')):
            result=render_layout('source.mp4','result.mp4',template,campaign,story_duration=story,
                                 runner=lambda command,_duration:commands.append(command))
        return result,commands[0]

    def test_optional_absent_cta_skips_minimum_logo_text_and_effects(self):
        campaign={'editing':{'reference_style':{'cta_min_seconds':10,'cta_text':'CEK BIO',
            'cta_logo_path':'missing-logo.png','cta_sfx_path':'missing-sound.mp3'}}}
        for template in ('ruang_founder','ruang_witness'):
            result,command=self.layout_commands(template,campaign)
            self.assertFalse(result['cta_present'])
            self.assertFalse(result['cta_required'])
            self.assertEqual(result['cta_duration_seconds'],0)
            self.assertIsNone(result['cta_at_seconds'])
            self.assertEqual(result['cta_text'],'')
            self.assertNotIn('missing-logo.png',command)
            self.assertNotIn('missing-sound.mp3',command)
            self.assertNotIn('drawbox',command[command.index('-filter_complex')+1])

    def test_present_cta_is_rendered_whether_optional_or_required(self):
        for template in ('ruang_founder','ruang_witness'):
            for required in (False,True):
                campaign={'editing':{'endcard':{'path':'cta.mp4','duration_seconds':1,'required':required},
                    'reference_style':{'cta_min_seconds':1,'cta_text':'CEK BIO'}}}
                result,command=self.layout_commands(template,campaign,duration=3)
                self.assertTrue(result['cta_present'])
                self.assertEqual(result['cta_required'],required)
                self.assertAlmostEqual(result['cta_at_seconds'],7.2)
                self.assertEqual(result['cta_duration_seconds'],1)
                self.assertEqual(result['cta_text'],'CEK BIO')
                self.assertIn('drawbox',command[command.index('-filter_complex')+1])

    def test_required_missing_cta_fails_for_settings_rules_and_manifest(self):
        campaigns=[{'editing':{'endcard':{'required':True}}},
                   {'rules':{'endcard_required':True}},
                   {'assets':[{'role':'endcard','required':True,'path':'cta.mp4'}]}]
        for template in ('ruang_founder','ruang_witness'):
            for campaign in campaigns:
                with self.assertRaisesRegex(EditingValidationError,'wajib'):
                    self.layout_commands(template,campaign)

    def test_present_cta_still_obeys_campaign_minimum(self):
        campaign={'editing':{'endcard':{'path':'cta.mp4','duration_seconds':1},
                             'reference_style':{'cta_min_seconds':10}}}
        with self.assertRaisesRegex(EditingValidationError,'minimum campaign'):
            self.layout_commands('ruang_founder',campaign,duration=3)

    def test_clip_plan_appends_available_optional_cta_and_requires_missing_one(self):
        source={'source_id':'source','path':'source.mp4'}
        highlight={'start_time':'00:00:00','end_time':'00:00:02'}
        plan=build_clip_plan(source,highlight,{})
        self.assertEqual(len(plan['segments']),1)
        with self.assertRaises(EditingValidationError):
            build_clip_plan(source,highlight,{'rules':{'endcard_required':True}})
        with tempfile.TemporaryDirectory() as folder:
            optional=Path(folder)/'optional.mp4';optional.write_bytes(b'optional fixture')
            required=Path(folder)/'required.mp4';required.write_bytes(b'required fixture')
            campaign={'assets':[{'role':'endcard','path':str(optional)},
                                 {'role':'endcard','path':str(required),'required':True}]}
            self.assertEqual(endcard_settings(campaign)['path'],str(required))
            for mandatory in (False,True):
                campaign={'assets':[{'role':'endcard','path':str(optional),'required':mandatory}],
                          'editing':{'endcard':{'duration_seconds':1}}}
                with patch('services.editing.probe_media',return_value={'has_video':True,'duration':1}):
                    plan=build_clip_plan(source,highlight,campaign)
                self.assertEqual(plan['segments'][-1]['kind'],'endcard')
                self.assertEqual(plan['endcard']['required'],mandatory)

    def test_broll_never_covers_official_cta_and_matches_narrative_cues(self):
        assets=[{'tags':['laptop'],'available_seconds':7,'name':'work'},
                {'tags':['jet ski'],'available_seconds':9,'name':'travel'}]
        with patch('services.ruang_templates.checked_broll',return_value=assets):
            for template in ('ruang_founder','ruang_witness'):
                shots=broll_plan({},29.2,template,cues=[{'start':6.5,'text':'liburan naik jet ski'}])
                self.assertEqual(shots[0]['name'],'travel')
                for shot in shots:
                    self.assertLessEqual(shot['at_seconds']+shot['duration_seconds'],29.2)
                    self.assertEqual(shot['transition'],'hard_cut')
                    self.assertLessEqual(shot['duration_seconds'],3)

    def test_unmatched_or_broad_cues_keep_main_footage(self):
        assets=[{'tags':['laptop','crypto','advantage'],'available_seconds':8,'name':'work'},
                {'tags':['freedom','jetski'],'available_seconds':9,'name':'travel'}]
        with patch('services.ruang_templates.checked_broll',return_value=assets):
            self.assertEqual(broll_plan({},60,'ruang_witness'),[])
            for text in ('wallet tracking','crypto advantage','freedom','laptopnya'):
                self.assertEqual(broll_plan({},60,'ruang_witness',cues=[{'start':6,'text':text}]),[])

    def test_no_repeated_footage_or_opener_and_sparse_budget(self):
        assets=[{'tags':['wallet'],'sha256':'same','available_seconds':8,'name':'screen'},
                {'tags':['wallet'],'sha256':'same','available_seconds':8,'name':'duplicate'},
                {'tags':['wallet'],'sha256':'intro','available_seconds':8,'name':'opener','opener':True},
                {'tags':['wallet'],'sha256':'different','available_seconds':8,'name':'screen2'}]
        with patch('services.ruang_templates.checked_broll',return_value=assets):
            shots=broll_plan({},38,'ruang_witness',cues=[{'start':t,'text':'wallet'} for t in range(5,35)])
        self.assertLessEqual(len(shots),2)
        self.assertEqual(len({s['sha256'] for s in shots}),len(shots))
        self.assertNotIn('opener',[s['name'] for s in shots])
        self.assertLessEqual(sum(s['duration_seconds'] for s in shots),38*.1)
        self.assertGreaterEqual(shots[1]['at_seconds']-(shots[0]['at_seconds']+shots[0]['duration_seconds']),12)

    def test_hook_colors_and_copy_are_render_inputs(self):
        from PIL import Image,ImageChops
        with tempfile.TemporaryDirectory() as folder:
            a,b=Path(folder)/'a.png',Path(folder)/'b.png'
            hook_card(a,'ruang_founder','WALLET BISA DILACAK?','BEVAN MEMBACA ON-CHAIN')
            hook_card(b,'ruang_founder','CERITA CAMPAIGN LAIN','ISI BERBEDA',
                      {'hook_accent':'#0033ff','hook_background':'#eeeeee'})
            first,second=Image.open(a),Image.open(b)
            self.assertEqual(first.getpixel((55,1190))[:3],(207,0,59))
            self.assertEqual(second.getpixel((55,1190))[:3],(0,51,255))
            self.assertEqual(second.getpixel((55,1300))[:3],(238,238,238))
            self.assertIsNotNone(ImageChops.difference(first,second).convert('RGB').getbbox())

    def test_invalid_campaign_color_fails_before_render(self):
        with self.assertRaises(EditingValidationError):
            style_options({'editing':{'reference_style':{'hook_accent':'invalid'}}})

    def test_campaign_import_preserves_broll_story_cues(self):
        from app import WebAPI
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'broll.mp4';path.write_bytes(b'local fixture')
            result=WebAPI.__new__(WebAPI)._inspect_campaign_file({'path':str(path),'role':'broll',
                'tags':['wallet','onchain'],'opener':True})
            self.assertTrue(result['opener'])
            self.assertEqual(result['tags'],['wallet','onchain'])


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'FFmpeg required')
class OptionalCtaRenderTests(unittest.TestCase):
    def test_video_without_cta_keeps_source_audio_and_finishes_normally(self):
        from PIL import Image
        import numpy as np
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'source.mp4';opener=root/'opener.png';output=root/'final.mp4'
            Image.new('RGB',(180,320),'blue').save(opener)
            subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=red:s=180x320:r=30:d=1',
                            '-f','lavfi','-i','sine=frequency=440:duration=1','-c:v','libx264','-preset','ultrafast',
                            '-c:a','aac','-shortest',str(source)],check=True,capture_output=True,timeout=30)
            campaign={'assets':[{'role':'broll','path':str(opener),'opener':True}],
                      'editing':{'reference_style':{'cta_min_seconds':10,'cta_text':'CEK BIO',
                          'cta_logo_path':'missing-logo.png','cta_sfx_path':'missing-sound.mp3'}}}
            result=render_layout(source,output,'ruang_founder',campaign,story_duration=1)
            info=probe_media(output)
            self.assertFalse(result['cta_present'])
            self.assertEqual((info['width'],info['height']),(1080,1920))
            self.assertTrue(info['has_audio'])
            self.assertAlmostEqual(info['duration'],6.2,delta=.1)
            raw=subprocess.run(['ffmpeg','-v','error','-ss','5.3','-i',str(output),'-t','0.5','-vn',
                                '-ac','1','-ar','8000','-f','f32le','pipe:1'],
                               check=True,capture_output=True,timeout=30).stdout
            self.assertGreater(float(np.sqrt(np.mean(np.frombuffer(raw,dtype=np.float32)**2))),.03)
