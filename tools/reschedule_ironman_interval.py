"""Move existing pending schedules to the user's requested 25-minute cadence."""
import argparse
import copy
import json
import math
import socket
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import urllib3.util.connection
urllib3.util.connection.allowed_gai_family=lambda:socket.AF_INET

from setup_ironman_campaign import api_instance, ACCOUNT, ROOT
from services.publishing import ReplizClient, matches_publication, schedule_update, ACTIVE
from services.scheduling import publication_day
from services.storage import atomic_json, utc_now

CAMPAIGN='camp_8d3c32dfe5b9'
ZONE='Asia/Makassar'
OUT=ROOT/'output/ironman-spacing-20261014'
PLAN=OUT/'plan.json'
FIELDS=['title','description','topic','type','medias','meta','additionalInfo','replies']


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def connection():
    api=api_instance();cfg=api._get_cfg()['repliz']
    return api,api._get_store(),ReplizClient(cfg['access_key'],cfg['secret_key'])


def plan():
    if PLAN.exists():
        raise ValueError('An existing plan must be applied or inspected; do not invent a second queue.')
    api,store,client=connection()
    raw=client.get('account',{'page':1,'limit':100});data=raw.get('data',raw)
    account=next(a for a in data['docs'] if a.get('_id',a.get('id'))==ACCOUNT)
    assert account['username']=='anak.clip0' and account['type']=='instagram' and account.get('isConnected',True)
    history=store.publications()
    pending=sorted([p for p in history if p['account_id']==ACCOUNT and p['campaign_id']==CAMPAIGN
        and p['status']=='scheduled' and p.get('schedule_id')],key=lambda p:p['scheduled_at'])
    assert pending,'No pending Ironman schedules'
    # Enough lead time to finish all updates before the first post becomes due.
    now=datetime.now(timezone.utc)
    first=datetime.fromtimestamp(math.ceil((now+timedelta(minutes=8)).timestamp()/300)*300,timezone.utc)
    rows=[]
    for index,p in enumerate(pending):
        raw=client.schedule(p['schedule_id']);d=raw.get('data',raw)
        assert d.get('status')=='pending' and matches_publication(d,p),'Provider changed; inspect before editing'
        target=first+timedelta(minutes=25*index)
        rows.append({'id':p['id'],'clip_id':p['clip_id'],'title':p['clip_title'],
            'schedule_id':p['schedule_id'],'old_scheduled_at':p['scheduled_at'],
            'scheduled_at':target.isoformat(),'scheduled_at_wita':target.astimezone(ZoneInfo(ZONE)).isoformat(),
            'state':'planned','original_body':{k:copy.deepcopy(d[k]) for k in FIELDS},
            'templateId':d.get('templateId')})
    ids={r['id'] for r in rows}
    counts=Counter(publication_day(p,ZONE) for p in history if p['account_id']==ACCOUNT
        and p['status'] in ACTIVE and p['id'] not in ids)
    counts.update(datetime.fromisoformat(r['scheduled_at']).astimezone(ZoneInfo(ZONE)).date().isoformat() for r in rows)
    profile=store.get('account_profile',ACCOUNT)
    result={'status':'planned','created_at':utc_now(),'account_id':ACCOUNT,'username':'anak.clip0',
        'campaign_id':CAMPAIGN,'interval_minutes':25,'timezone':ZONE,
        'authorization':'upload dan beri jarak, setiaap 20-30 menit',
        'previous_daily_limit':profile['daily_limit'],
        'required_daily_limit':max(profile['daily_limit'],max(counts.values())),
        'profile_before':profile,'rows':rows,
        'api_reference':'https://docs.repliz.com/api/schedule/update-schedule'}
    atomic_json(PLAN,result)
    print(json.dumps({'count':len(rows),'interval_minutes':25,'first':rows[0]['scheduled_at_wita'],
        'last':rows[-1]['scheduled_at_wita'],'required_daily_limit':result['required_daily_limit']},ensure_ascii=True))


def apply():
    record=read(PLAN);api,store,client=connection()
    if record['status']=='planned':
        assert datetime.fromisoformat(record['rows'][0]['scheduled_at'])>datetime.now(timezone.utc)+timedelta(minutes=2)
    profile=store.get('account_profile',ACCOUNT)
    if profile['daily_limit']<record['required_daily_limit']:
        result=api.save_account_profile(ACCOUNT,{**profile,'daily_limit':record['required_daily_limit']})
        assert result['status']=='ok',result
    record['status']='applying';atomic_json(PLAN,record)
    for row in record['rows']:
        current=store.publication(row['id'])
        assert current['schedule_id']==row['schedule_id']
        raw=client.schedule(row['schedule_id']);d=raw.get('data',raw)
        target=row['scheduled_at']
        expected={**current,'scheduled_at':target}
        already_updated=matches_publication(d,expected)
        if not already_updated:
            assert d['status']=='pending' and matches_publication(d,{**current,'scheduled_at':row['old_scheduled_at']})
            assert datetime.fromisoformat(target)>datetime.now(timezone.utc)+timedelta(minutes=1)
            assert all(d[k]==row['original_body'][k] for k in FIELDS),'Post content changed since planning'
            body=copy.deepcopy(row['original_body'])
            body['scheduleAt']=target.replace('+00:00','Z')
            if row.get('templateId'):body['templateId']=row['templateId']
            row['state']='updating';atomic_json(PLAN,record)
            response=client.session.put('https://api.repliz.com/public/schedule/'+row['schedule_id'],
                json=body,auth=client.auth,timeout=25)
            response.raise_for_status()
            raw=client.schedule(row['schedule_id']);d=raw.get('data',raw)
        assert matches_publication(d,expected),'Updated schedule not confirmed; do not submit a new post'
        assert all(d[k]==row['original_body'][k] for k in FIELDS),'Unexpected content mutation'
        state=schedule_update(d)
        store.update_publication(row['id'],{**state,'scheduled_at':target,
            'local_day':datetime.fromisoformat(target).astimezone(ZoneInfo(ZONE)).date().isoformat(),
            'daily_limit':record['required_daily_limit'],'timezone':ZONE,
            'rescheduled_from':row['old_scheduled_at'],'requested_interval_minutes':25,
            'reschedule_authorization':record['authorization']},expected_status=('scheduled','publishing','published'))
        row.update(state='verified',provider_status=d['status'],verified_at=utc_now())
        atomic_json(PLAN,record)
        print(json.dumps({k:row[k] for k in ['title','schedule_id','scheduled_at_wita','state']},ensure_ascii=True),flush=True)
    record.update(status='applied',completed_at=utc_now());atomic_json(PLAN,record)
    # Save the user's preference without replacing other saved account settings.
    store.put('publishing_policy',ACCOUNT,{'id':ACCOUNT,'campaign_id':CAMPAIGN,'interval_minutes':25,
        'requested_range_minutes':[20,30],'authorization':record['authorization'],'updated_at':utc_now()})
    lines=['# Antrean Instagram · setiap 25 menit','',
        'Akun: **Anak.clipo (@anak.clip0)**. Semua waktu WITA. Jadwal lama diperbarui dengan ID yang sama.','',
        '| Clip | Tanggal | Jam | Status |','| --- | --- | --- | --- |']
    for row in record['rows']:
        t=datetime.fromisoformat(row['scheduled_at_wita'])
        lines.append(f"| {row['title']} | {t:%d-%m-%Y} | {t:%H:%M} | scheduled |")
    (OUT/'JADWAL.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['plan','apply']);args=p.parse_args()
    {'plan':plan,'apply':apply}[args.action]()
