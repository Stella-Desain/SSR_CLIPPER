"""Render the two human-selected educational highlights through SSR_CLIPPER."""
import argparse,copy,json,sys,uuid,shutil,threading
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.stdout.reconfigure(encoding='utf-8',errors='replace')
from app import WebAPI
from clipper_core import AutoClipperCore
from services.editing import fingerprint_source,probe_media,file_sha256
from services.template_selection import choose_template
from services.storage import atomic_json,utc_now
from services.face_tracking import CAMERA_VERSION
from services.framing import FRAMING_VERSION
from utils.helpers import get_ffmpeg_path
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',default='output/bevan-revision-20261009')
parser.add_argument('--assets',default='output/bevan-production-20261009/assets')
args=parser.parse_args()
OUT=(ROOT/args.output).resolve();OUT.mkdir(parents=True,exist_ok=True)
ASSETS=(ROOT/args.assets).resolve()
source=ASSETS/'bevan-interview-source.mp4'
words=json.loads(source.with_suffix('.words.json').read_text(encoding='utf-8'))
repairs=[]
reviewed=[]
for w in words['words']:
    if 52.75 <= w['start'] < 52.97 and w['word'].strip()=='trade':
        repairs.append({'original':'trade buy','corrected':'TradFi','start':w['start'],'end':53.12})
        reviewed.append({**w,'word':' TradFi','end':53.12})
    elif 52.95 <= w['start'] < 53.13 and w['word'].strip()=='buy':
        continue
    elif 76.75 <= w['start'] < 77.21 and w['word'].strip() in ('fun','-fun'):
        reviewed.append({**w,'word':' funds' if w['word'].strip()=='fun' else ' funds'})
        repairs.append({'original':w['word'],'corrected':'funds','start':w['start'],'end':w['end']})
    else:reviewed.append(w)
words['words']=reviewed
words['manual_word_repairs']=repairs
atomic_json(ASSETS/'bevan-interview-source.reviewed.words.json',words)
cta_words=json.loads((ASSETS/'CTA_GMGN_Apps_1.words.json').read_text(encoding='utf-8'))
api=WebAPI.__new__(WebAPI)
api.config_file=str(ROOT/'config.json');api.worker_enabled=False;api.output_dir=str(ROOT/'output')
campaign=copy.deepcopy(next(c for c in api._get_cfg()['campaigns'] if c['id']=='camp_a0ad79a3ee99'))
if not api._campaign_readiness(campaign)['production_ready']:raise ValueError(api._campaign_readiness(campaign))
if words['source_sha256']!=file_sha256(source):raise ValueError('Source words changed')
if cta_words['source_sha256']!=file_sha256(campaign['editing']['endcard']['path']):raise ValueError('CTA words changed')
identity=fingerprint_source(str(source))
identity.update(media=probe_media(source,get_ffmpeg_path()),url=str(source.resolve()))
job_id='job_bevan_ruang_revision_20261009'
job={'id':job_id,'source':str(source.resolve()),'source_id':identity['source_id'],'campaign_id':campaign['id'],
    'campaign':campaign,'title':'Bevan · Dua template Ruang Berpikir','status':'running','clips':[],
    'created_at':utc_now(),'execution':{'interface':'local_command','selection':'reviewed_source_word_times',
    'original_url':'https://www.youtube.com/watch?v=3HJPIe6GmNo','download_start_seconds':360,'no_model_identity_claim':True}}
store=api._get_store();store.put('job',job_id,job)
core=AutoClipperCore(client=None,output_dir=OUT/'clips',ffmpeg_path=get_ffmpeg_path(),
    local_whisper_settings={'enabled':True},log_callback=lambda s: print(str(s),flush=True))
core.campaign_config=campaign;core.source_analysis=identity;core.job_id=job_id;core.efficient_framing=True
core._caption_lock=threading.Lock()
core.framing_encoder_args=['-c:v','h264_qsv','-global_quality','14']
core.get_video_encoder_args=lambda:['-c:v','h264_qsv','-global_quality','14']
original_ffmpeg=core._run_ffmpeg_subprocess
def accelerated_ffmpeg(command,**kwargs):
    if 'libx264' in command:
        updated=[];i=0
        while i<len(command):
            if command[i]=='-c:v' and command[i+1]=='libx264':
                updated+=['-c:v','h264_qsv','-global_quality','14'];i+=2
            elif command[i] in ('-preset','-crf'):
                i+=2
            else:updated.append(command[i]);i+=1
        command=updated
    return original_ffmpeg(command,**kwargs)
core._run_ffmpeg_subprocess=accelerated_ffmpeg
import services.editing as editing_module
original_media_run=editing_module._run
def accelerated_media_run(command,**kwargs):
    if 'libx264' not in command:return original_media_run(command,**kwargs)
    updated=[];i=0
    while i<len(command):
        if command[i]=='-c:v' and command[i+1]=='libx264':
            updated+=['-c:v','h264_qsv','-global_quality','14'];i+=2
        elif command[i] in ('-preset','-crf'):i+=2
        else:updated.append(command[i]);i+=1
    try:return original_media_run(updated,**kwargs)
    except Exception:return original_media_run(command,**kwargs)
editing_module._run=accelerated_media_run
original_base=core._render_clip_base
def reuse_verified_portrait(video,highlight,index,*args,**kwargs):
    folder=core.output_dir/f'clip-{index:03d}'
    portrait=folder/'temp_portrait.mp4';metadata_path=folder/'data.json';camera_path=folder/'camera.json'
    if portrait.is_file() and metadata_path.is_file() and camera_path.is_file():
        previous=json.loads(metadata_path.read_text(encoding='utf-8'))
        camera=json.loads(camera_path.read_text(encoding='utf-8'))
        if (camera.get('camera_version')==CAMERA_VERSION and camera.get('framing_version')==FRAMING_VERSION
                and previous.get('start_time')==highlight['start_time'] and previous.get('end_time')==highlight['end_time']
                and camera.get('detector')=='opencv' and camera.get('fit_frames',1)/max(1,camera.get('frames',1))<.1
                and abs(probe_media(portrait,get_ffmpeg_path())['duration']-highlight['duration_seconds'])<.15):
            checksum=file_sha256(portrait)
            shutil.copy2(portrait,folder/'master.mp4')
            if file_sha256(folder/'master.mp4')!=checksum:raise ValueError('Portrait cache changed during copy')
            print('REUSE_VERIFIED_PORTRAIT',index,checksum,flush=True)
            return
    return original_base(video,highlight,index,*args,**kwargs)
core._render_clip_base=reuse_verified_portrait
current={}
def timestamps(value):return f'00:{int(value//60):02d}:{value%60:06.3f}'
highlights=[
    {'start':25.42,'end':54.65,'template_id':'ruang_founder',
     'title':'Kenapa Bevan Melacak Wallet Crypto?',
     'hook_title':'MAIN CRYPTO TANPA INI?',
     'hook_description':'BEVAN JELASIN KENAPA WALLET TRACKING ITU PENTING',
     'description':'Bevan menjelaskan pentingnya wallet tracking dan membaca aktivitas on-chain.',
     'editing_cues':[{'start':6.0,'text':'wallet tracking crypto'},{'start':12.0,'text':'transparan onchain'},{'start':22.0,'text':'advantage'}]},
    {'start':55.1,'end':93.37,'template_id':'ruang_witness',
     'title':'Apa yang Bisa Dilihat dari Wallet Tracking?',
     'hook_title':'WALLET BISA DILACAK?',
     'hook_description':'BEVAN UNGKAP DATA YANG BISA DILIHAT DI ON-CHAIN',
     'description':'Percakapan Bevan tentang wallet tracking, riwayat transaksi, dan data PnL on-chain.',
     'editing_cues':[{'start':6.2,'text':'wallet tracking'},{'start':17.0,'text':'tracking crypto'},{'start':28.0,'text':'onchain'},{'start':44.0,'text':'wallet'},{'start':57.0,'text':'kelebihan'}]}
]
def caption_words(_audio):
    h=current['highlight'];start,end=h['start'],h['end'];intro=5.2
    story=probe_media(current['directory']/'temp_portrait.mp4',get_ffmpeg_path())['duration']
    selected=[{**w,'start':max(0,w['start']-start)+intro,'end':min(end-start,w['end']-start)+intro}
              for w in words['words'] if w['end']>start and w['start']<end and w['end']>w['start']]
    selected += [{**w,'start':w['start']+intro+story,'end':w['end']+intro+story} for w in cta_words['words']]
    # Correct named entities and clear ASR spelling errors, with timings retained.
    replacements={'kripto':'crypto','kripto,':'crypto','anonimus':'anonymous','fun-fun':'fund-fund','trade buy':'TradFi'}
    for w in selected:
        t=w['word'].strip()
        if t in replacements:w['word']=' '+replacements[t]
    atomic_json(current['directory']/'caption-words.json',{'words':selected,'intro_seconds':intro,'story_seconds':story,
        'source_sha256':words['source_sha256'],'cta_sha256':cta_words['source_sha256'],'cta_opening_alignment':cta_words.get('opening_repair')})
    return SimpleNamespace(words=[SimpleNamespace(**w) for w in selected],segments=[],text=' '.join(w['word'].strip() for w in selected))
core._whisper_transcribe_words=caption_words
def finalize(directory,metadata):
    metadata['source_provenance']={'original_url':job['execution']['original_url'],'download_start_seconds':360,
        'source_sha256':words['source_sha256'],'cta_sha256':cta_words['source_sha256']}
    metadata['caption_transcript_provenance']={'kind':'verified_source_and_CTA_word_times_with_intro_offset',
        'source_words':str(source.with_suffix('.words.json')),'cta_words':str(ASSETS/'CTA_GMGN_Apps_1.words.json')}
    # Publication copy is clean; the stored brief remains intact in the snapshot.
    publication_job=copy.deepcopy(job)
    publication_job['campaign']['brief']['cta']='Cek Bio untuk akses GMGN'
    metadata=api._finalize_workflow_clip(directory,metadata,publication_job)
    music=metadata['music']['attribution']
    credit=f"{music['source_url']} · CC BY 3.0: {music['license_ccurl']} · musik dipotong dan dicampur dengan dialog."
    metadata['caption']+='\n'+credit
    for platform in metadata['captions']:metadata['captions'][platform]+='\n'+credit
    registered=api._register_clip(metadata['final_path'],metadata)
    metadata['revision_id']=registered['revision_id']
    return metadata
core.finalize_callback=finalize
try:
    for index,h in enumerate(highlights,1):
        selection_campaign=copy.deepcopy(campaign)
        selection_campaign['editing'].pop('template_pool',None)
        selection_campaign['editing'].update(selection_mode='fixed',preset_id=h['template_id'])
        h.update(start_time=timestamps(h['start']),end_time=timestamps(h['end']),duration_seconds=h['end']-h['start'],
                 hook_text=h['hook_title'],editing_template=choose_template(selection_campaign,'user_requested_one_per_template'))
        current.update(highlight=h,directory=core.output_dir/f'clip-{index:03d}')
        core.process_clip(str(source),h,index,total_clips=2,add_captions=True,add_hook=False,portrait=False,campaign_id=campaign['id'])
        job['clips'].append({'index':index,'status':'done','path':str(current['directory']/'master.mp4')})
        store.put('job',job_id,job)
    job.update(status='completed',progress=1,finished_at=utc_now())
    store.put('job',job_id,job)
    atomic_json(OUT/'render-result.json',job)
    print('TWO_CLIPS_COMPLETE',flush=True)
except Exception as exc:
    job.update(status='failed',error=str(exc));store.put('job',job_id,job)
    raise
finally:
    core.cleanup()
