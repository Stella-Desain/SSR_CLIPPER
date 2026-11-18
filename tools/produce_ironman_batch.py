"""Produce six reviewed Ironman drafts with original voice and varied source ranges."""
import argparse
import copy
import json
import subprocess
import sys
from pathlib import Path

import cv2
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.achievement_montage import (validate_recipe, prepare_scene, frame_scene,
    make_hook, render_recipe)
from services.montage_layers import prepare_text_layers, apply_text_layers
from services.editing import file_sha256, probe_media
from services.storage import atomic_json, utc_now
from utils.helpers import get_ffmpeg_path

OLD = ROOT / 'output/ironman-tests-20261013'
OUT = ROOT / 'output/ironman-batch-20261014'
VLOG = OLD / 'assets/official-ironman-vlog.mp4'
URL = 'https://www.youtube.com/watch?v=u9d14ssEc0c'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def build():
    by_name = {a['title']: a for a in read(OLD / 'assets-index.json')}
    vlog_hash = file_sha256(VLOG)
    def raw(name, start, duration, group, **extra):
        a = by_name[name]
        return dict(path=a['path'], source_id=a['sha256'], source_url=a['url'], name=name,
            source_start=start, duration=duration, visual_group=group, fit='fill', anchor=[.5,.5], **extra)
    def yt(start, duration, group, anchor=None, **extra):
        return dict(path=str(VLOG), source_id=vlog_hash, source_url=URL,
            name='Vlog resmi Bevan', source_start=start, duration=duration,
            visual_group=group, fit='fill', anchor=anchor or [.5,.5], crop_bottom=.09, **extra)
    def image(path, duration, group, url, **extra):
        return dict(path=str(path), source_id=file_sha256(path), source_url=url,
            name=path.stem, duration=duration, visual_group=group, fit='fill', **extra)
    def photo(name, duration, **extra):
        return image(ROOT / 'output/ironman-reference-20261013/official-assets' / name,
            duration, 'finisher_ui_flag_same_session',
            'https://drive.google.com/drive/folders/17spOI2GBEbuevxka4NTd5hEZz2Uq3UCL', **extra)
    def voice(key, ranges, duration):
        return dict(path=str(OUT / 'audio' / f'voice-{key}.mp3'), duration=duration,
            source_id=vlog_hash, source_url=URL, source_ranges=ranges,
            provenance='Original Bevan audio; source ranges joined with 5–10 ms edge fades')
    music_a = read(OLD / 'recipes/ironman-test-03.json')['music']
    music_b = read(OLD / 'recipes/ironman-test-02.json')['music']
    hook = dict(duration=5, bounds=[.07,.065,.86,.10], background='#ffffff',
        color='#111111', accent='#e31327', font_path='C:/Windows/Fonts/ariblk.ttf',
        font_size=62, alignment='center', red_rule=True, entry_seconds=.15, exit_seconds=.12)
    base = dict(schema='ssr-achievement-montage', version=1,
        canvas=dict(width=1080,height=1920,fps=30),
        constraints=dict(hook_required_word='IRONMAN',min_hook_seconds=5,min_seconds=15,max_seconds=180),
        cta=dict(required=False,enabled=False),reference_role='style_only',
        finished_clipper_reference_used_as_source=False)
    finish_run = image(OUT/'assets/finish-run-8_0.png', 5,
        'race_finish_runner_profile', by_name['IMG_1849.MOV']['url'],
        derived_from_source_id=by_name['IMG_1849.MOV']['sha256'],freeze_frame_from_seconds=8,
        anchor=[.46,.5])
    finish_arch = image(OUT/'assets/finish-arch-721.png',3,'race_finish_arch_proof',URL,
        derived_from_source_id=vlog_hash,freeze_frame_from_seconds=721,anchor=[.57,.5])
    smile = copy.deepcopy(read(OLD/'revisions/film-burn-v2/recipe.json')['scenes'][-1])
    smile['duration'] = 3
    race_hero = image(OUT/'assets/race-hero-smile-675_3.png',3,'race_day_hero_smile',URL,
        derived_from_source_id=vlog_hash,freeze_frame_from_seconds=675.3,
        anchor=[.55,.5],gamma=1.1)
    specs = [
        dict(title='5 bulan persiapan IRONMAN', variant='achievement_story_v2',
            hook='5 BULAN PERSIAPAN\nUNTUK IRONMAN 70.3',
            description='Bevan menceritakan lima bulan persiapannya sebelum start IRONMAN 70.3. Perjalanan itu berakhir dengan pencapaian sebagai finisher.',
            narration=voice('01',[(667.3,16.9)],16.9),
            scenes=[yt(667.3,9,'five_months_original_voice',[.55,.5],anchor_end=[.56,.5],gamma=1.08),
                    raw('IMG_1781.MOV',25,2,'race_swim_start_new_range'),
                    yt(678.3,1.7,'pre_start_air_temperature',[.6,.5],gamma=1.08),
                    yt(689,3,'open_water_context_new_range'),
                    yt(683,1.2,'pre_start_complete_sentence',[.6,.5],gamma=1.08),
                    photo('IMG_0939.png',3,anchor=[.5,.5])],music=music_a,music_start=8,
            transitions=[dict(at=16.9,duration=.3,intensity=.5,seed=31)]),
        dict(title='Tes air sebelum IRONMAN',variant='achievement_story_v2',
            hook='SEBELUM IRONMAN\nBEVAN TES AIR DULU',
            description='Mengenali kondisi air menjadi bagian persiapan Bevan sebelum IRONMAN 70.3. Fokus pada proses dan persiapan lomba.',
            narration=voice('02',[(475.1,8.7666666667),(487.5666666667,7.0333333333)],15.8),
            scenes=[yt(475.1,5,'test_swim_original_voice',[.69,.5],anchor_end=[.59,.5],gamma=1.12),
                    raw('IMG_1814.MOV',3,2,'sea_temperature_context'),
                    yt(482.1,1.7666666667,'test_swim_explanation',[.59,.5],gamma=1.12),
                    yt(487.5666666667,7.0333333333,'test_swim_complete_sentence',[.64,.5],anchor_end=[.65,.5],gamma=1.12),
                    photo('IMG_0937.png',3,anchor=[.5,.6],zoom=1.18)],
            music=music_b,music_start=90,transitions=[]),
        dict(title='Sepeda dicek sebelum IRONMAN',variant='achievement_story_v2',
            hook='DETAIL PERSIAPAN\nSEBELUM IRONMAN',
            description='Bevan memastikan sepedanya dicek sebelum masuk area transition IRONMAN. Persiapan kecil menjadi bagian perjalanan menuntaskan lomba.',
            narration=voice('03',[(573,5.9)],5.9),
            scenes=[yt(573,5.9,'bike_mechanic_original_voice',[.51,.5],anchor_end=[.54,.5]),
                    raw('IMG_1572.MOV',2.2,3.1,'cycle_training_front_new_take'),
                    raw('IMG_1561.MOV',6,2,'bike_transport_preparation'),finish_run],
            music=music_a,music_start=96,
            transitions=[dict(at=11,duration=.3,intensity=.55,seed=32)]),
        dict(title='Perjalanan ke IRONMAN pertama',variant='achievement_story_v2',
            hook='IRONMAN 70.3 PERTAMA\nPERJALANAN BEVAN',
            description='Persiapan, perjalanan, latihan, hingga garis finish IRONMAN 70.3 pertama Bevan Pramudito.',
            narration=voice('04',[(91.1,5.2333333333)],5.2333333333),
            scenes=[yt(91.1,5.2333333333,'first_ironman_original_voice',[.53,.5],anchor_end=[.52,.5]),
                    yt(149,2,'commercial_flight_cabin'),
                    yt(291,2,'arrival_walk_sunshine_coast',[.63,.5]),
                    raw('Bevan Running new 5.mp4',.5,2.5,'warmup_before_run'),
                    raw('IMG_1573.MOV',1.5,3,'cycle_training_early_range'),
                    yt(719.8,1.2,'finish_arrival_profile',[.25,.5]),finish_arch],
            music=music_b,music_start=112,
            transitions=[dict(at=15.9333333333,duration=.3,intensity=.5,seed=33)]),
        dict(title='Latihan menuju IRONMAN',variant='achievement_dynamic_v2',
            hook='PROSES DI BALIK\nPENCAPAIAN IRONMAN',
            description='Pemanasan, latihan renang, bersepeda, dan pemulihan menjadi bagian proses Bevan menuju pencapaian IRONMAN 70.3.',
            scenes=[raw('Bevan Running new 20.mp4',.4,5,'hydration_training_close'),
                    raw('Bevan Struggle 34.mp4',2,3,'warmup_mobility'),
                    raw('Bevan Running new 1.mp4',.2,2.7,'warmup_stretching'),
                    raw('66a70715-4fd4-44a9-9e65-bde62c931e01.mp4',4,3,'pool_training_unused_take'),
                    raw('IMG_1573.MOV',14,3.3,'cycle_training_late_range'),smile],
            music=music_b,music_start=20,
            transitions=[dict(at=17,duration=.3,intensity=.55,seed=34)]),
        dict(title='IRONMAN race day · Jedag Jedug',variant='achievement_jedag_jedug_v2',
            hook='BEVAN MENUNTASKAN\nIRONMAN 70.3',
            description='Potret persiapan dan hari lomba Bevan Pramudito dalam perjalanan menuntaskan IRONMAN 70.3.',
            scenes=[yt(631.5,5.0666666667,'race_morning_identity_new_range',[.6,.5],anchor_end=[.58,.5],gamma=1.1),
                    raw('Bevan Running new 11.mp4',.1,3,'running_track_unused_take'),
                    raw('7aed9602-4cfb-4b80-bf54-28f8c30d17d2.mp4',.2,2.5,'pool_top_down_unused_range'),
                    yt(692,2,'open_water_warmup_new_range',[.44,.5]),
                    raw('IMG_1561.MOV',16,2.5,'bike_bag_before_race_new_range'),
                    raw('IMG_1833.MOV',4.5,2.5,'race_run_departure_new_range'),race_hero],
            music=music_a,music_start=64,
            transitions=[dict(at=17.5666666667,duration=.3,intensity=.6,seed=35)])]
    source_words = []
    for event in read(OUT/'source-captions.id.json3')['events']:
        for segment in event.get('segs', []):
            word = segment.get('utf8','').strip()
            if not word or word.startswith('['):
                continue
            source_words.append((event['tStartMs']/1000 + segment.get('tOffsetMs',0)/1000, word))
    source_words.sort()
    recipes = []
    for index,spec in enumerate(specs,1):
        recipe = {**copy.deepcopy(base), **copy.deepcopy(spec)}
        recipe['id'] = f'ironman-batch-20261014-{index:02}'
        recipe['hook'] = {**copy.deepcopy(hook), 'text':spec['hook']}
        recipe['music']['start'] = recipe.pop('music_start')
        recipe['text_overlays'] = []
        # Framing reviewed against the actual person, not the asset filename.
        for scene in recipe['scenes']:
            if index <= 4 and scene['path'] == str(VLOG) and scene.get('source_start', 9999) < 700:
                if 'original_voice' in scene['visual_group'] or 'pre_start' in scene['visual_group'] or 'test_swim' in scene['visual_group']:
                    scene['fit'] = 'context'
            if scene['name'] == 'Bevan Running new 20.mp4':
                scene.update(anchor=[.27,.5],anchor_end=[.32,.5])
            if scene['name'] == 'Bevan Struggle 34.mp4':
                scene.update(anchor=[.67,.5],anchor_end=[.65,.5])
            if scene['name'] == 'Bevan Running new 1.mp4':
                scene.update(anchor=[.27,.5])
            if scene['name'] == 'Bevan Running new 5.mp4':
                scene.update(anchor=[.36,.5])
            if scene['name'] == 'IMG_1572.MOV':
                scene.update(anchor=[.4,.5],anchor_end=[.36,.5])
            if scene.get('visual_group') == 'bike_mechanic_original_voice':
                scene.update(anchor=[.45,.5],anchor_end=[.49,.5])
            if scene.get('visual_group') == 'five_months_original_voice':
                scene.update(anchor=[.56,.5],anchor_end=[.58,.5])
            if scene.get('visual_group') == 'pre_start_complete_sentence':
                scene.update(anchor=[.39,.5])
        if recipe.get('narration'):
            words, at = [], 0
            for start,length in recipe['narration']['source_ranges']:
                for timestamp,word in source_words:
                    if start <= timestamp < start+length:
                        if index == 3 and 575.1 <= timestamp < 576.2:
                            continue  # Ambiguous ASR bike-mechanic term; do not invent a quote.
                        word = word.strip('.,!?')
                        if word.lower() == 'us':
                            continue  # Spurious token in the official ASR, not a spoken word.
                        word = {'Brisband':'Brisbane','test':'tes'}.get(word,word)
                        words.append((at+timestamp-start,word.upper()))
                at += length
            for i in range(0,len(words),2):
                group=words[i:i+2];start=group[0][0]
                end=min(recipe['narration']['duration'],group[-1][0]+.42,
                        words[i+2][0] if i+2<len(words) else recipe['narration']['duration'])
                if end > start:
                    recipe['text_overlays'].append(dict(start=start,duration=end-start,
                        text=' '.join(w[1] for w in group),position=[.5,.79],font_size=74,
                        color='#ffffff',stroke_width=5,entry_seconds=.065,
                        role='caption',timing_source='official_youtube_word_offsets'))
        else:
            positions = [(5,3,'PEMANASAN'),(8,2.7,'LATIHAN'),(10.7,3,'RENANG'),(13.7,3.3,'SEPEDA'),(17,3,'IRONMAN 70.3')]
            if index == 6:
                positions=[(5.0666666667,3,'LARI'),(8.0666666667,2.5,'RENANG'),
                    (10.5666666667,2,'OPEN WATER'),(12.5666666667,2.5,'PERSIAPAN'),
                    (15.0666666667,2.5,'HARI LOMBA'),(17.5666666667,3,'BEVAN · IRONMAN 70.3')]
            recipe['text_overlays']=[dict(start=t,duration=d,text=text,position=[.5,.84],font_size=54,
                color='#ffffff',background='#111111dc',stroke_width=0,role='chapter') for t,d,text in positions]
        if index == 3:
            recipe['text_overlays'].append(dict(start=11,duration=5,text='IRONMAN 70.3',position=[.5,.84],font_size=58,stroke_width=4))
        if index == 4:
            recipe['text_overlays'].append(dict(start=15.9333333333,duration=3,text='GARIS FINISH · IRONMAN',position=[.5,.84],font_size=54,stroke_width=4))
        if index == 6:
            recipe['beat_effects']=dict(enabled=True,start_seconds=152/30,end_seconds=527/30,
                beats_seconds=[frame/30 for frame in range(152,527,15)],estimated_bpm=120,
                punch_scale=.065,shake_pixels=6,rotation_degrees=.3,brightness_pulse=.035,decay_seconds=.28)
        duration = validate_recipe(recipe)
        atomic_json(OUT/'recipes'/f'clip-{index:03}.json',recipe)
        recipes.append(dict(index=index,title=recipe['title'],duration_seconds=duration,
                            original_voice=bool(recipe.get('narration')),path=str(OUT/'clips'/f'clip-{index:03}'/'master.mp4')))
    # Rebuilding recipes changes the proposal, so it requires fresh style approval.
    atomic_json(OUT/'batch.json',{
        'clips':recipes,
        'status':'awaiting_user_editing_style_approval',
        'approval_requested_by_user':True,
        'production_render_authorized':False,
        'campaign_id':'camp_8d3c32dfe5b9',
        'publishing':'draft_only'})
    print(json.dumps(recipes,ensure_ascii=True),flush=True)


def preview(indices):
    cache=OUT/'clips/scene-cache';cache.mkdir(parents=True,exist_ok=True)
    for index in indices:
        recipe=read(OUT/'recipes'/f'clip-{index:03}.json')
        frames=[];at=0
        layers=prepare_text_layers(recipe.get('text_overlays',[]),1080,1920)
        for scene in recipe['scenes']:
            source=prepare_scene(scene,cache,get_ffmpeg_path())
            image=source.suffix.lower() in {'.png','.jpg'}
            # Leading/trailing proof catches source-camera pans that a midpoint
            # alone can hide, before spending time on a production render.
            times=[scene['duration']/2] if image else [min(.15,scene['duration']/3),scene['duration']/2,max(0,scene['duration']-.15)]
            c=None if image else cv2.VideoCapture(str(source))
            for local in times:
                if image:
                    frame=cv2.imread(str(source))
                else:
                    c.set(cv2.CAP_PROP_POS_MSEC,local*1000);ok,frame=c.read()
                    if not ok:raise ValueError('Preview failed')
                frame=frame_scene(frame,scene,local/scene['duration'],1080,1920);t=at+local
                if t<recipe['hook']['duration']:
                    hook=make_hook(recipe['hook'],1080,1920);alpha=hook[:,:,3:4]/255
                    frame=(frame*(1-alpha)+hook[:,:,:3][:,:,::-1]*alpha).astype('uint8')
                frame=apply_text_layers(frame,t,layers)
                pic=Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB));pic.thumbnail((270,480));frames.append((t,scene,pic))
            if c:c.release()
            at+=scene['duration']
        sheet=Image.new('RGB',(270*4,530*((len(frames)+3)//4)),'#222');draw=ImageDraw.Draw(sheet)
        for i,(at,scene,pic) in enumerate(frames):
            x=i%4*270;y=i//4*530;sheet.paste(pic,(x,y+25));draw.text((x+4,y+3),f'{at:.2f}s',fill='white')
            draw.text((x+4,y+508),scene['visual_group'][:30],fill='white')
        sheet.save(OUT/'review'/f'clip-{index:03}-storyboard.jpg');print('Preview ready',index,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['build','preview','render']);p.add_argument('--indices');p.add_argument('--batch-dir',type=Path,default=OUT);a=p.parse_args()
    if a.action=='build' and a.batch_dir.resolve()!=OUT.resolve():
        p.error('Use the dedicated follow-up builder to create a new batch.')
    OUT=a.batch_dir.resolve()
    indices=[int(i) for i in a.indices.split(',')] if a.indices else ([r['index'] for r in read(OUT/'batch.json')['clips']] if a.action!='build' else list(range(1,7)))
    if a.action=='build':
        from build_ironman_approved_batch import build as build_approved
        build_approved()
    elif a.action=='preview':preview(indices)
    else:
        if read(OUT/'batch.json').get('production_render_authorized') is not True:
            p.error('Production render is on hold until the user approves the editing style.')
        from services.storage import WorkflowStore
        from services.achievement_montage import RENDER_VERSION
        published=WorkflowStore(ROOT/'workflow.sqlite3').publications()
        for index in indices:
            recipe_path=OUT/'recipes'/f'clip-{index:03}.json'
            destination=OUT/'clips'/f'clip-{index:03}'/'master.mp4'
            metadata_path=destination.parent/'data.json'
            if destination.exists() and metadata_path.exists():
                previous=read(metadata_path)
                if (previous.get('recipe_sha256')==file_sha256(recipe_path)
                        and previous.get('render_version')==RENDER_VERSION
                        and previous.get('final_sha256')==file_sha256(destination)):
                    print('Existing matching render retained',index,flush=True)
                    continue
            if any(p.get('clip_path')==str(destination) for p in published):
                p.error('This output has a publication record. Create a separate revision to preserve its bytes.')
            render_recipe(recipe_path,destination)
