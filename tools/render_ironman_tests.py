"""Render, review and register the three Ironman tests in SSR_CLIPPER."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.achievement_montage import prepare_scene, frame_scene, make_hook, render_recipe, validate_recipe
from services.editing import probe_media, file_sha256
from services.storage import atomic_json, utc_now
from setup_ironman_campaign import api_instance
from utils.helpers import get_ffmpeg_path

OUT = ROOT / 'output/ironman-tests-20261013'
cv2.setNumThreads(2)


def preview(recipes):
    cache = OUT / 'clips/scene-cache'
    cache.mkdir(parents=True, exist_ok=True)
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 17)
    for path in recipes:
        recipe = json.loads(path.read_text(encoding='utf-8'))
        validate_recipe(recipe)
        pictures = []
        for i, scene in enumerate(recipe['scenes']):
            source = prepare_scene(scene, cache, get_ffmpeg_path())
            if source.suffix.lower() in {'.png', '.jpg', '.jpeg'}:
                frame = cv2.imread(str(source))
            else:
                capture = cv2.VideoCapture(str(source))
                capture.set(cv2.CAP_PROP_POS_MSEC, scene['duration'] * 500)
                ok, frame = capture.read()
                capture.release()
                if not ok:
                    raise ValueError('Scene preview not decodable')
            frame = frame_scene(frame, scene, .5, 1080, 1920)
            if i == 0:
                hook = make_hook(recipe['hook'], 1080, 1920)
                alpha = hook[:, :, 3:4] / 255
                frame = (frame * (1-alpha) + hook[:, :, :3][:, :, ::-1] * alpha).astype(np.uint8)
                cv2.imwrite(str(OUT / (recipe['id'] + '-hook.jpg')), frame)
            picture = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            picture.thumbnail((270, 480))
            pictures.append((scene, picture))
            print(recipe['id'], 'prepared', i + 1, flush=True)
        sheet = Image.new('RGB', (1080, 525 * ((len(pictures) + 3) // 4)), '#202020')
        draw = ImageDraw.Draw(sheet)
        for n, (scene, pic) in enumerate(pictures):
            x, y = n % 4 * 270, n // 4 * 525
            sheet.paste(pic, (x, y))
            draw.text((x+3,y+482), str(n+1)+' · '+scene['name'][:26], font=font, fill='white')
            draw.text((x+3,y+503), str(scene['duration'])+'s · '+scene.get('fit','fill'), font=font, fill='white')
        sheet.save(OUT / (recipe['id'] + '-storyboard.jpg'))


def render(recipes):
    for i, path in enumerate(recipes, 1):
        destination = OUT / 'clips' / f'clip-{i:03}' / 'master.mp4'
        data = destination.parent / 'data.json'
        if destination.exists() and data.exists():
            meta = json.loads(data.read_text(encoding='utf-8'))
            if meta.get('recipe_sha256') == file_sha256(path) and meta.get('final_sha256') == file_sha256(destination):
                print('Existing verified render', i, flush=True)
                continue
        render_recipe(path, destination)


def register():
    api = api_instance()
    campaign = next(c for c in api._get_cfg()['campaigns'] if c['id'] == 'camp_8d3c32dfe5b9')
    job = {'id': 'job_ironman_tests_20261013', 'campaign_id': campaign['id'], 'campaign': campaign,
           'title': 'Ironman · 3 test referensi dan film burn', 'source': 'https://www.youtube.com/@bevanpramudt',
           'status': 'completed', 'created_at': utc_now(), 'clips': [], 'progress': 1}
    clips = []
    for i in range(1,4):
        directory = OUT / 'clips' / f'clip-{i:03}'
        metadata = json.loads((directory / 'data.json').read_text(encoding='utf-8'))
        recipe = json.loads(Path(metadata['recipe']).read_text(encoding='utf-8'))
        media = probe_media(directory / 'master.mp4', get_ffmpeg_path())
        if media['width'] != 1080 or media['height'] != 1920 or abs(media['duration']-metadata['duration_seconds']) > .1:
            raise ValueError('Unexpected render dimensions/duration')
        credit = recipe['music']['attribution']
        caption = (recipe['description'] + '\n\n@bevanpramudt\n'
                   + ' '.join(campaign['brief']['hashtags']) + '\n\nMusik: '
                   + credit['name'] + ' — ' + credit['artist'] + '\n' + credit['source_url']
                   + '\nCC BY 3.0: ' + credit['license_ccurl'] + '\nMusik dipotong, dinormalisasi, dan diberi fade.')
        metadata.update(campaign_id=campaign['id'], campaign_version_id=campaign['version_id'],
                        campaign_snapshot=campaign, job_id=job['id'], source_url=job['source'],
                        caption=caption, captions={'instagram': caption, 'tiktok': caption},
                        has_captions=False, has_hook=True, created_at=utc_now(),
                        blockers=[], warnings=[], render_status='done',
                        reviewed_by='agent_visual_and_media_QA_for_user_requested_test_upload')
        thumbnail = directory / 'thumbnail.jpg'
        subprocess.run([get_ffmpeg_path(), '-v', 'error', '-ss', '1', '-i', metadata['final_path'],
                        '-frames:v', '1', '-vf', 'scale=270:480', '-y', str(thumbnail)], check=True)
        metadata['thumbnail'] = str(thumbnail)
        clip = api._register_clip(metadata['final_path'], metadata)
        metadata['clip_id'] = clip['id']
        metadata['revision_id'] = clip['revision_id']
        atomic_json(directory / 'data.json', metadata)
        clips.append({'clip_id': clip['id'], 'title': clip['title'], 'path': clip['path'], 'duration': media['duration']})
        job['clips'].append({'index': i, 'status': 'done', 'path': clip['path']})
    api._get_store().put('job', job['id'], job)
    atomic_json(OUT / 'registered-clips.json', clips)
    print(json.dumps(clips, ensure_ascii=True), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['preview', 'render', 'register'])
    args = parser.parse_args()
    recipes = sorted((OUT / 'recipes').glob('ironman-test-*.json'))
    {'preview': lambda: preview(recipes), 'render': lambda: render(recipes), 'register': register}[args.action]()
