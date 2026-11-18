"""Additional approved-style clips from distinct official vlog moments."""
import copy
import json
import shutil
from pathlib import Path

import build_ironman_approved_batch as base
from services.achievement_montage import validate_recipe
from services.editing import file_sha256
from services.storage import atomic_json, utc_now

OUT = base.ROOT / 'output/ironman-batch-2-20261014'
PREVIOUS = base.ROOT / 'output/ironman-batch-20261014'


def main():
    OUT.mkdir(exist_ok=True)
    if (OUT/'registered-clips.json').exists():
        raise ValueError('Registered output must be revised in a separate directory.')
    (OUT/'audio').mkdir(exist_ok=True)
    (OUT/'review').mkdir(exist_ok=True)
    shutil.copyfile(PREVIOUS/'source-captions.id.json3', OUT/'source-captions.id.json3')
    base.OUT = OUT
    previous = base.read(PREVIOUS/'batch.json')
    approval = previous['style_approval']
    assert approval['status']=='approved'
    original_a = base.read(PREVIOUS/'recipes/clip-001.json')
    original_b = base.read(PREVIOUS/'recipes/clip-005.json')
    source_hash = original_a['scenes'][0]['source_id']

    def yt(start, length, group, anchor=(.5,.5), **extra):
        return {'path':str(base.VLOG), 'source_id':source_hash, 'source_url':base.URL,
            'name':'Vlog resmi Bevan', 'source_start':start, 'duration':length,
            'visual_group':group, 'fit':'context', 'context_height':.64,
            'crop_bottom':.09, 'anchor':list(anchor), **extra}

    def payoff(index):
        # Four different payoff pictures within this batch; common official
        # finisher material also appears in earlier edits and is documented.
        source = {1:2, 2:3, 3:5, 4:1}[index]
        scene = copy.deepcopy(base.read(PREVIOUS/'recipes'/f'clip-{source:03}.json')['scenes'][-1])
        scene.update(duration=3, zoom=1, zoom_end=1.025)
        return scene

    specs = [
        {'title':'Cuaca menjelang IRONMAN pertama',
         'hook':'MENJELANG IRONMAN\nBEVAN HADAPI ANGIN DINGIN',
         'description':'Bevan bercerita tentang cuaca berangin dan harapannya menjelang IRONMAN 70.3 pertama.',
         'ranges':[(173.25,14.5)], 'music_start':38,
         'scenes':[yt(173.25,14.5,'arrival_weather_original_voice',(.51,.5),context_height=.48,gamma=1.08,
             anchor_path=[[0,.51,.5],[5,.52,.5],[10,.51,.5],[14.5,.51,.5]])]},
        {'title':'Apa itu race pack IRONMAN?',
         'hook':'SEBELUM START IRONMAN\nAMBIL RACE PACK DULU',
         'description':'Pengambilan race pack dan fasilitas persiapan Bevan sebelum IRONMAN 70.3.',
         'ranges':[(295.12,16.7)], 'music_start':52,
         'scenes':[yt(295.12,16.7,'race_pack_original_voice',(.44,.5),context_height=.62,gamma=1.10,
             anchor_path=[[0,.44,.5],[4,.43,.5],[8,.55,.5],[11,.54,.5],[14,.5,.5],[16.7,.49,.5]])]},
        {'title':'Bagian tersulit IRONMAN menurut Bevan',
         'hook':'IRONMAN PERTAMA BEVAN\nBAGIAN MANA PALING SULIT?',
         'description':'Cerita Bevan setelah finish IRONMAN 70.3 pertama: pengalaman renang dan lari.',
         'ranges':[(727.5,8.0),(738.05,4.35)], 'music_start':72,
         'scenes':[yt(727.5,8,'post_finish_original_voice',(.44,.5),anchor_end=[.45,.5],gamma=1.18),
                   yt(738.05,4.35,'hardest_swim_run_original_voice',(.42,.5),anchor_end=[.44,.5],gamma=1.18)]},
        {'title':'Check-in dan persiapan sepeda IRONMAN',
         'hook':'Sebelum start IRONMAN\ncheck-in dan cek sepeda',
         'description':'Persiapan resmi Bevan: check-in, pengambilan perlengkapan, dan pengecekan sepeda sebelum IRONMAN 70.3.',
         'music_start':126,
         'scenes':[yt(337.6,2.4,'race_checkin_ticket',(.63,.5),editorial_context_height=.60),
                   yt(341,2.7,'race_checkin_exit',(.54,.5),editorial_context_height=.60,
                       anchor_path=[[0,.54,.5],[1,.60,.5],[2,.61,.5],[2.7,.62,.5]]),
                   yt(288,3,'race_registration_counter',(.42,.5),anchor_end=[.43,.5]),
                   yt(574,3.9,'mechanic_check_before_transition',(.43,.5),anchor_end=[.50,.5])]},
    ]
    batch_rows = []
    for index, spec in enumerate(specs, 1):
        recipe = copy.deepcopy(original_a if index<=3 else original_b)
        recipe.update(id=f'ironman-followup-20261014-{index:02}', title=spec['title'],
            description=spec['description'], scenes=spec['scenes']+[payoff(index)],
            generation_authorization='User requested more clips using the previously approved editing styles.',
            text_overlays=[], transitions=[])
        recipe.pop('narration',None)
        recipe['hook']['text']=spec['hook']
        recipe['music']['start']=spec['music_start']
        if index<=3:
            ranges=spec['ranges']; duration=sum(length for _,length in ranges)
            voice=base.extract_voice(index,ranges)
            recipe['narration']={'path':str(voice),'duration':duration,
                'source_id':source_hash,'source_url':base.URL,'source_ranges':ranges,
                'provenance':'Original Bevan speech, sentence cuts with 5-10 ms edge fades'}
            layers=base.captions(ranges,index)
            for layer in layers:
                text=layer['text']
                if index==1:
                    text=text.replace('BASE','BEST')
                if index==2:
                    text=text.replace('BLACK','BIKE')
                layer['text']=text
            if index==3:
                # Automatic captions split the time result incorrectly. Avoid
                # inventing a number: use a clearly designated context label.
                layers=[l for l in layers if not 1.25<=l['start']<5.9]
                for layer in layers:
                    # Earlier active words share the same three-word phrase,
                    # so the bad numeric token must also leave those phrases.
                    layer['text']=layer['text'].replace(' 620','')
                layers.append({'start':1.3,'duration':4.5,'text':'FINISH IRONMAN 70.3',
                    'role':'context_label','position':[.5,.80], 'font_size':52,
                    'stroke_width':0,'background':'#111111d9'})
            recipe['text_overlays']=layers+[{'start':duration,'duration':3,
                'text':'FINISHER · IRONMAN 70.3','position':[.5,.84],
                'font_size':52,'stroke_width':0,'background':'#111111d9','role':'payoff'}]
            recipe['transitions']=[{'at':duration,'duration':.3,'intensity':.5,'seed':50+index}]
        else:
            for scene in recipe['scenes'][:-1]:
                scene.update(context_height=scene.get('editorial_context_height',.70),matte_rgb=[166,164,166])
            recipe['text_overlays']=[{'start':start,'duration':length,'text':text,
                'position':[.5,.85],'font_size':52,'stroke_width':0,
                'background':'#111111d9','role':'chapter'}
                for start,length,text in [(5.1,3,'RACE PACK'),(8.1,3.9,'CEK SEPEDA'),(12,3,'FINISHER · IRONMAN 70.3')]]
        total=validate_recipe(recipe)
        path=OUT/'recipes'/f'clip-{index:03}.json'; atomic_json(path,recipe)
        batch_rows.append({'index':index,'title':recipe['title'],'style_id':recipe['style_id'],
            'duration_seconds':total,'original_voice':index<=3,'recipe':str(path),
            'path':str(OUT/'clips'/f'clip-{index:03}'/'master.mp4')})
    atomic_json(OUT/'batch.json',{'title':'Ironman tambahan · 3 Vlog + 1 Editorial',
        'job_id':'job_ironman_followup_20261014','status':'approved_recipes_ready',
        'campaign_id':previous['campaign_id'],'clips':batch_rows,
        'style_approval':approval,'production_render_authorized':True,
        'generation_authorization':'cari lagii yang bisa di bikin clip dan generate lagi',
        'publication_order':[1,4,2,3],'publishing':'draft_only','updated_at':utc_now()})
    atomic_json(OUT/'review/selection-notes.json',{
        'selected':['arrival weather','race pack','post-finish reflection','check-in and mechanic check'],
        'excluded':['dark night-before footage: face obscured','unrelated travel/trading assets','unverified athlete identities'],
        'style':'Previously user-approved A and B; no new editing style.',
        'b_roll':'No additional B-roll over original speech; editorial shots reflect their chapter labels.',
        'reuse':'Distinct main footage and original dialogue ranges. Common official finisher payoffs reused and recorded.',
        'uncertain_caption':'Finish time numeric ASR omitted, replaced with an explicit context label.',
        'hyperframes_usage':'unknown: usage_request_failed; native renderer used'})
    print(json.dumps(batch_rows,ensure_ascii=True))


if __name__=='__main__':
    main()
