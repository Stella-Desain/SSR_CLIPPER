"""Register exact QA-reviewed outputs and distribute the approved Instagram batch."""
import argparse
import copy
import json
import sys
from datetime import datetime,timedelta,timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from setup_ironman_campaign import api_instance,ACCOUNT
from services.editing import file_sha256
from services.publishing import ReplizClient,ACTIVE,overlapping,validate_reservation,schedule_update
from services.storage import atomic_json,digest,utc_now
from services.scheduling import normalize_upload_times,parse_schedule_time,publication_day

OUT=ROOT/'output/ironman-batch-20261014'
CAMPAIGN='camp_8d3c32dfe5b9'
ZONE='Asia/Makassar'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def quality():
    batch=read(OUT/'batch.json')
    if not batch.get('production_render_authorized') or batch.get('style_approval',{}).get('status')!='approved':
        raise ValueError('Human editing-style approval is missing')
    verified=[]
    for row in batch['clips']:
        path=Path(row['path']);qa=read(path.parent/'qa-result.json');meta=read(path.parent/'data.json')
        if not qa.get('complete_decode') or not qa.get('visual_review_passed'):
            raise ValueError(f"Clip {row['index']} still needs complete media/visual QA")
        if qa['sha256']!=file_sha256(path) or qa['sha256']!=meta['final_sha256']:
            raise ValueError('Output bytes changed after QA')
        if file_sha256(row['recipe'])!=meta['recipe_sha256']:
            raise ValueError('Recipe changed after the delivered render')
        verified.append((row,meta,qa))
    return verified


def register():
    verified=quality();api=api_instance();store=api._get_store()
    campaign=next(c for c in api._get_cfg()['campaigns'] if c['id']==CAMPAIGN)
    if '#ironman' not in campaign['brief'].get('hashtags',[]) or campaign['brief'].get('cta'):
        raise ValueError('Campaign snapshot does not match the verified Ironman brief')
    batch=read(OUT/'batch.json')
    job={'id':batch.get('job_id','job_ironman_approved_batch_20261014'),'campaign_id':CAMPAIGN,
        'campaign':copy.deepcopy(campaign),'title':batch.get('title','Ironman · 4 Vlog + 1 Editorial + 1 Jedag-jedug'),
        'source':'https://www.youtube.com/@bevanpramudt','status':'completed',
        'created_at':utc_now(),'progress':1,'clips':[]}
    existing={str(Path(c['path']).resolve()):c for c in store.list('clip') if c.get('path')}
    registered=[]
    for row,meta,qa in verified:
        path=Path(row['path']);recipe=read(row['recipe']);credit=recipe['music']['attribution']
        previous=existing.get(str(path.resolve()))
        if previous and previous.get('file_hash')==qa['sha256']:
            clip=previous
        else:
            caption=(recipe['description']+'\n\n@bevanpramudt\n'+' '.join(campaign['brief']['hashtags'])+
                '\n\nMusik: '+credit['name']+' — '+credit['artist']+'\n'+credit['source_url']+
                '\nCC BY 3.0: '+credit['license_ccurl']+'\nMusik dipotong, dinormalisasi, dan diberi fade.')
            meta.update(campaign_id=CAMPAIGN,campaign_version_id=campaign['version_id'],
                campaign_snapshot=copy.deepcopy(campaign),job_id=job['id'],source_url=job['source'],
                caption=caption,captions={'instagram':caption,'tiktok':caption},
                has_hook=True,has_captions=bool(recipe.get('narration')),created_at=utc_now(),
                blockers=[],warnings=[],render_status='done',thumbnail=str(path.parent/'thumbnail.jpg'),
                reviewed_by='agent complete decode, source-voice onset and visual frame review',
                editing_style_approval=read(OUT/'batch.json')['style_approval'])
            clip=api._register_clip(path,meta)
            meta.update(clip_id=clip['id'],revision_id=clip['revision_id'])
            atomic_json(path.parent/'data.json',meta)
        registered.append({'index':row['index'],'clip_id':clip['id'],'title':clip['title'],
            'path':clip['path'],'duration':qa['duration_seconds'],'sha256':qa['sha256']})
        job['clips'].append({'index':row['index'],'status':'done','path':clip['path']})
    store.put('job',job['id'],job);atomic_json(OUT/'registered-clips.json',registered)
    print(json.dumps(registered,ensure_ascii=True),flush=True)


def next_slot(profile,existing,now):
    zone=ZoneInfo(ZONE);limit=int(profile['daily_limit'])
    used=[p for p in existing if p['account_id']==ACCOUNT and p['status'] in ACTIVE]
    for offset in range(366):
        day=now.astimezone(zone).date()+timedelta(days=offset)
        on_day=[p for p in used if publication_day(p,ZONE)==day.isoformat()]
        if len(on_day)>=limit:
            continue
        for slot in normalize_upload_times(profile.get('upload_times')):
            when=parse_schedule_time(day.isoformat()+'T'+slot,ZONE)
            if when<now+timedelta(minutes=5):
                continue
            if any(abs((parse_schedule_time(p['scheduled_at'],ZONE)-when).total_seconds())<60 for p in used):
                continue
            return when
    raise ValueError('No available saved account slot')


def publish():
    quality();api=api_instance();store=api._get_store();cfg=api._get_cfg()['repliz']
    client=ReplizClient(cfg['access_key'],cfg['secret_key'])
    raw=client.get('account',{'page':1,'limit':100});raw=raw.get('data',raw)
    account=next((a for a in raw.get('docs',[]) if a.get('_id',a.get('id'))==ACCOUNT),None)
    if not account or account.get('username')!='anak.clip0' or account.get('type')!='instagram' or not account.get('isConnected',True):
        raise ValueError('Live destination is not the authorized Instagram account')
    profile=store.get('account_profile',ACCOUNT)
    clips={c['index']:c for c in read(OUT/'registered-clips.json')}
    # Alternate storytelling and montage, retaining the user's saved time slots.
    for index in read(OUT/'batch.json').get('publication_order',[1,6,2,5,3,4]):
        row=clips[index];history=store.publications()
        prior=next((p for p in history if p['clip_id']==row['clip_id'] and p['account_id']==ACCOUNT),None)
        if prior:
            # A storage connection reset occurred before create_schedule was
            # called. Retry once using the same reservation; never retry an
            # uncertain schedule submission or a provider-side post failure.
            if (prior['status']=='failed' and not prior.get('schedule_id')
                    and prior.get('uncertain_submission') is False
                    and str(prior.get('error','')).startswith('Exception saat upload ke storage:')
                    and prior.get('safe_storage_retry_count',0)<1):
                if prior['file_hash']!=row['sha256']:
                    raise ValueError('Retry file differs from the QA-approved bytes')
                retried=store.update_publication(prior['id'],{'status':'uploading','error':None,
                    'safe_storage_retry_count':prior.get('safe_storage_retry_count',0)+1},expected_status=('failed',))
                api._send_publication(retried)
                current=store.publication(prior['id'])
                print(json.dumps({k:current.get(k) for k in ['id','clip_title','status','schedule_id','scheduled_at','error']},ensure_ascii=True),flush=True)
                if current['status'] not in {'scheduled','published'}:
                    raise ValueError('Storage retry needs attention; no further automatic attempt')
                continue
            if prior['status'] not in {'scheduled','published'}:
                raise ValueError('A previous submission needs reconciliation before another attempt')
            print('Existing publication retained',prior['id'],prior['status'],flush=True)
            continue
        result=api.review_clip(row['clip_id'],{'action':'approve'})
        if result['status']!='ok':raise ValueError(result)
        clip=result['clip']
        if clip['file_hash']!=row['sha256']:
            raise ValueError('Reviewed file differs from the QA-approved bytes')
        when=next_slot(profile,history,datetime.now(timezone.utc))
        repeated=[p['id'] for p in history if p['account_id']==ACCOUNT and p['status'] in ACTIVE and overlapping(clip,p)]
        publication={'id':'pub_'+digest([clip['id'],ACCOUNT])[:24],
            'dedupe_key':digest({'clip_id':clip['id'],'account_id':ACCOUNT}),
            'clip_id':clip['id'],'clip_title':clip['title'],'clip_path':clip['path'],
            'campaign_id':CAMPAIGN,'campaign_version_id':clip['campaign_version_id'],
            'revision_id':clip['revision_id'],'file_hash':clip['file_hash'],'approval_hash':clip['approval_hash'],
            'account_id':ACCOUNT,'account_name':account['name'],'platform':'instagram',
            'audience_scope':clip['campaign_snapshot']['audience_scope'],
            'daily_limit':int(profile['daily_limit']),'timezone':ZONE,
            'scheduled_at':when.isoformat(),'local_day':when.astimezone(ZoneInfo(ZONE)).date().isoformat(),
            'caption':clip['captions']['instagram'],'status':'uploading','source_ranges':clip['source_ranges'],
            'allow_source_overlap':bool(repeated),
            'overlap_review':{'existing_publications':repeated,'same_clip_reposting':False,
                'reason':'Reviewed different edits: new original dialogue or a new montage; limited shared official training/payoff assets.'},
            'authorization':'User requested uploads to Anak.clipo and the campaign earning goal; user approved 4A + 1B + 1C editing styles.',
            'created_at':utc_now(),'error':None}
        store.reserve_publications([publication],validate_reservation)
        api._send_publication(publication)
        current=store.publication(publication['id'])
        print(json.dumps({k:current.get(k) for k in ['id','clip_title','status','schedule_id','scheduled_at','error']},ensure_ascii=True),flush=True)
        if current['status'] not in {'scheduled','published'}:
            raise ValueError('Provider needs attention; no blind resubmission')
    sync()


def sync():
    api=api_instance();store=api._get_store();cfg=api._get_cfg()['repliz']
    client=ReplizClient(cfg['access_key'],cfg['secret_key'])
    known={r['clip_id'] for r in read(OUT/'registered-clips.json')};rows=[]
    for publication in store.publications():
        if publication['clip_id'] not in known or publication['account_id']!=ACCOUNT:continue
        if publication.get('schedule_id'):
            fields=schedule_update(client.schedule(publication['schedule_id']))
            publication=store.update_publication(publication['id'],fields)
        rows.append({k:publication.get(k) for k in ['id','clip_id','clip_title','status','schedule_id','scheduled_at','post_id','post_url','error']})
    atomic_json(OUT/'publication-result.json',rows);print(json.dumps(rows,ensure_ascii=True),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['register','publish','sync']);parser.add_argument('--batch-dir',type=Path,default=OUT);parser.add_argument('--ipv4',action='store_true',help='Use IPv4 for this process when the local NAT64 route resets TLS connections');args=parser.parse_args()
    OUT=args.batch_dir.resolve()
    if args.ipv4:
        import socket
        import urllib3.util.connection
        urllib3.util.connection.allowed_gai_family=lambda:socket.AF_INET
    {'register':register,'publish':publish,'sync':sync}[args.action]()
