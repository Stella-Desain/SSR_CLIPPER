"""Build three editable reference-based recipes from reviewed official assets."""
import copy
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.editing import file_sha256
from services.storage import atomic_json
from utils.helpers import get_ffmpeg_path

OUT = ROOT / 'output/ironman-tests-20261013'
ASSETS = OUT / 'assets'
REF = ROOT / 'output/ironman-reference-20261013'


def main():
    assets = json.loads((OUT / 'assets-index.json').read_text(encoding='utf-8'))
    music = json.loads((OUT / 'music-selected.json').read_text(encoding='utf-8'))
    by_name = {a['title']: a for a in assets}
    vlog = ASSETS / 'official-ironman-vlog.mp4'
    # Reviewed smile with open eyes; avoid freezing a mid-speech close-up.
    snapshot = ASSETS / 'bevan-finisher-smile-746_2.png'
    if not snapshot.exists():
        subprocess.run([get_ffmpeg_path(), '-v', 'error', '-ss', '746.2', '-i', str(vlog),
                        '-frames:v', '1', '-y', str(snapshot)], check=True)
    vlog_hash = file_sha256(vlog)
    finish_freeze = ASSETS / 'bevan-finish-close-7_8.png'
    if not finish_freeze.exists():
        filters = 'zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=mobius:desat=0,zscale=t=bt709:m=bt709:r=tv'
        subprocess.run([get_ffmpeg_path(), '-v', 'error', '-ss', '7.8', '-i', by_name['IMG_1849.MOV']['path'],
                        '-vf', filters, '-frames:v', '1', '-y', str(finish_freeze)], check=True)

    def raw(name, start, duration, group, fit='fill', anchor=None, **extra):
        a = by_name[name]
        return {'path': a['path'], 'source_id': a['sha256'], 'source_url': a['url'],
                'name': name, 'source_start': start, 'duration': duration,
                'visual_group': group, 'fit': fit, 'anchor': anchor or [.5, .5], **extra}

    def yt(start, duration, group, anchor=None, **extra):
        return {'path': str(vlog), 'source_id': vlog_hash,
                'source_url': 'https://www.youtube.com/watch?v=u9d14ssEc0c',
                'name': 'Vlog Ironman resmi Bevan', 'source_start': start, 'duration': duration,
                'visual_group': group, 'fit': 'fill', 'anchor': anchor or [.5, .5], **extra}

    def photo(name, duration, **extra):
        p = REF / 'official-assets' / name
        return {'path': str(p), 'source_id': file_sha256(p),
                'source_url': 'https://drive.google.com/drive/folders/17spOI2GBEbuevxka4NTd5hEZz2Uq3UCL',
                'name': 'Foto resmi Bevan · ' + name, 'duration': duration,
                'visual_group': 'finisher_ui_flag_same_session', 'fit': 'fill', **extra}

    base = {'schema': 'ssr-achievement-montage', 'version': 1,
            'constraints': {'hook_required_word': 'IRONMAN', 'min_hook_seconds': 5, 'min_seconds': 15, 'max_seconds': 180},
            'canvas': {'width': 1080, 'height': 1920, 'fps': 30},
            'cta': {'required': False, 'enabled': False},
            'reference_role': 'style_only', 'finished_clipper_reference_used_as_source': False}
    dynamic_hook = {'duration': 5, 'bounds': [.083333, .655273, .835069, .125],
                    'background': '#ffffff', 'color': '#000000', 'accent': '#e31327',
                    'font_path': 'C:/Windows/Fonts/ariblk.ttf', 'font_size': 62,
                    'alignment': 'center', 'red_rule': True, 'entry_seconds': .18}
    def soundtrack(track_id, start):
        m = next(m for m in music if m['id'] == track_id)
        return {'path': m['local_path'], 'start': start, 'target_lufs': -16,
                'attribution': {'name': m['name'], 'artist': m['artist_name'],
                                'source_url': m['shareurl'], 'license_ccurl': m['license_ccurl'],
                                'changes': 'excerpt, loudness normalization and fades'}}

    recipes = [
        {**copy.deepcopy(base), 'id': 'ironman-test-01', 'variant': 'achievement_dynamic',
         'title': 'Ironman · Dinamis', 'description': 'Di usia 21 tahun, Bevan Pramudito menuntaskan IRONMAN 70.3. Proses latihan dan momen pencapaiannya.',
         'hook': {**dynamic_hook, 'text': 'MAHASISWA UI INI\nTAKLUKKAN IRONMAN\nDI USIA 21 TAHUN'},
         'music': soundtrack('367026', 32),
         'scenes': [yt(250, 2.5, 'coastal_walk_identity', [.42, .5]),
                    yt(424.5, 2.5, 'helmet_preparation', [.56, .5]),
                    raw('09c5394a-46ed-4ab2-9bd7-107908152833.mp4', 10, 2, 'pool_april9_side', fit='contain'),
                    raw('Bevan Struggle 13.mp4', 1, 2, 'indoor_bike_trainer', fit='contain'),
                    raw('IMG_1781.MOV', 13, 2, 'swim_start_black_wave'),
                    raw('IMG_1830.MOV', 10, 3, 'race_cycling_close', fit='contain'),
                    raw('IMG_1833.MOV', 1.5, 3, 'race_running_bridge', fit='contain'),
                    photo('IMG_0939.png', 3, payoff_wobble=1.7)],
         'transitions': [{'at': 9, 'duration': .4, 'intensity': .8, 'seed': 1},
                         {'at': 17, 'duration': .4, 'intensity': .75, 'seed': 2}]},
        {**copy.deepcopy(base), 'id': 'ironman-test-02', 'variant': 'achievement_editorial',
         'title': 'Ironman · Editorial', 'description': 'Bikin bangga! Perjalanan latihan hingga garis finish IRONMAN 70.3 Bevan Pramudito.',
         'hook': {'duration': 5, 'bounds': [.022222, .435156, .952778, .270312],
                  'text': 'Bikin bangga!\nBevan menuntaskan\nIRONMAN 70.3\ndi usia 21 tahun.',
                  'background': '#ffffff', 'color': '#111111', 'accent': '#e31327',
                  'accent_word': 'IRONMAN', 'font_path': 'C:/Windows/Fonts/arial.ttf',
                  'font_size': 70, 'alignment': 'left', 'entry_seconds': .15},
         'music': soundtrack('23561', 48),
         'scenes': [photo('IMG_0937.png', 5),
                    raw('IMG_1747.MOV', 7, 3, 'race_morning_parking_preparation', fit='contain'),
                    raw('7aed9602-4cfb-4b80-bf54-28f8c30d17d2.mp4', 4, 2.5, 'pool_first_swim_front', fit='contain'),
                    raw('Bevan Running new 30.mp4', .3, 2.5, 'training_track_running', fit='contain'),
                    raw('IMG_1573.MOV', 8, 3, 'cycle_training_road', fit='contain'),
                    yt(658.5, 3, 'race_swim_face', fit='contain'),
                    raw('IMG_1849.MOV', 19, 7, 'race_finish_corridor', fit='contain')],
         'transitions': [{'at': 16, 'duration': .5, 'intensity': .55, 'seed': 4}]},
        {**copy.deepcopy(base), 'id': 'ironman-test-03', 'variant': 'achievement_dynamic_film_burn',
         'title': 'Ironman · Film Burn', 'description': 'Dari latihan ke garis finish. Perjalanan Bevan Pramudito menuntaskan IRONMAN 70.3.',
         'hook': {**dynamic_hook, 'text': 'BEVAN & IRONMAN\nDARI LATIHAN\nKE GARIS FINISH'},
         'music': soundtrack('367026', 64),
         'scenes': [raw('IMG_1745.MOV', 2, 5, 'race_morning_parking_identity', fit='contain'),
                    raw('Bevan Struggle 4.mp4', .5, 2, 'running_shoes_ground', fit='contain'),
                    raw('665e3435-e656-4622-aa4f-81d913b27030.mp4', 13, 2, 'pool_april9_close'),
                    raw('IMG_1574.MOV', .2, 2, 'cycle_training_departure', fit='contain'),
                    yt(694, 2, 'open_water_practice', fit='contain'),
                    raw('IMG_1790.MOV', 6, 2, 'swim_start_pink_wave'),
                    yt(759.5, 3, 'finisher_medal_helmet_face', [.37, .5]),
                    {'path': str(snapshot), 'source_id': file_sha256(snapshot),
                     'source_url': 'https://www.youtube.com/watch?v=u9d14ssEc0c&t=746s',
                     'derived_from_sha256': vlog_hash, 'freeze_frame_from_seconds': 746.2,
                     'name': 'Bevan tersenyum setelah finish · frame resmi', 'duration': 4,
                     'visual_group': 'finisher_smile_white_cap', 'fit': 'fill', 'anchor': [.445, .65]}],
         'transitions': [{'at': 7, 'duration': .5, 'intensity': 1, 'seed': 7},
                         {'at': 11, 'duration': .5, 'intensity': .95, 'seed': 8},
                         {'at': 18, 'duration': .5, 'intensity': .9, 'seed': 9}]}
    ]
    folder = OUT / 'recipes'
    folder.mkdir(exist_ok=True)
    editorial = recipes[1]
    editorial['scenes'][-1]['duration'] = 5
    finish_asset = by_name['IMG_1849.MOV']
    editorial['scenes'].append({'path': str(finish_freeze), 'source_id': file_sha256(finish_freeze),
        'source_url': finish_asset['url'], 'derived_from_source_id': finish_asset['sha256'],
        'freeze_frame_from_seconds': 7.8, 'name': 'Bevan di finish · freeze frame resmi',
        'duration': 2, 'visual_group': 'race_finish_close_freeze', 'fit': 'inset_fill', 'anchor': [.52,.5]})
    for recipe in recipes:
        for scene in recipe['scenes']:
            if scene.get('fit') == 'contain':
                scene['fit'] = 'inset_fill' if recipe['variant'] == 'achievement_editorial' else 'fill'
            if recipe['variant'] == 'achievement_editorial':
                scene['fit'] = 'inset_fill'
            if scene['name'] in {'IMG_1745.MOV', 'IMG_1747.MOV'}:
                scene['anchor'] = [.55, .5]
            if scene['name'] == 'IMG_1830.MOV':
                scene.update(anchor=[.40,.5], anchor_end=[.24,.5])
                scene['anchor_path'] = [[0,.40,.5],[.4,.35,.5],[.8,.26,.5],[1.2,.17,.5],
                                        [1.6,.33,.5],[2,.40,.5],[2.4,.50,.5],[2.9,.58,.5],[3,.59,.5]]
            if scene['name'] == 'IMG_1833.MOV':
                scene.update(anchor=[.42,.5], anchor_end=[.36,.5])
            if scene['name'] == 'IMG_1849.MOV':
                scene.update(source_start=3, anchor=[.55,.5], anchor_end=[.6,.5])
        if recipe['id'] == 'ironman-test-01':
            recipe['scenes'][3]['visual_group'] = 'bicycle_preparation_lift'
        if recipe['id'] == 'ironman-test-02':
            recipe['scenes'][0].update(zoom=1.25, anchor=[.5,.62])
            recipe['scenes'][5].update(source_start=680, anchor=[.64,.5], anchor_end=[.6,.5])
        if recipe['id'] == 'ironman-test-03':
            recipe['scenes'][-1].update(anchor=[.445,.65], zoom=1.12, gamma=1.18)
        atomic_json(folder / (recipe['id'] + '.json'), recipe)
    templates = OUT / 'templates'
    templates.mkdir(exist_ok=True)
    for recipe in recipes[:2]:
        template = {k: copy.deepcopy(recipe[k]) for k in ['schema', 'version', 'canvas', 'hook', 'constraints', 'cta']}
        template['schema'] = 'ssr-achievement-montage-template'
        template.update(id=recipe['variant'], renderer='services.achievement_montage.render_recipe',
                        editable_fields=['hook', 'canvas', 'constraints', 'scenes', 'music', 'transitions', 'cta'],
                        scene_policy={'same_source_range_within_clip': False, 'requires_official_source': True})
        atomic_json(templates / (recipe['variant'] + '.json'), template)
    print('Three recipes and two reusable template definitions saved')


if __name__ == '__main__':
    main()
