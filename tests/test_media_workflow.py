"""Offline integration checks with real FFmpeg and synthetic, non-user media."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from services.editing import build_clip_plan, mix_music, probe_media, render_composition, file_sha256
from services.framing import frame_video
from services.media_preview import MediaPreview


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg tools required')
class MediaWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.video = cls.root / 'source.mp4'
        cls.music = cls.root / 'music.wav'
        cls.endcard = cls.root / 'endcard.png'
        cls.run_ff('-f','lavfi','-i','testsrc2=size=320x180:rate=24:duration=2.4',
                   '-f','lavfi','-i','sine=frequency=440:duration=2.4','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-shortest',str(cls.video))
        cls.run_ff('-f','lavfi','-i','sine=frequency=180:duration=0.8',str(cls.music))
        cls.run_ff('-f','lavfi','-i','color=c=green:s=320x180','-frames:v','1',str(cls.endcard))
        cls.video.with_suffix('.srt').write_text('1\n00:00:00,000 --> 00:00:01,800\nCerita keluarga yang hangat.\n',encoding='utf-8')

    @classmethod
    def run_ff(cls,*args):
        result=subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y',*args],capture_output=True,timeout=90)
        if result.returncode: raise AssertionError(result.stderr.decode(errors='replace'))

    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()

    def test_composition_includes_endcard_and_music_without_duration_drift(self):
        source={'path':str(self.video),'source_id':'original'}
        plan=build_clip_plan(source,{'start_time':'00:00:00','end_time':'00:00:01'}, {
            'rules':{'max_external_ratio':.6,'max_external_ratio_strict':True},
            'editing':{'endcard':{'path':str(self.endcard),'duration_seconds':1,'required':True},
                       'music':{'path':str(self.music),'required':True}}})
        output=self.root/'composition.mp4'
        media=render_composition(plan['segments'],output,width=270,height=480)
        self.assertAlmostEqual(media['duration'],2,delta=.1)
        self.assertEqual((media['width'],media['height']),(270,480))
        mixed=self.root/'mixed.mp4'
        result=mix_music(output,plan['music'],mixed)
        self.assertTrue(result['mixed']);self.assertTrue(probe_media(mixed)['has_audio'])
        self.assertAlmostEqual(probe_media(mixed)['duration'],media['duration'],delta=.1)
        # The closing image must actually be in the rendered media, not only metadata.
        import cv2
        capture=cv2.VideoCapture(str(mixed));capture.set(cv2.CAP_PROP_POS_MSEC,1500)
        ok,frame=capture.read();capture.release();self.assertTrue(ok)
        b,g,r=frame[240,135];self.assertGreater(int(g),int(r)+30);self.assertGreater(int(g),int(b)+30)

    def test_ambiguous_face_framing_preserves_duration_and_records_fallback(self):
        core=SimpleNamespace(ffmpeg_path='ffmpeg',mediapipe_settings={},campaign_config={'editing':{'framing':'speaker'}},
                             face_tracking_mode='opencv',is_cancelled=lambda:False,log=lambda *_:None)
        out=self.root/'framed.mp4';frame_video(core,self.video,out,lambda *_:None)
        media=probe_media(out);self.assertEqual((media['width'],media['height']),(1080,1920))
        self.assertAlmostEqual(media['duration'],probe_media(self.video)['duration'],delta=.1)
        camera=json.loads((self.root/'camera.json').read_text(encoding='utf-8'))
        self.assertGreater(camera['fit_frames'],0)

    def test_missing_face_detector_preserves_full_frame_with_observable_fallback(self):
        core = SimpleNamespace(ffmpeg_path='ffmpeg', mediapipe_settings={}, face_tracking_mode='opencv',
            campaign_config={'editing': {'framing': 'speaker'}}, is_cancelled=lambda: False, log=lambda *_: None)
        out = self.root / 'no-detector.mp4'
        # Both installed and bundled detector data must be missing. Otherwise
        # the application's bundled fallback correctly keeps OpenCV available.
        with patch('cv2.data.haarcascades', str(self.root / 'missing-cascades')), \
                patch('utils.helpers.get_bundle_dir', return_value=self.root / 'missing-bundle'):
            frame_video(core, self.video, out, lambda *_: None)
        camera = json.loads((self.root / 'camera.json').read_text(encoding='utf-8'))
        self.assertEqual(camera['detector'], 'unavailable')
        self.assertEqual(camera['fit_frames'], camera['frames'])
        self.assertGreater(camera['frames'], 0)
        self.assertAlmostEqual(probe_media(out)['duration'], probe_media(self.video)['duration'], delta=.1)

    def test_core_local_source_finalization_and_resume_without_ai(self):
        from clipper_core import AutoClipperCore
        output=self.root/'core';finalized=[]
        def make():
            core=AutoClipperCore(client=None,output_dir=str(output),log_callback=lambda *_:None)
            core.resume_dir=output/'job-test';core.campaign_config={'editing':{'template_id':'clean',
                'music':{'policy':'local','path':str(self.music)}},'brief':{'durasi_min':1,'durasi_max':3}}
            core.finalize_callback=lambda directory,meta:finalized.append(meta) or meta
            return core
        core=make();core.process(str(self.video),num_clips=1,add_captions=False,add_hook=False,portrait=False,highlight_finder=False,dur_min=1,dur_max=2)
        self.assertEqual(core.get_clips_state()[0]['status'],'done',core.get_clips_state())
        self.assertEqual(finalized[0]['audio_analysis']['status'],'measured')
        self.assertIsInstance(finalized[0]['audio_analysis']['true_peak_dbtp'],float)
        master=output/'job-test'/'clip-001'/'master.mp4';before=file_sha256(master)
        other=make();other._render_clip_base=lambda *a,**k:self.fail('Completed clip must not render again')
        other.process(str(self.video),num_clips=1,add_captions=False,add_hook=False,portrait=False,highlight_finder=False,dur_min=1,dur_max=2)
        self.assertEqual(other.get_clips_state()[0]['status'],'done',other.get_clips_state())
        self.assertEqual(before,file_sha256(master));self.assertEqual(len(finalized),2)
        self.assertEqual(finalized[0]['audio_analysis'],finalized[1]['audio_analysis'])

    def test_templates_produce_distinct_subtitles_through_real_renderer(self):
        from clipper_core import AutoClipperCore
        words=[SimpleNamespace(word='Cerita',start=.1,end=.8),SimpleNamespace(word='keluarga',start=.8,end=1.7)]
        transcript=SimpleNamespace(words=words,segments=[SimpleNamespace(text='Cerita keluarga',start=.1,end=1.7,words=words)])
        core=AutoClipperCore(client=None,output_dir=str(self.root/'captions'),log_callback=lambda *_:None)
        core._whisper_transcribe_words=lambda *_:transcript
        hashes=[]
        for style in ['minimal','capcut','hormozi']:
            output=self.root/(style+'.mp4')
            core.add_captions_api_with_progress(str(self.video),str(output),subtitle_style=style)
            self.assertTrue(probe_media(output)['has_audio']);hashes.append(file_sha256(output))
        core.cleanup();self.assertEqual(len(set(hashes)),3)

    def test_template_preview_bridge_returns_playable_video(self):
        from test_workflow import Harness
        api=Harness(self.root/'preview-api')
        try:
            result=api.get_template_preview('clean')
            self.assertEqual(result['status'],'ok',result)
            self.assertTrue(result['preview_url'].startswith('http://127.0.0.1:'))
            from urllib.parse import urlsplit
            output=api._media_preview.files[urlsplit(result['preview_url']).path]
            self.assertAlmostEqual(probe_media(output)['duration'],3,delta=.1)
            shutil.copyfile(self.video, output)
            cached = api.get_template_preview('clean')
            self.assertEqual(cached['status'], 'error', cached)
            self.assertIn('kanvas', cached['message'])
        finally:
            if hasattr(api,'_media_preview'):api._media_preview.close()

    def test_final_duration_budget_reserves_mandatory_endcard(self):
        from clipper_core import AutoClipperCore
        core=AutoClipperCore(client=None,output_dir=str(self.root/'budget'))
        core.campaign_config={'editing':{'endcard':{'path':str(self.endcard),'duration_seconds':3}}}
        self.assertEqual(core._highlight_duration_budget(15,60),(12,57))
        core.cleanup()

    def test_required_poster_is_part_of_composition(self):
        plan=build_clip_plan({'path':str(self.video),'source_id':'s'}, {'start_time':'00:00:00','end_time':'00:00:01'},
            {'assets':[{'id':'poster','path':str(self.endcard),'role':'image','required':True}]})
        self.assertEqual(len(plan['segments']),2)
        self.assertEqual(plan['segments'][1]['asset_id'],'poster');self.assertTrue(plan['segments'][1]['is_image'])
        self.assertEqual(plan['validation']['duration_seconds'],4)

    def test_variable_frame_rate_preserves_the_time_of_visual_events(self):
        import cv2
        source = self.root / 'variable.mp4'
        self.run_ff('-f','lavfi','-i','color=red:s=160x90:r=24:d=0.25',
            '-f','lavfi','-i','color=blue:s=160x90:r=24:d=0.25',
            '-filter_complex','[0:v][1:v]concat=n=2:v=1:a=0,setpts=PTS+gte(N\\,6)*1/TB[v]',
            '-map','[v]','-fps_mode','vfr','-c:v','libx264',str(source))
        info = probe_media(source)
        self.assertLess(info['fps'], info['nominal_fps'])
        core = SimpleNamespace(ffmpeg_path='ffmpeg', mediapipe_settings={}, face_tracking_mode='opencv',
            campaign_config={'editing':{'framing':'fit'}}, is_cancelled=lambda:False, log=lambda *_:None)
        final = self.root / 'variable-framed.mp4'
        frame_video(core, source, final, lambda *_:None)
        capture = cv2.VideoCapture(str(final))
        try:
            for seconds, channel in [(0.8,2), (1.3,0)]:
                capture.set(cv2.CAP_PROP_POS_MSEC,seconds*1000)
                ok, frame = capture.read()
                self.assertTrue(ok)
                self.assertGreater(int(frame[960,540,channel]),200)
        finally:
            capture.release()
        self.assertAlmostEqual(probe_media(final)['duration'],info['duration'],delta=.1)

    def test_efficient_decode_preserves_crop_pixels_and_timing(self):
        import cv2
        import numpy as np
        source = self.root / 'large-pattern.mp4'
        self.run_ff('-f','lavfi','-i','testsrc2=size=1280x720:rate=24:duration=0.5',
            '-c:v','libx264','-preset','ultrafast',str(source))
        core = SimpleNamespace(ffmpeg_path='ffmpeg', mediapipe_settings={}, face_tracking_mode='opencv',
            campaign_config={'editing': {'framing': 'center'}}, efficient_framing=True,
            is_cancelled=lambda: False, log=lambda *_: None)
        final = self.root / 'efficient-framed.mp4'
        frame_video(core, source, final, lambda *_: None, output_width=480, output_height=360)
        # Compare the actual crop against a direct full-source crop, not the
        # optimization's implementation or its metadata alone.
        expected = self.root / 'expected-crop.mp4'
        self.run_ff('-i',str(source),'-vf','crop=960:720:160:0,scale=480:360',
            '-c:v','libx264','-crf','18',str(expected))
        captures = [cv2.VideoCapture(str(p)) for p in (final,expected)]
        try:
            images = [capture.read() for capture in captures]
            self.assertTrue(all(ok for ok, _ in images))
            error = np.mean(np.abs(images[0][1].astype(float)-images[1][1].astype(float)))
            self.assertLess(error, 8)
        finally:
            for capture in captures: capture.release()
        info = probe_media(final)
        self.assertEqual((info['width'],info['height']),(480,360))
        self.assertAlmostEqual(info['duration'],probe_media(source)['duration'],delta=.05)
        camera = json.loads((self.root/'camera.json').read_text(encoding='utf-8'))
        self.assertEqual(camera['frames'],12)
        self.assertEqual(camera['decode_canvas'],{'width':640,'height':360})

    def test_hardware_framing_failure_retries_without_mutating_shared_settings(self):
        encoder = ['-c:v','h264_qsv','-preset','invalid-framing-test-preset']
        messages = []
        core = SimpleNamespace(ffmpeg_path='ffmpeg', mediapipe_settings={}, face_tracking_mode='opencv',
            campaign_config={'editing': {'framing': 'center'}}, framing_encoder_args=encoder,
            is_cancelled=lambda: False, log=messages.append)
        final = self.root / 'encoder-fallback.mp4'
        before = file_sha256(self.video)
        frame_video(core,self.video,final,lambda *_:None,output_width=160,output_height=90)
        self.assertTrue(probe_media(final)['has_audio'])
        self.assertAlmostEqual(probe_media(final)['duration'],probe_media(self.video)['duration'],delta=.05)
        self.assertEqual(file_sha256(self.video),before)
        self.assertEqual(core.framing_encoder_args,encoder)
        camera = json.loads((self.root/'camera.json').read_text(encoding='utf-8'))
        self.assertEqual(camera['video_encoder'],'libx264')
        self.assertTrue(any('mengulang dengan CPU' in message for message in messages))

    def test_source_duration_uses_video_when_audio_is_longer(self):
        source = self.root / 'long-audio.mp4'
        self.run_ff('-i',str(self.video),'-f','lavfi','-i','sine=frequency=440:duration=4',
            '-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac',str(source))
        info = probe_media(source)
        self.assertLess(info['duration'],2.5)
        self.assertGreaterEqual(info['container_duration'],4)


class PreviewTests(unittest.TestCase):
    def test_ranges_and_unregistered_files(self):
        import urllib.request
        import urllib.error
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'video.mp4';path.write_bytes(b'0123456789')
            server=MediaPreview()
            try:
                url=server.register(path)
                with urllib.request.urlopen(urllib.request.Request(url,headers={'Range':'bytes=2-5'})) as res:
                    self.assertEqual(res.status,206);self.assertEqual(res.read(),b'2345')
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(url+'/../other.mp4')
                self.assertEqual(error.exception.code,404)
                error.exception.close()
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(urllib.request.Request(url,headers={'Range':'bytes=99-'}))
                self.assertEqual(error.exception.code,416)
                error.exception.close()
            finally: server.close()


if __name__=='__main__': unittest.main()
