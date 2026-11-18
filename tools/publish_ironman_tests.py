"""Publish only the three QA-reviewed files to the explicitly requested IG account."""
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from setup_ironman_campaign import api_instance, ACCOUNT
from services.publishing import ReplizClient, schedule_update, validate_reservation
from services.storage import atomic_json, digest, utc_now

OUT = ROOT / 'output/ironman-tests-20261013'


def publish():
    qa = json.loads((OUT / 'qa-result.json').read_text(encoding='utf-8'))
    if not qa.get('passed') or not qa.get('visual_review_passed'):
        raise ValueError('Media and visual QA must pass before any upload')
    api = api_instance()
    store = api._get_store()
    accounts = api.get_repliz_accounts()
    if accounts['status'] != 'ok':
        raise ValueError('Cannot verify the destination account')
    account = next((a for a in accounts['accounts'] if str(a.get('_id', a.get('id'))) == ACCOUNT), None)
    if not account or account.get('type') != 'instagram' or account.get('name', '').casefold() != 'anak.clipo' or account.get('isConnected') is False:
        raise ValueError('Destination does not match the authorized Anak.clipo account')
    clips = json.loads((OUT / 'registered-clips.json').read_text(encoding='utf-8'))
    start = datetime.now(timezone.utc) + timedelta(minutes=2)
    for index, row in enumerate(clips):
        previous = next((p for p in store.publications() if p['clip_id'] == row['clip_id'] and p['account_id'] == ACCOUNT), None)
        if previous:
            print('Existing publication preserved', previous['id'], previous['status'], flush=True)
            continue
        result = api.review_clip(row['clip_id'], {'action': 'approve'})
        if result['status'] != 'ok':
            raise ValueError(result)
        clip = result['clip']
        approved = next(r for r in qa['clips'] if r['path'] == clip['path'])
        if approved['sha256'] != clip['file_hash']:
            raise ValueError('Rendered bytes changed after visual review')
        when = start + timedelta(minutes=index)
        publication = {'id': 'pub_' + digest([clip['id'], ACCOUNT])[:24],
            'dedupe_key': digest({'clip_id': clip['id'], 'account_id': ACCOUNT}),
            'clip_id': clip['id'], 'clip_title': clip['title'], 'clip_path': clip['path'],
            'campaign_id': clip['campaign_id'], 'campaign_version_id': clip['campaign_version_id'],
            'revision_id': clip['revision_id'], 'file_hash': clip['file_hash'], 'approval_hash': clip['approval_hash'],
            'account_id': ACCOUNT, 'account_name': account['name'], 'platform': 'instagram',
            'audience_scope': clip['campaign_snapshot']['audience_scope'], 'daily_limit': 3,
            'timezone': 'Asia/Makassar', 'scheduled_at': when.isoformat(),
            'local_day': when.astimezone(ZoneInfo('Asia/Makassar')).date().isoformat(),
            'caption': clip['captions']['instagram'], 'status': 'uploading',
            'source_ranges': clip['source_ranges'], 'allow_source_overlap': False,
            'created_at': utc_now(), 'error': None,
            'authorization': 'User explicitly requested three test videos uploaded to Anak.clipo in this chat.'}
        store.reserve_publications([publication], validate_reservation)
        api._send_publication(publication)
        current = store.publication(publication['id'])
        print(json.dumps({k: current.get(k) for k in ['id','clip_title','status','schedule_id','scheduled_at','error']}, ensure_ascii=True), flush=True)
        if current['status'] not in {'scheduled', 'published'}:
            raise RuntimeError('Publication needs attention; no blind resubmission')
    sync()


def sync():
    api = api_instance()
    store = api._get_store()
    cfg = api._get_cfg()['repliz']
    client = ReplizClient(cfg['access_key'], cfg['secret_key'])
    records = []
    for publication in store.publications():
        if publication.get('campaign_id') != 'camp_8d3c32dfe5b9' or publication.get('account_id') != ACCOUNT:
            continue
        if publication.get('schedule_id'):
            raw = client.schedule(publication['schedule_id'])
            fields = schedule_update(raw)
            # Preserve the provider evidence without authentication data.
            atomic_json(OUT / ('provider-' + publication['id'] + '.json'), raw)
            if fields.get('post_id') and not fields.get('post_url'):
                try:
                    content = client.content(fields['post_id'], ACCOUNT)
                    data = content.get('data', content)
                    url = data.get('permalink') or data.get('url') or data.get('postUrl')
                    if url:
                        fields['post_url'] = url
                except Exception:
                    pass
            publication = store.update_publication(publication['id'], fields)
        records.append({k: publication.get(k) for k in ['id','clip_id','clip_title','account_name','platform',
                       'status','schedule_id','scheduled_at','post_id','post_url','error']})
    atomic_json(OUT / 'publication-result.json', records)
    print(json.dumps(records, ensure_ascii=True), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['publish', 'sync'])
    args = parser.parse_args()
    {'publish': publish, 'sync': sync}[args.action]()
