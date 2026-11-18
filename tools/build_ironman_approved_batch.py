"""Build the six-clip allocation approved by the user on 14 October 2026."""
import argparse
import copy
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.achievement_montage import validate_recipe
from services.editing import file_sha256
from services.storage import atomic_json, utc_now
from utils.helpers import get_ffmpeg_path

OUT = ROOT / 'output/ironman-batch-20261014'
OLD = ROOT / 'output/ironman-tests-20261013'
REVIEW = ROOT / 'output/ironman-style-review-20261014'
VLOG = OLD / 'assets/official-ironman-vlog.mp4'
URL = 'https://www.youtube.com/watch?v=u9d14ssEc0c'
FONT = 'C:/Windows/Fonts/ariblk.ttf'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def extract_voice(index, ranges):
    path = OUT / 'audio' / f'voice-{index:02}.mp3'
    stamp = path.with_suffix('.source.json')
    identity = {'source_sha256':file_sha256(VLOG),'ranges':ranges,'edge_fades_ms':[5,10]}
    if path.exists() and stamp.exists() and read(stamp) == identity:
        return path
    cmd = [get_ffmpeg_path(),'-v','error','-y']
    for start,length in ranges:
        cmd += ['-ss',str(start),'-t',str(length),'-i',str(VLOG)]
    filters = []
    for i,(_,length) in enumerate(ranges):
        filters.append(f'[{i}:a]atrim=duration={length},asetpts=PTS-STARTPTS,'
                       f'afade=t=in:d=0.005,afade=t=out:st={length-.01}:d=0.01[a{i}]')
    filters.append(''.join(f'[a{i}]' for i in range(len(ranges)))+
                   f'concat=n={len(ranges)}:v=0:a=1[out]')
    cmd += ['-filter_complex',';'.join(filters),'-map','[out]','-ac','1','-ar','16000',
            '-c:a','libmp3lame','-b:a','96k',str(path)]
    subprocess.run(cmd,check=True,capture_output=True)
    atomic_json(stamp,identity)
    return path


def captions(ranges, index):
    # The official YouTube word offsets were more faithful than the independent
    # local ASR pass on the music-heavy vlog. Ambiguous names are cut from audio.
    words = []
    source_words = []
    for event in read(OUT/'source-captions.id.json3')['events']:
        for seg in event.get('segs',[]):
            token = seg.get('utf8','').strip()
            if token and not token.startswith('['):
                source_words.append((event['tStartMs']/1000+seg.get('tOffsetMs',0)/1000,token))
    at = 0.
    for start,length in ranges:
        for t,word in source_words:
            if not start <= t < start+length:
                continue
            word = word.strip('.,!?')
            if word.lower() in {'e','ee','us'}:
                continue
            # Uncertain bike verb in this ASR is omitted rather than invented.
            if index == 4 and 452.9 <= t < 454.5:
                continue
            word = {'Brisband':'Brisbane','test':'tes','bik':'bike'}.get(word,word)
            words.append((at+t-start,word.upper()))
        at += length
    layers,groups,group = [],[],[]
    for word in words:
        if group and word[0]-group[-1][0]>1.05:
            groups.append(group);group=[]
        group.append(word)
        if len(group)==3:
            groups.append(group);group=[]
    if group:
        groups.append(group)
    for group in groups:
        text = ' '.join(w[1] for w in group)
        for active,(start,_) in enumerate(group):
            next_index = next(i for i,w in enumerate(words) if w==(start,group[active][1]))+1
            end = min(at,words[next_index][0] if next_index<len(words) else start+.55)
            # Preserve an actual breath as a gap instead of holding a stale word.
            end = min(end,start+.95)
            if end <= start:
                continue
            layers.append({'start':start,'duration':end-start,'phrase_start':group[0][0],
                'text':text,'highlight_index':active,'highlight_color':'#1677FF',
                'position':[.5,.80],'font_path':FONT,'font_size':66,'color':'#ffffff',
                'stroke_width':2,'entry_seconds':.07,'role':'caption',
                'timing_source':'official_youtube_word_offsets'})
    return layers


def build(indices=None):
    approval = read(REVIEW/'approval.json')
    if approval.get('status') != 'approved' or approval.get('allocation') != {'A':4,'B':1,'C':1}:
        raise ValueError('This batch needs the matching human style approval')
    assets = {a['title']:a for a in read(OLD/'assets-index.json')}
    source_hash = file_sha256(VLOG)

    def raw(name,start,length,group,anchor=(.5,.5),**extra):
        a = assets[name]
        return {'path':a['path'],'source_id':a['sha256'],'source_url':a['url'],
            'name':name,'source_start':start,'duration':length,'visual_group':group,
            'fit':'fill','anchor':list(anchor),**extra}

    def yt(start,length,group,anchor=(.5,.5),**extra):
        return {'path':str(VLOG),'source_id':source_hash,'source_url':URL,
            'name':'Vlog resmi Bevan','source_start':start,'duration':length,
            'visual_group':group,'fit':'context','context_height':.64,
            'anchor':list(anchor),'crop_bottom':.09,**extra}

    def still(path,length,group,url,**extra):
        return {'path':str(path),'source_id':file_sha256(path),'source_url':url,
                'name':path.stem,'duration':length,'visual_group':group,'fit':'fill',**extra}

    def photo(name,length,**extra):
        path = ROOT/'output/ironman-reference-20261013/official-assets'/name
        return still(path,length,'finisher_ui_flag_'+path.stem,
            'https://drive.google.com/drive/folders/17spOI2GBEbuevxka4NTd5hEZz2Uq3UCL',**extra)

    finisher = OUT/'assets/finisher-732.png'
    if not finisher.exists():
        subprocess.run([get_ffmpeg_path(),'-v','error','-y','-ss','732','-threads','2',
            '-i',str(VLOG),'-frames:v','1',str(finisher)],check=True,capture_output=True)
    finish_run = still(OUT/'assets/finish-run-8_0.png',2.8,'finish_run_profile',
        assets['IMG_1849.MOV']['url'],derived_from_source_id=assets['IMG_1849.MOV']['sha256'],
        freeze_frame_from_seconds=8,fit='context',context_height=.72,
        anchor=[.46,.5],zoom=1,zoom_end=1.025)
    arch = still(OUT/'assets/finish-arch-721.png',3,'finish_arch_arrival',URL,
        derived_from_source_id=source_hash,freeze_frame_from_seconds=721,anchor=[.35,.5],zoom=1,zoom_end=1.035)
    smile = copy.deepcopy(read(OLD/'revisions/film-burn-v2/recipe.json')['scenes'][-1])
    smile.update(duration=3,zoom=1.08,zoom_end=1.105)
    wide_smile = still(finisher,3,'finisher_wide_medal_smile',URL,
        derived_from_source_id=source_hash,freeze_frame_from_seconds=732,
        fit='context',context_height=.72,anchor=[.44,.56],gamma=1.18,zoom=1,zoom_end=1.035)
    music_a = read(OLD/'recipes/ironman-test-03.json')['music']
    music_b = read(OLD/'recipes/ironman-test-02.json')['music']
    styles = {
        'A':{'name':'Vlog + Film Burn','hook':{'duration':5,'bounds':[.07,.06,.86,.12],
            'background':'#111111c4','color':'#ffffff','accent':'#e31327',
            'accent_word':True,'font_path':FONT,'font_size':60,'alignment':'center',
            'red_rule':False,'entry_seconds':.15,'exit_seconds':.12},
            'caption':{'font_path':FONT,'font_size':66,'words_per_phrase':3,
                       'color':'#ffffff','highlight_color':'#1677FF','position':[.5,.80]},
            'max_b_roll_fraction':.20,'max_b_roll_shots':2,'closing_seconds':[2,3],
            'cta':{'enabled':False,'required':False}},
        'B':{'name':'Montase Editorial','hook':{'duration':5,'bounds':[.055,.65,.89,.13],
            'background':'#ffffff','color':'#111111','accent':'#e31327',
            'accent_word':True,'font_path':'C:/Windows/Fonts/arial.ttf','font_size':62,
            'alignment':'left','red_rule':False,'entry_seconds':.15,'exit_seconds':.12},
            'cta':{'enabled':False,'required':False}},
        'C':{'name':'Jedag-jedug','hook':{'duration':152/30,'bounds':[.083333,.655273,.835069,.125],
            'background':'#ffffff','color':'#111111','accent':'#e31327',
            'font_path':FONT,'font_size':62,'alignment':'center','red_rule':True,
            'entry_seconds':.15,'exit_seconds':.12},
            'cta':{'enabled':False,'required':False}}}
    specs = [
        {'title':'5 bulan persiapan IRONMAN','style':'A',
         'hook':'5 BULAN PERSIAPAN\nUNTUK IRONMAN 70.3',
         'description':'Lima bulan persiapan hingga Bevan Pramudito menuntaskan IRONMAN 70.3.',
         'voice_ranges':[(669.35,4.25),(676.05,7.95)],'music':music_a,'music_start':8,
         'scenes':[yt(669.35,4.25,'five_months_original_voice',(.54,.5),anchor_end=[.56,.5],gamma=1.08),
            yt(676.05,7.95,'pre_start_complete_sentence',(.6,.5),anchor_end=[.55,.5],gamma=1.08),
            photo('IMG_0939.png',3,anchor=[.5,.5])]},
        {'title':'Tes air sebelum IRONMAN','style':'A',
         'hook':'SEBELUM IRONMAN\nBEVAN TES AIR DULU',
         'description':'Bevan mengenali kondisi air sebelum start IRONMAN 70.3.',
         'voice_ranges':[(475.1,8.7666666667),(487.5666666667,7.0333333333)],'music':music_b,'music_start':90,
         'scenes':[yt(475.1,4.5,'test_swim_original_voice',(.67,.5),anchor_end=[.60,.5],gamma=1.12),
            raw('IMG_1814.MOV',3,1.5,'sea_temperature_context',role='b_roll'),
            yt(481.1,2.7666666667,'test_swim_importance',(.60,.5),gamma=1.12),
            yt(487.5666666667,7.0333333333,'test_swim_complete_sentence',(.4,.5),anchor_end=[.34,.5],gamma=1.12,context_height=.60,
                anchor_path=[[0,.4,.5],[1,.45,.5],[2,.54,.5],[3,.60,.5],[4,.57,.5],
                             [5,.59,.5],[5.5,.57,.5],[6,.49,.5],[6.8,.34,.5],[7.0333333333,.34,.5]]),
            photo('IMG_0937.png',3,anchor=[.5,.6],zoom=1.10)]},
        {'title':'Persiapan menjelang IRONMAN','style':'A',
         'hook':'SIAPKAN DIRI\nSEBELUM IRONMAN',
         'description':'Bevan menyiapkan diri sebelum keberangkatan menuju IRONMAN 70.3.',
         'voice_ranges':[(18.48,3.75),(28.72,9.23)],'music':music_a,'music_start':96,
         'scenes':[yt(18.48,3.75,'departure_preparation_original_voice',(.53,.5),anchor_end=[.54,.5],context_height=.60),
            yt(28.72,3.85,'sports_preparation_original_voice',(.48,.5),anchor_end=[.55,.5],context_height=.60),
            raw('Bevan Running new 20.mp4',3.5,1,'hydration_training',(.28,.5),role='b_roll',fit='context',context_height=.64),
            yt(33.57,4.38,'preparation_complete_sentence',(.61,.5),anchor_end=[.60,.5]),finish_run]},
        {'title':'Perjalanan ke IRONMAN pertama','style':'A',
         'hook':'IRONMAN 70.3 PERTAMA\nPERJALANAN BEVAN',
         'description':'Keberangkatan dan persiapan sepeda Bevan sebelum IRONMAN 70.3 pertamanya.',
         'voice_ranges':[(91.1,5.2333333333),(452.24,8.86)],'music':music_b,'music_start':112,
         'scenes':[yt(91.1,5.2333333333,'first_ironman_original_voice',(.32,.5),anchor_end=[.36,.5],context_height=.60),
            yt(452.24,7.86,'bike_preparation_original_voice',(.48,.5),anchor_end=[.53,.5]),
            yt(278,1,'coastal_arrival_context',(.60,.5),role='b_roll',context_height=.68),arch]},
        {'title':'Latihan menuju IRONMAN · Editorial','style':'B',
         'hook':'Proses di balik\npencapaian IRONMAN',
         'description':'Pemanasan, latihan renang, bersepeda, dan pencapaian Bevan di IRONMAN 70.3.',
         'music':music_b,'music_start':20,
         'scenes':[raw('Bevan Running new 1.mp4',.2,2.7,'warmup_stretching',(.35,.5)),
            raw('Bevan Running new 5.mp4',.5,3,'warmup_before_run',(.34,.5)),
            raw('66a70715-4fd4-44a9-9e65-bde62c931e01.mp4',4,3,'pool_training_unused_take'),
            raw('IMG_1573.MOV',14,3.3,'cycle_training_late_range',(.55,.5)),smile]},
        {'title':'Latihan ke finish IRONMAN · Jedag Jedug','style':'C',
         'hook':'BEVAN MENUNTASKAN\nIRONMAN 70.3',
         'description':'Persiapan, renang, sepeda, lari, dan medali Bevan di IRONMAN 70.3.',
         'music':music_a,'music_start':64,
         'scenes':[raw('IMG_1748.MOV',.5,152/30,'race_morning_warmup_identity',(.35,.5),fit='context',context_height=.70,playback_rate=.5),
            raw('Bevan Running new 30.mp4',.1,3,'running_track_bevan',(.5,.5),fit='context',context_height=.70),
            raw('7aed9602-4cfb-4b80-bf54-28f8c30d17d2.mp4',.2,2.5,'pool_top_down_unused_range'),
            yt(692,2,'open_water_warmup',(.44,.5),context_height=.72),
            raw('IMG_1830.MOV',10,2.5,'race_cycling_close',(.4,.5),
                fit='context',context_height=.64,anchor_end=[.5,.5],
                anchor_path=[[0,.4,.5],[.8,.26,.5],[1.2,.17,.5],[1.6,.33,.5],[2,.4,.5],[2.5,.52,.5]]),
            raw('IMG_1849.MOV',5.4,2.5,'race_finish_approach',(.58,.5),anchor_end=[.50,.5],fit='context',context_height=.68),wide_smile]}
    ]
    batches=[]
    prior_rows={r['index']:r for r in read(OUT/'batch.json').get('clips',[])}
    for index,spec in enumerate(specs,1):
        if indices is not None and index not in indices:
            batches.append(prior_rows[index])
            continue
        style=spec.pop('style');hook_text=spec.pop('hook');ranges=spec.pop('voice_ranges',None)
        recipe={'schema':'ssr-achievement-montage','version':1,
            'canvas':{'width':1080,'height':1920,'fps':30},
            'constraints':{'hook_required_word':'IRONMAN','min_hook_seconds':5,'min_seconds':15,'max_seconds':180},
            'id':f'ironman-approved-20261014-{index:02}',
            'variant':{'A':'achievement_vlog_film_burn','B':'achievement_editorial_v2','C':'achievement_jedag_jedug_v2'}[style],
            'style_id':style,'style_approval':approval,
            'hook':{**styles[style]['hook'],'text':hook_text},
            'cta':styles[style]['cta'],'reference_role':'style_only',
            'finished_clipper_reference_used_as_source':False,**copy.deepcopy(spec)}
        recipe['music']['start']=recipe.pop('music_start')
        recipe['text_overlays']=[];recipe['transitions']=[]
        if ranges:
            voice_duration=sum(length for _,length in ranges)
            path=extract_voice(index,ranges)
            recipe['narration']={'path':str(path),'duration':voice_duration,
                'source_id':source_hash,'source_url':URL,'source_ranges':ranges,
                'provenance':'Original Bevan audio, sentence cuts with 5–10 ms edge fades'}
            recipe['text_overlays']=captions(ranges,index)
            if index==4:
                recipe['text_overlays'].append({'start':5.9,'duration':1.5,
                    'text':'PERSIAPAN SEPEDA','position':[.5,.80],'font_size':52,
                    'background':'#111111d9','stroke_width':0,'role':'context_label'})
            recipe['text_overlays'].append({'start':voice_duration,'duration':recipe['scenes'][-1]['duration'],
                'text':'FINISHER · IRONMAN 70.3','position':[.5,.84],
                'font_size':52,'background':'#111111d9','stroke_width':0,'role':'payoff'})
            recipe['transitions']=[{'at':voice_duration,'duration':.3,'intensity':.5,'seed':30+index}]
            b_roll=[s for s in recipe['scenes'] if s.get('role')=='b_roll']
            total=sum(s['duration'] for s in recipe['scenes'])
            if len(b_roll)>2 or sum(s['duration'] for s in b_roll)/total>.20:
                raise ValueError('Approved vlog B-roll limits exceeded')
        elif style=='B':
            for scene in recipe['scenes'][:-1]:
                scene.update(fit='context',context_height=.70,matte_rgb=[166,164,166])
            recipe['text_overlays']=[{'start':t,'duration':d,'text':text,'position':[.5,.85],
                'font_size':52,'stroke_width':0,'background':'#111111d9','role':'chapter'}
                for t,d,text in [(5.7,3,'RENANG'),(8.7,3.3,'SEPEDA'),(12,3,'FINISHER · IRONMAN 70.3')]]
        else:
            recipe['beat_effects']={'enabled':True,'start_seconds':152/30,'end_seconds':527/30,
                'beats_seconds':[f/30 for f in range(152,527,15)],'estimated_bpm':120,
                'punch_scale':.055,'shake_pixels':5,'rotation_degrees':.25,
                'brightness_pulse':.025,'decay_seconds':.28,
                'measurement':str(OLD/'jedag-jedug/beat-analysis-verified.json')}
            recipe['transitions']=[{'at':527/30,'duration':.3,'intensity':.55,'seed':36}]
            recipe['text_overlays']=[{'start':527/30,'duration':3,'text':'FINISHER · IRONMAN 70.3',
                'position':[.5,.84],'font_size':52,'stroke_width':0,'background':'#111111d9','role':'payoff'}]
        total=validate_recipe(recipe)
        path=OUT/'recipes'/f'clip-{index:03}.json';atomic_json(path,recipe)
        batches.append({'index':index,'title':recipe['title'],'style_id':style,
            'duration_seconds':total,'original_voice':bool(ranges),'recipe':str(path),
            'path':str(OUT/'clips'/f'clip-{index:03}'/'master.mp4')})
    for key,style in styles.items():
        atomic_json(OUT/'templates'/f'approved-style-{key}.json',
            {'schema':'ssr-editing-style-preset','version':1,'style_id':key,
             'renderer':'services.achievement_montage','editable':True,'approval':approval,**style})
    atomic_json(OUT/'batch.json',{'status':'approved_recipes_ready','campaign_id':'camp_8d3c32dfe5b9',
        'clips':batches,'style_approval':approval,'approval_requested_by_user':True,
        'production_render_authorized':True,'publishing':'draft_only','updated_at':utc_now()})
    print(json.dumps(batches,ensure_ascii=True,indent=2),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--indices');args=parser.parse_args()
    build([int(x) for x in args.indices.split(',')] if args.indices else None)
