"""Real media contract: editable draft -> portable version -> independent consumer.

No desktop window, browser, AI, campaign updates or user library are involved.
"""
import copy
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

from PIL import Image
from services.template_editor import TemplateEditorMixin
from services.external_templates import resolve_preset, template_directory
from services.editing import probe_media
from template_sdk.ssr_template_engine.design import load_design, render_design
from utils.helpers import get_ffmpeg_path


class EditorHarness(TemplateEditorMixin):
    pass


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg tools required')
class EditorEndToEndTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='editor real media ')
        self.root = Path(self.tmp.name)
        self.api = EditorHarness()
        self.ffmpeg = get_ffmpeg_path()
        self.editor_patch = patch('services.template_editor.editor_root', return_value=self.root / 'drafts')
        self.library_patch = patch('services.external_templates.library_root', return_value=self.root / 'library')
        self.editor_patch.start(); self.library_patch.start()

    def tearDown(self):
        if hasattr(self.api, '_media_preview'):
            self.api._media_preview.close()
        self.library_patch.stop(); self.editor_patch.stop()
        self.tmp.cleanup()

    def source(self, duration, name):
        source = self.root / name
        subprocess.run([self.ffmpeg, '-y', '-v', 'error', '-f', 'lavfi', '-i',
            f'color=c=blue:s=320x180:r=10:d={duration}', '-f', 'lavfi', '-i',
            f'sine=frequency=440:sample_rate=48000:duration={duration}', '-c:v', 'libx264',
            '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', str(source)], check=True,
            capture_output=True, timeout=60)
        return source

    def ok(self, value):
        self.assertEqual(value['status'], 'ok', value)
        return value

    def frame(self, path, second):
        result = subprocess.run([self.ffmpeg, '-v', 'error', '-ss', str(second), '-i', str(path),
            '-frames:v', '1', '-f', 'image2pipe', '-vcodec', 'png', 'pipe:1'],
            check=True, capture_output=True, timeout=30)
        return Image.open(io.BytesIO(result.stdout)).convert('RGB')

    def test_draft_preview_and_installed_version_render_after_editor_files_are_removed(self):
        short = self.source(2.8, 'sample.mp4')
        long = self.source(37.2, 'real highlight.mp4')
        project = self.ok(self.api.editor_create_project({'name':'Portable layout','ratio':'9:16'}))['project']
        project = self.ok(self.api.editor_add_asset(project['id'], str(short), 'video'))['project']
        font = Path(__file__).resolve().parents[1] / 'assets/fonts/PodcastBlack.ttf'
        font_result = self.ok(self.api.editor_add_asset(project['id'], str(font), 'font'))
        project, font_asset = font_result['project'], font_result['asset']
        image_path = self.root / 'logo.png'
        Image.new('RGBA', (40,40), (255,0,0,255)).save(image_path)
        image_result = self.ok(self.api.editor_add_asset(project['id'], str(image_path), 'image'))
        project, logo = image_result['project'], image_result['asset']
        srt = self.root / 'sample.srt'
        srt.write_text('1\n00:00:00,000 --> 00:00:02,000\nUCAPAN UTUH\n', encoding='utf8')
        project = self.ok(self.api.editor_add_asset(project['id'], str(srt), 'subtitle'))['project']
        project['canvas'].update(width=180,height=320,fps=10)
        video = project['layers'][0]
        video.update(x=10,y=60,width=160,height=200,fit='contain',framing='fit')
        base = {'x':10,'y':5,'width':160,'height':45,'rotation':0,'visible':True,'locked':False,
            'timing':{'mode':'full','start':0,'duration':4}}
        typography = {'font_family':font_asset['font_family'],'font_asset_id':font_asset['id'],
            'font_size':18,'color':'#ffffff','align':'center','bold':False,
            'outline_color':'#000000','outline_width':1}
        project['layers'].extend([
            {**base,'id':'title','type':'text','name':'Title',**typography,'binding':'title','text':'Sample forbidden'},
            {**base,'id':'subtitle','type':'subtitle','name':'Subtitle',**typography,'y':267,'height':45,
                'words_per_group':2,'max_lines':2,'highlight_color':'#bcff32','background':'#00000000'},
            {**base,'id':'logo','type':'image','name':'Logo','x':65,'y':125,'width':40,'height':40,
                'asset_id':logo['id'],'fit':'contain','timing':{'mode':'start','start':0,'duration':.6}},
            {**base,'id':'closing','type':'rect','name':'Closing','x':10,'y':225,'width':160,'height':20,
                'color':'#ffff00','border_color':'#ffff00','border_width':0,
                'timing':{'mode':'end','start':0,'duration':.7}},
        ])
        project['preview']['title'] = 'Sample title only'
        saved = self.ok(self.api.editor_save_project(project))['project']
        render = self.ok(self.api.editor_start_render(saved['id']))['render']
        deadline = time.monotonic()+90
        while time.monotonic()<deadline:
            render = self.ok(self.api.editor_get_render(render['id']))['render']
            if render['status'] in ('completed','failed','cancelled'):
                break
            time.sleep(.1)
        self.assertEqual(render['status'],'completed',render)
        self.assertAlmostEqual(probe_media(render['path'], self.ffmpeg)['duration'],2.8,delta=.12)
        first = self.frame(render['path'],.2)
        self.assertGreater(first.getpixel((80,140))[0],200, 'Uploaded logo appears at its position')
        # Pad is transparent, retaining the design canvas background rather than black.
        pad = self.frame(render['path'],1.2).getpixel((80,80))
        self.assertGreater(pad[2],10)
        self.assertLess(pad[2],80)
        published = self.ok(self.api.editor_publish_project(saved['id']))
        with zipfile.ZipFile(published['path']) as archive:
            model = json.loads(archive.read('design.json'))
            self.assertNotIn('preview',model)
            self.assertFalse(any(name.endswith(('.mp4','.srt','.wav')) for name in archive.namelist()))
            self.assertNotIn(str(short),json.dumps(model))
        preset_id = published['preset']['id']
        directory = template_directory(preset_id)
        shutil.rmtree(self.root / 'drafts')
        short.unlink();srt.unlink();image_path.unlink()
        preset = resolve_preset(preset_id)
        self.assertEqual(preset['external_template']['engine'],'design')
        output = self.root / 'independent.mp4'
        words = [{'word':'NARASI','start':0,'end':1}, {'word':'BARU','start':1,'end':2}]
        metadata = render_design(load_design(directory), directory, long, output,
            title='REAL TITLE', subtitle_words=words, ffmpeg=self.ffmpeg)
        info = probe_media(output,self.ffmpeg)
        self.assertAlmostEqual(info['duration'],37.2,delta=.12)
        self.assertTrue(info['has_audio']);self.assertFalse(metadata['editor_required'])
        self.assertEqual((info['width'],info['height']),(180,320))
        yellow = self.frame(output,37).getpixel((80,235))
        self.assertGreater(yellow[0],200);self.assertGreater(yellow[1],200);self.assertLess(yellow[2],60)
        blue = self.frame(output,20).getpixel((80,150))
        self.assertGreater(blue[2],200);self.assertLess(blue[0],70)
        active = self.frame(output,.4).crop((10,267,170,312))
        pixels = active.tobytes()
        self.assertTrue(any(g>130 and r>80 and b<100 for r,g,b in zip(pixels[0::3],pixels[1::3],pixels[2::3])),
            'Active subtitle uses selected green instead of silently falling back to white')

    def test_clipper_applies_native_caption_once_and_required_campaign_music(self):
        from clipper_core import AutoClipperCore
        from services.campaigns import normalize_campaign
        from services.editing import fingerprint_source
        from services.template_selection import choose_template
        source = self.source(2.8, 'production source.mp4')
        music = self.root / 'music.wav'
        subprocess.run([self.ffmpeg,'-y','-v','error','-f','lavfi','-i',
            'sine=frequency=180:sample_rate=48000:duration=2.8',str(music)],
            check=True,capture_output=True,timeout=30)
        project = self.ok(self.api.editor_create_project({'name':'Campaign native','ratio':'1:1'}))['project']
        added = self.ok(self.api.editor_add_asset(project['id'],str(Path(__file__).resolve().parents[1]/'assets/fonts/PodcastBlack.ttf'),'font'))
        project,font = added['project'],added['asset']
        project['canvas'].update(width=160,height=160,fps=10)
        project['layers'][0].update(width=160,height=160,fit='contain',framing='fit')
        project['layers'].append({'id':'captions','type':'subtitle','name':'Custom captions','x':5,'y':120,
            'width':150,'height':35,'font_family':font['font_family'],'font_asset_id':font['id'],
            'font_size':16,'color':'#ffffff','highlight_color':'#bcff32','background':'#00000000',
            'align':'center','bold':False,'outline_color':'#000000','outline_width':1,
            'words_per_group':2,'max_lines':2,'timing':{'mode':'full','start':0,'duration':4}})
        self.ok(self.api.editor_save_project(project))
        published = self.ok(self.api.editor_publish_project(project['id']))
        campaign = normalize_campaign({'id':'test-campaign','name':'Native test','brief':{'durasi_min':1,'durasi_max':4},
            'editing':{'preset_id':published['preset']['id'],'music':{'policy':'local','path':str(music),'volume':.18}}})
        core = AutoClipperCore(client=None,output_dir=self.root/'clips',log_callback=lambda *_:None)
        core.ffmpeg_path = self.ffmpeg
        core.campaign_config = campaign
        core.source_analysis = fingerprint_source(str(source))
        core._caption_lock = threading.Lock()
        caption_calls = []
        words = [SimpleNamespace(word='UCAPAN',start=.1,end=1.3),SimpleNamespace(word='UTUH',start=1.3,end=2.7)]
        def captions(audio):
            self.assertTrue(Path(audio).is_file());caption_calls.append(audio)
            return SimpleNamespace(words=words,segments=[])
        core._whisper_transcribe_words = captions
        core.add_captions_api_with_progress = lambda *_args,**_kw:self.fail('Native captions must not be restyled afterwards')
        def base(*args,**kwargs):
            self.assertFalse(args[7], 'Source must not be cropped before the native video box')
            target = core.output_dir/'clip-001'/'master.mp4'
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
        core._render_clip_base = base
        highlight = {'start_time':'00:00:00,000','end_time':'00:00:02,800','duration_seconds':2.8,'title':'Production title',
            'editing_template':choose_template(campaign,'normal-job:1')}
        try:
            directory = core.process_clip(str(source),highlight,1,1,campaign_id=campaign['id'])
            metadata = json.loads((directory/'data.json').read_text(encoding='utf8'))
            self.assertEqual(len(caption_calls),1)
            self.assertEqual(metadata['template_render']['engine'],'design')
            self.assertEqual(metadata['editing_template']['preset_id'],published['preset']['id'])
            self.assertTrue(metadata['has_captions']);self.assertTrue(metadata['music']['mixed'])
            self.assertEqual(metadata['music']['volume'],.18)
            self.assertTrue(metadata['final_sha256']);self.assertEqual(metadata['blockers'],[])
            info = probe_media(directory/'master.mp4',self.ffmpeg)
            self.assertEqual((info['width'],info['height']),(160,160));self.assertTrue(info['has_audio'])
            self.assertAlmostEqual(info['duration'],2.8,delta=.12)
        finally:
            core.cleanup()

    def test_archiving_keeps_selected_versions_visible_in_existing_campaign_only(self):
        from services.workflow import WorkflowMixin
        project = self.ok(self.api.editor_create_project({'name':'Archived template'}))['project']
        published = self.ok(self.api.editor_publish_project(project['id']))
        preset_id = published['preset']['id']
        self.ok(self.api.editor_archive_project(project['id'],True))
        class CatalogHarness(WorkflowMixin):
            def _get_cfg(self):
                return {'campaigns':[{'id':'existing','editing':{'template_pool':[
                    {'preset_id':preset_id,'enabled':True,'weight':50}]}}]}
        catalog = CatalogHarness()
        new_choices = self.ok(catalog.get_campaign_editing_presets())['presets']
        self.assertNotIn(preset_id,[item['id'] for item in new_choices])
        old_choices = self.ok(catalog.get_campaign_editing_presets('existing'))['presets']
        retained = next(item for item in old_choices if item['id']==preset_id)
        self.assertTrue(retained['archived'])
        self.assertEqual(resolve_preset(preset_id)['id'],preset_id)


if __name__ == '__main__':
    unittest.main()
