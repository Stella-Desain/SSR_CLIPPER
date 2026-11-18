"""Schedule the user's twelve reviewed, quieter clips without changing old posts."""
import argparse
from collections import Counter
import csv
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import re
import sys
import time
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app import WebAPI
from services.account_tags import publication_caption
from services.clip_variants import publication_media, verify_clip_files
from services.publishing import ReplizClient, account_limit, eligible_accounts, matches_publication, schedule_update, validate_reservation
from services.scheduling import normalize_upload_times, scheduling_timezone
from services.storage import atomic_json, digest, utc_now

JOB = 'job_5525f7e9d1bc4d0b946a3ec835a386bb'
CAMPAIGN = 'camp_43ef11ba'
ACCOUNTS = ['6ab7d8cb62caae1e044feb07', '6a6e52d862caae1e04ef51a3']
SLOTS = ['07:00', '08:00', '19:00', '20:00']
ZONE = ZoneInfo('Asia/Makassar')
REPORT = ROOT / 'output/headless-timothy-jWVNlLLQGc0-20261013/scheduling-12'


class HeadlessAPI(WebAPI):
    def _start_upload_worker(self):
        # The current lease owner sends the durable queue, not a second worker.
        pass


def output(data):
    print(re.sub(r'https?://[^\s"\']+', '[URL]', json.dumps(data, ensure_ascii=True)), flush=True)


def remote_schedules(client):
    records = []
    for page in range(1, 101):
        result = client.get('schedule', {'page': page, 'limit': 100, 'accountIds[]': ACCOUNTS})
        data = result.get('data', result)
        records.extend(data.get('docs', []))
        if not data.get('hasNextPage'):
            return records
    raise ValueError('Remote schedule pagination did not finish.')


def assignments(clips, campaign, profiles, accounts, existing, start):
    if len(clips) != 12:
        raise ValueError('Expected exactly twelve clips.')
    profiles = {p['account_id']: p for p in profiles}
    accounts = {str(a['_id']): a for a in accounts}
    history, result = list(existing), []
    batch = 'timothy-12-' + start.isoformat()
    for index, clip in enumerate(clips):
        if clip.get('review_status') != 'approved' or not clip.get('approval_hash'):
            raise ValueError('Every clip must pass the existing review gate.')
        aid = ACCOUNTS[index % 2]
        day = start + timedelta(days=index // 4)
        when = datetime.fromisoformat(day.isoformat() + 'T' + SLOTS[index % 4]).replace(tzinfo=ZONE)
        media = publication_media(clip, 'tiktok')
        item = {
            'id': 'pub_' + digest({'batch': batch, 'clip': clip['id']})[:32],
            'dedupe_key': digest({'clip_id': clip['id'], 'account_id': aid}),
            'batch_id': batch, 'clip_id': clip['id'], 'clip_title': clip['title'],
            'clip_path': media['path'], 'campaign_id': CAMPAIGN,
            'campaign_version_id': clip.get('campaign_version_id'), 'revision_id': clip['revision_id'],
            'file_hash': media['file_hash'], 'approval_hash': clip['approval_hash'],
            'account_id': aid, 'account_name': accounts[aid]['name'], 'platform': 'tiktok',
            'audience_scope': campaign['audience_scope'], 'daily_limit': account_limit(campaign, profiles[aid]),
            'timezone': ZONE.key, 'upload_times': normalize_upload_times(profiles[aid].get('upload_times')),
            'scheduled_at': when.astimezone(timezone.utc).isoformat(), 'local_day': day.isoformat(),
            'schedule_edited': True, 'caption': publication_caption(clip, 'tiktok'), 'status': 'queued',
            'source_ranges': clip.get('source_ranges', []), 'created_at': utc_now(), 'error': None,
        }
        validate_reservation(item, history)
        result.append(item)
        history.append(item)
    return result


def prepare(api, client, start):
    plan_path = REPORT / 'plan.json'
    if plan_path.is_file():
        plan = json.loads(plan_path.read_text(encoding='utf-8'))
        if plan['start_date'] != start.isoformat():
            raise ValueError('A saved plan already uses a different start date.')
        return plan
    cfg, store = api._get_cfg(), api._get_store()
    if scheduling_timezone(cfg) != ZONE.key:
        raise ValueError('The saved timezone changed; expected WITA.')
    clips = sorted([c for c in store.list('clip') if c.get('job_id') == JOB], key=lambda c: c['path'])
    if len(clips) != 12 or any(c.get('music', {}).get('volume') != .2 for c in clips):
        raise ValueError('Expected the exact twelve music-20-percent revisions.')
    for clip in clips:
        verify_clip_files(clip)
    account_result = api.get_repliz_accounts()
    if account_result.get('status') != 'ok':
        raise ValueError(account_result.get('message'))
    accounts = [a for a in account_result['accounts'] if a['_id'] in ACCOUNTS]
    campaign = next(c for c in cfg['campaigns'] if c['id'] == CAMPAIGN)
    allowed = eligible_accounts(campaign, store.list('account_profile'), accounts)
    if {a['_id'] for a, _ in allowed} != set(ACCOUNTS) or any(a['type'] != 'tiktok' for a in accounts):
        raise ValueError('Both exact TikTok accounts must be connected and eligible.')
    existing = store.publications()
    if any(p['clip_id'] in {c['id'] for c in clips} and p['status'] != 'cancelled' for p in existing):
        raise ValueError('Target clips already have publications; do not create another plan.')
    remote = remote_schedules(client)
    days = {(start + timedelta(days=i)).isoformat() for i in range(3)}
    for record in remote:
        when = record.get('scheduleAt')
        if when and record.get('status') in ('pending', 'process', 'success'):
            day = datetime.fromisoformat(when.replace('Z', '+00:00')).astimezone(ZONE).date().isoformat()
            if day in days:
                raise ValueError('The requested three-day window already contains other provider posts.')
        if record.get('title') in {c['title'] for c in clips}:
            raise ValueError('A target title already exists at the provider; reconcile before submitting.')
    usage = client.get('storage/statistic')
    free = usage.get('usage', {}).get('free')
    size = sum(Path(publication_media(c, 'tiktok')['path']).stat().st_size for c in clips)
    if isinstance(free, (int, float)) and free < size:
        raise ValueError('Repliz storage is insufficient for this batch.')
    REPORT.mkdir(parents=True, exist_ok=True)
    atomic_json(REPORT / 'before-review.json', clips)
    reviewed = []
    for clip in clips:
        result = api.review_clip(clip['id'], {'action': 'approve'})
        if result.get('status') != 'ok':
            raise ValueError(result.get('message'))
        reviewed.append(result['clip'])
        atomic_json(Path(clip['path']).parent / 'data.json', result['clip'])
    rows = assignments(reviewed, campaign, store.list('account_profile'), accounts, existing, start)
    plan = {'start_date': start.isoformat(), 'timezone': ZONE.key, 'assignments': rows,
            'authorization': 'User requested all twelve clips, six per account, four per day; confirmed October 19 without changing old schedules.',
            'music_volume': .2, 'created_at': utc_now()}
    atomic_json(plan_path, plan)
    return plan


def reserve(api, plan):
    store = api._get_store()
    token = 'preview_' + digest({'batch': plan['start_date'], 'job': JOB})[:32]
    saved = store.get('distribution_preview', token)
    if saved and saved.get('confirmed'):
        return
    store.put('distribution_preview', token, {'id': token, 'assignments': plan['assignments'],
        'timezone': ZONE.key, 'created': time.time()})
    result = api.confirm_distribution(token)
    if result.get('status') != 'ok':
        raise ValueError(result.get('message'))
    output({'reserved': result['total_scheduled'], 'worker_owned_by_command': api.worker_enabled})


def upload(api, plan):
    store = api._get_store()
    if api.worker_enabled:
        for item in plan['assignments']:
            current = store.publication(item['id'])
            if current['status'] == 'queued':
                current = store.update_publication(item['id'], {'status': 'uploading', 'attempted_at': utc_now()}, expected_status={'queued'})
                api._send_publication(current)
                current = store.publication(item['id'])
                output({'clip': current['clip_title'], 'status': current['status'], 'error': current.get('error')})
                if any(code in str(current.get('error', '')) for code in ('HTTP 401', 'HTTP 402', 'HTTP 403')):
                    break
    else:
        deadline, previous = time.monotonic() + 1200, None
        while time.monotonic() < deadline:
            statuses = Counter(store.publication(p['id'])['status'] for p in plan['assignments'])
            if statuses != previous:
                output({'existing_app_worker': dict(statuses)})
                previous = statuses
            if not any(statuses.get(s, 0) for s in ('queued', 'uploading', 'publishing')):
                return
            time.sleep(5)


def verify(api, client, plan):
    store, problems = api._get_store(), []
    for item in plan['assignments']:
        current = store.publication(item['id'])
        try:
            if current.get('uncertain_submission') and current.get('media_url'):
                store.update_publication(current['id'], client.reconcile(current))
                current = store.publication(current['id'])
            if not current.get('schedule_id'):
                raise ValueError(current.get('error') or current['status'])
            raw = client.schedule(current['schedule_id'])
            if not matches_publication(raw.get('data', raw), current):
                raise ValueError('Provider account, caption, media, or time differs from the saved plan.')
            update = schedule_update(raw)
            if update.get('status') != 'scheduled':
                raise ValueError(update.get('error') or 'Provider did not confirm a future schedule.')
            store.update_publication(current['id'], {**update, 'verified_at': utc_now()})
        except Exception as exc:
            problems.append({'publication_id': item['id'], 'error': re.sub(r'https?://\S+', '[URL]', str(exc))})
    records = [store.publication(p['id']) for p in plan['assignments']]
    report = {'total': len(records), 'statuses': dict(Counter(p['status'] for p in records)),
              'per_account': dict(Counter(p['account_name'] for p in records)), 'timezone': ZONE.key,
              'music_volume': .2, 'old_schedules_modified': False, 'problems': problems, 'publications': records}
    atomic_json(REPORT / 'result.json', report)
    with (REPORT / 'jadwal.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['Clip', 'Akun', 'Tanggal WITA', 'Jam WITA', 'Status', 'ID Repliz'])
        for p in records:
            when = datetime.fromisoformat(p['scheduled_at']).astimezone(ZONE)
            writer.writerow([p['clip_title'], p['account_name'], when.date().isoformat(), when.strftime('%H:%M'), p['status'], p.get('schedule_id', '')])
    output({k: v for k, v in report.items() if k != 'publications'})
    return not problems


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['prepare', 'run', 'verify'])
    parser.add_argument('--start-date', type=date.fromisoformat, required=True)
    args = parser.parse_args()
    api = HeadlessAPI()
    try:
        cfg = api._get_cfg()['repliz']
        client = ReplizClient(cfg['access_key'], cfg['secret_key'])
        plan = prepare(api, client, args.start_date)
        if args.mode == 'prepare':
            output({'prepared': len(plan['assignments']), 'start_date': plan['start_date']})
            return 0
        if args.mode == 'run':
            reserve(api, plan)
            upload(api, plan)
        return 0 if verify(api, client, plan) else 1
    finally:
        api._worker_lease.close()


if __name__ == '__main__':
    raise SystemExit(main())
