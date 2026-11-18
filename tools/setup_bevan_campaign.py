"""Register the two reusable presets and verified official assets in BEVAN."""
import copy,json,sys,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.stdout.reconfigure(encoding='utf-8',errors='replace')
from app import WebAPI
from services.editing import file_sha256,probe_media
from utils.helpers import get_ffmpeg_path
OUT=ROOT/'output/bevan-production-20261009'
assets=OUT/'assets'
shutil.copy2(OUT/'.media/audio/sfx/sfx_001.mp3',assets/'cta-whoosh.mp3')
api=WebAPI.__new__(WebAPI)
api.config_file=str(ROOT/'config.json');api.worker_enabled=False;api.output_dir=str(ROOT/'output')
cfg=api._get_cfg()
original=copy.deepcopy(next(c for c in cfg['campaigns'] if c['id']=='camp_a0ad79a3ee99'))
if not (OUT/'campaign-before.json').is_file():
    (OUT/'campaign-before.json').write_text(json.dumps(original,ensure_ascii=False,indent=2),encoding='utf-8')
campaign=copy.deepcopy(original)
for conflict in campaign.get('extraction',{}).get('conflicts',[]):
    if conflict.get('field')=='brief.angles' and not conflict.get('resolved'):
        campaign['brief']['angles']=copy.deepcopy(conflict['suggested'])
        conflict.update(resolved=True,resolution='Follow prohibition on comparing or attacking other creators/brands.')
selected=json.loads((OUT/'music-selected.json').read_text(encoding='utf-8'))
def asset(name,path,role,**extra):
    return {'id':file_sha256(path)[:24],'name':name,'path':str(path.resolve()),'role':role,'required':False,
            'sha256':file_sha256(path),**extra}
new_assets = [
    asset('Bevan bekerja di laptop · footage resmi',assets/'bevan-work.mp4','broll',opener=True,tags=['laptop','bekerja di laptop']),
    asset('Bevan desert · footage resmi',assets/'bevan-desert.mp4','broll',tags=['gurun','desert','sandboarding']),
    asset('Bevan jetski · footage resmi',assets/'bevan-jetski.mov','broll',tags=['jetski','jet ski']),
    asset('CTA GMGN Apps1 · resmi, suara lengkap sejak awal',assets/'CTA_GMGN_Apps_1.mp4','endcard',required=True,
          provenance='https://drive.google.com/file/d/1Xvrsrm95UByOc9i9hPxeIkIaiww8KPJ7/view'),
    asset('Hip-hop instrumental · 95 BPM · CC BY 3.0',assets/'hiphop-95-bpm.mp3','music',attribution=selected),
    asset('GMGN · logo resmi',assets/'gmgn-cta-plate.png','image',provenance='https://docs.gmgn.ai/'),
    asset('CTA whoosh',assets/'cta-whoosh.mp3','music',usage='transition_sfx')]
new_hashes={a['sha256'] for a in new_assets}
old_cta_hash=file_sha256(assets/'CTA_GMGN_Apps.mp4')
campaign['assets']=[a for a in campaign['assets'] if a.get('sha256') not in new_hashes|{old_cta_hash}]+new_assets
cta=next(a for a in campaign['assets'] if a['role']=='endcard' and a['required'])
for link in campaign.get('source_links',[]):
    if link.get('required') and '1zI4Xh972NV4ec7u_' in link.get('url',''):
        link['asset_id']=cta['id']
editing=campaign['editing']
editing.update(preset_id='ruang_founder',selection_mode='weighted_random',
    template_pool=[{'preset_id':p,'enabled':True,'weight':50} for p in ('ruang_founder','ruang_witness')],
    framing='speaker',source_role='campaign',review_mode='manual',max_workers=2)
editing['endcard'].update(path=cta['path'],required=True,duration_seconds=probe_media(cta['path'],get_ffmpeg_path())['duration'])
editing['music'].update(policy='local',path=str((assets/'hiphop-95-bpm.mp3').resolve()),required=True,
    volume=.15,ducking=True,fade_seconds=.5,start_seconds=0,
    attribution={'id':selected['id'],'name':selected['name'],'artist':selected['artist_name'],
                 'license_ccurl':selected['license_ccurl'],'source_url':selected['shareurl']})
editing['reference_style']={'hook_title':'','hook_description':'','hook_strip':'LIKE, COMMENT & FOLLOW',
    'hook_accent':'#cf003b','hook_background':'#ffffff','hook_text_color':'#111111',
    'cta_text':'Cek Bio untuk akses GMGN','cta_min_seconds':10,
    'cta_logo_path':str((assets/'gmgn-cta-plate.png').resolve()),'cta_logo_sha256':file_sha256(assets/'gmgn-cta-plate.png'),
    'cta_sfx_path':str((assets/'cta-whoosh.mp3').resolve()),'cta_sfx_sha256':file_sha256(assets/'cta-whoosh.mp3'),
    **editing.get('reference_style',{})}
result=api.save_campaign_workspace(campaign['id'],campaign)
if result['status']!='ok':raise ValueError(result)
(OUT/'campaign-ready.json').write_text(json.dumps(result['campaign'],ensure_ascii=False,indent=2),encoding='utf-8')
print(result['status'],result['readiness'])
