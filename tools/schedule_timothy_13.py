"""Upload the thirteen K-iDtHzEzu8 edits using the user's two-account schedule."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from itertools import combinations, permutations
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
from services.publishing import ReplizClient, eligible_accounts, matches_publication, schedule_update, validate_reservation
from services.storage import WorkflowStore, atomic_json, digest, utc_now

JOB = 'job_7d8185ab7d9c4795a61678c09c75b9b4'
CAMPAIGN = 'camp_43ef11ba'
ACCOUNTS = ['6ab7d8cb62caae1e044feb07', '6a6e52d862caae1e04ef51a3']
TIMES = ['07:00', '07:30', '19:00', '19:30']
ZONE = ZoneInfo('Asia/Makassar')
BATCH = 'timothy-K-iDtHzEzu8-13-20261021'
REPORT = ROOT / 'output/headless-timothy-K-iDtHzEzu8-20261019/publishing'


class HeadlessAPI(WebAPI):
    def _start_upload_worker(self):
        pass


def emit(value):
    message = json.dumps(value, ensure_ascii=True)
    print(re.sub(r'https?://[^\s"\']+', '[URL]', message), flush=True)


def read_remote(client):
    records = []
    for page in range(1, 101):
        data = client.get('schedule', {'page': page, 'limit': 100, 'accountIds[]': ACCOUNTS})
        data = data.get('data', data)
        records.extend(data.get('docs', []))
        if not data.get('hasNextPage'):
            return records
    raise ValueError('Provider schedule pagination did not finish.')


def available_slots(account_id, count, remote, now):
    """Fit 3-4 total posts on each active account-day, including existing posts."""
    used = [datetime.fromisoformat(r['scheduleAt'].replace('Z', '+00:00')).astimezone(ZONE)
            for r in remote if str(r.get('accountId')) == account_id and r.get('scheduleAt')
            and r.get('status') in {'pending', 'process', 'success'}]
    days = []
    for offset in range(15):
        day = now.astimezone(ZONE).date() + timedelta(days=offset)
        occupied = [t for t in used if t.date() == day]
        free = []
        for slot in TIMES:
            when = datetime.fromisoformat(day.isoformat() + 'T' + slot).replace(tzinfo=ZONE)
            if when < now + timedelta(minutes=30):
                continue
            if any(abs((t-when).total_seconds()) < 60 for t in occupied):
                continue
            free.append(when)
        days.append((len(occupied), free))

    @lru_cache(None)
    def fit(offset, remaining):
        if not remaining:
            return ()
        if offset == len(days):
            return None
        occupied, free = days[offset]
        results = []
        for take in range(min(remaining, len(free), max(0, 4-occupied)), -1, -1):
            if take and not 3 <= occupied + take <= 4:
                continue
            rest = fit(offset+1, remaining-take)
            if rest is not None:
                results.append(tuple(free[:take]) + rest)
        return min(results) if results else None

    result = fit(0, count)
    if result is None:
        raise ValueError('No complete 3-4/day plan fits the requested time windows.')
    return list(result)


def overlap_seconds(left, right):
    return sum(max(0, min(a['end_seconds'], b['end_seconds']) - max(a['start_seconds'], b['start_seconds']))
               for a in left.get('source_ranges', []) for b in right.get('source_ranges', [])
               if a.get('source_id') and a.get('source_id') == b.get('source_id'))


def split_clips(clips):
    weights = {(i, j): overlap_seconds(a, b) for i, a in enumerate(clips)
               for j, b in enumerate(clips) if i < j}
    def cost(indices):
        side = set(indices)
        return sum(w for (i, j), w in weights.items() if (i in side) == (j in side))
    first = set(min(combinations(range(len(clips)), (len(clips)+1)//2), key=cost))
    return [[c for i, c in enumerate(clips) if (i in first) == side] for side in [True, False]]


def spread(group, slots):
    weights = {(i, j): overlap_seconds(a, b) for i, a in enumerate(group)
               for j, b in enumerate(group) if i < j}
    def cost(order):
        positions = {c: i for i, c in enumerate(order)}
        return sum(w / (abs((slots[positions[i]]-slots[positions[j]]).total_seconds())/3600 + .5)
                   for (i, j), w in weights.items())
    order = min(permutations(range(len(group))), key=cost)
    return [group[i] for i in order]


def clean_caption(text):
    seen = set()
    def keep(match):
        key = match[0].casefold()
        if key in seen:
            return ''
        seen.add(key)
        return match[0]
    text = re.sub(r'(?<!\w)#[\w]+', keep, text)
    text = '\n'.join(re.sub(r'[ \t]{2,}', ' ', line).strip() for line in text.splitlines())
    return re.sub(r'\n{3,}', '\n\n', text).strip()


def prepare(api, client):
    path = REPORT / 'plan.json'
    if path.exists():
        saved = json.loads(path.read_text(encoding='utf-8'))
        if saved.get('batch_id') != BATCH or len(saved.get('assignments', [])) != 13:
            raise ValueError('The saved batch differs from this request.')
        return saved
    cfg, store = api._get_cfg(), api._get_store()
    if cfg.get('timezone') != ZONE.key:
        raise ValueError('The saved timezone differs from WITA.')
    clips = sorted([c for c in store.list('clip') if c.get('job_id') == JOB], key=lambda c: c['path'])
    if len(clips) != 13:
        raise ValueError('Expected exactly the thirteen rendered clips.')
    for clip in clips:
        verify_clip_files(clip)
    campaign = next(c for c in cfg['campaigns'] if c['id'] == CAMPAIGN)
    response = api.get_repliz_accounts()
    if response.get('status') != 'ok':
        raise ValueError(response.get('message'))
    allowed = eligible_accounts(campaign, store.list('account_profile'), response['accounts'])
    accounts = {str(a['_id']): a for a, p in allowed}
    if set(accounts) != set(ACCOUNTS) or any(a['type'] != 'tiktok' for a in accounts.values()):
        raise ValueError('The two selected TikTok accounts must be connected and eligible.')
    existing = store.publications()
    if any(p['clip_id'] in {c['id'] for c in clips} and p['status'] != 'cancelled' for p in existing):
        raise ValueError('These clips already have publications; reconcile the saved batch.')
    remote = read_remote(client)
    if any(r.get('title') in {c['title'] for c in clips} for r in remote):
        raise ValueError('A target title already exists remotely; reconcile before submission.')
    usage = client.get('storage/statistic');usage = usage.get('data', usage)
    size = sum(Path(publication_media(c, 'tiktok')['path']).stat().st_size for c in clips)
    if usage.get('usage', {}).get('free', 0) < size:
        raise ValueError('Insufficient provider storage.')
    now = datetime.now(timezone.utc)
    groups = split_clips(clips)
    slots = [available_slots(aid, len(group), remote, now) for aid, group in zip(ACCOUNTS, groups)]
    atomic_json(REPORT / 'before-review.json', clips)
    atomic_json(REPORT / 'before-profiles.json', [p for a, p in allowed])
    for a, profile in allowed:
        updated = {**profile, 'daily_limit': 4, 'upload_times': TIMES}
        store.put('account_profile', profile.get('id') or profile['account_id'], updated)
    reviewed = {}
    for clip in clips:
        result = api.review_clip(clip['id'], {'action': 'approve', 'caption': clean_caption(clip['caption'])})
        if result.get('status') != 'ok':
            raise ValueError(result.get('message'))
        reviewed[clip['id']] = result['clip']
        atomic_json(Path(clip['path']).parent / 'data.json', result['clip'])
    rows, history = [], list(existing)
    for aid, group, times in zip(ACCOUNTS, groups, slots):
        for clip, when in zip(spread(group, times), times):
            clip = reviewed[clip['id']]
            media = publication_media(clip, 'tiktok')
            row = {'id': 'pub_' + digest({'batch': BATCH, 'clip': clip['id']})[:32],
                   'dedupe_key': digest({'clip_id': clip['id'], 'account_id': aid}),
                   'batch_id': BATCH, 'clip_id': clip['id'], 'clip_title': clip['title'],
                   'clip_path': media['path'], 'file_hash': media['file_hash'],
                   'campaign_id': CAMPAIGN, 'campaign_version_id': clip.get('campaign_version_id'),
                   'revision_id': clip['revision_id'], 'approval_hash': clip['approval_hash'],
                   'account_id': aid, 'account_name': accounts[aid]['name'], 'platform': 'tiktok',
                   'audience_scope': campaign['audience_scope'], 'daily_limit': 4,
                   'timezone': ZONE.key, 'upload_times': TIMES,
                   'scheduled_at': when.astimezone(timezone.utc).isoformat(), 'local_day': when.date().isoformat(),
                   'caption': publication_caption(clip, 'tiktok'), 'status': 'queued', 'error': None,
                   'source_ranges': clip.get('source_ranges', []), 'created_at': utc_now(),
                   'allow_source_overlap': True,
                   'overlap_authorization': 'User requested uploading all thirteen distinct rendered candidates across two accounts.'}
            validate_reservation(row, history, now=now)
            rows.append(row);history.append(row)
    rows.sort(key=lambda p: (p['scheduled_at'], ACCOUNTS.index(p['account_id'])))
    plan = {'batch_id': BATCH, 'job_id': JOB, 'timezone': ZONE.key, 'created_at': utc_now(),
            'authorization': 'User requested upload to two accounts, 3-4 per account per day, WITA morning/evening, earliest available slot.',
            'daily_totals_include_existing_posts': True, 'old_schedules_modified': False, 'assignments': rows}
    atomic_json(path, plan)
    write_csv(rows, REPORT / 'jadwal-rencana.csv')
    return plan


def write_csv(rows, path):
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['Clip', 'Akun', 'Tanggal WITA', 'Jam WITA', 'Status', 'ID Repliz'])
        for p in rows:
            t = datetime.fromisoformat(p['scheduled_at']).astimezone(ZONE)
            writer.writerow([p['clip_title'], p['account_name'], t.date().isoformat(), t.strftime('%H:%M'), p['status'], p.get('schedule_id', '')])


def reserve(api, plan):
    store = api._get_store();token = 'preview_' + BATCH
    saved = store.get('distribution_preview', token)
    if saved and saved.get('confirmed'):
        return
    store.put('distribution_preview', token, {'id': token, 'assignments': plan['assignments'], 'timezone': ZONE.key, 'created': time.time()})
    result = api.confirm_distribution(token)
    if result.get('status') != 'ok':
        raise ValueError(result.get('message'))
    emit({'reserved': result['total_scheduled']})


def upload(api, plan):
    if not api.worker_enabled:
        raise ValueError('Another app worker owns the queue; do not start a competing sender.')
    store = api._get_store()
    def send(row):
        current = store.publication(row['id'])
        if current['status'] == 'queued' or (current['status'] == 'failed' and not current.get('uncertain_submission') and not current.get('schedule_id')):
            current = store.update_publication(current['id'], {'status': 'uploading', 'attempted_at': utc_now()}, expected_status={'queued', 'failed'})
            api._send_publication(current)
        current = store.publication(row['id'])
        emit({'clip': current['clip_title'], 'account': current['account_name'], 'status': current['status'], 'error': current.get('error')})
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(send, plan['assignments']))


def verify(api, client, plan):
    store, problems = api._get_store(), []
    for row in plan['assignments']:
        current = store.publication(row['id'])
        try:
            if current.get('uncertain_submission') and current.get('media_url'):
                store.update_publication(current['id'], client.reconcile(current))
                current = store.publication(current['id'])
            if not current.get('schedule_id'):
                raise ValueError(current.get('error') or current['status'])
            raw = client.schedule(current['schedule_id'])
            if not matches_publication(raw.get('data', raw), current):
                raise ValueError('Provider account, media, caption, or time differs from the saved plan.')
            update = schedule_update(raw)
            if update.get('status') not in {'scheduled', 'publishing', 'published'}:
                raise ValueError(update.get('error') or 'Provider did not confirm the schedule.')
            store.update_publication(current['id'], {**update, 'verified_at': utc_now()})
        except Exception as exc:
            problems.append({'publication_id': row['id'], 'error': str(exc)})
    records = [store.publication(p['id']) for p in plan['assignments']]
    result = {'batch_id': BATCH, 'verified_at': utc_now(), 'total': len(records),
              'statuses': dict(Counter(p['status'] for p in records)),
              'per_account': dict(Counter(p['account_name'] for p in records)),
              'timezone': ZONE.key, 'old_schedules_modified': False, 'problems': problems, 'publications': records}
    atomic_json(REPORT / 'result.json', result)
    write_csv(records, REPORT / 'jadwal-upload.csv')
    lines = ['# Jadwal upload Timothy Ronald', '', f"{len(records)} clip; status: {result['statuses']}.", '',
             'Waktu: WITA. Slot: 07.00, 07.30, 19.00, 19.30. Kuota 3–4 per akun per hari menghitung posting lama yang sudah ada.', '',
             '| Tanggal | Jam | Akun | Clip | Status |', '|---|---|---|---|---|']
    for p in records:
        t = datetime.fromisoformat(p['scheduled_at']).astimezone(ZONE)
        lines.append(f"| {t.date()} | {t:%H:%M} | {p['account_name']} | {p['clip_title']} | {p['status']} |")
    (REPORT / 'JADWAL.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    emit({k: v for k, v in result.items() if k != 'publications'})
    return not problems


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['prepare', 'run', 'verify'])
    args = parser.parse_args();REPORT.mkdir(parents=True, exist_ok=True)
    api = HeadlessAPI()
    # Avoid recovering or claiming unrelated jobs/publications in the GUI database.
    api._workflow_store = WorkflowStore(ROOT / 'workflow.sqlite3')
    try:
        cfg = api._get_cfg()['repliz'];client = ReplizClient(cfg['access_key'], cfg['secret_key'])
        plan = prepare(api, client)
        if args.mode == 'prepare':
            emit({'prepared': len(plan['assignments']), 'per_account': dict(Counter(p['account_name'] for p in plan['assignments'])),
                  'days': dict(Counter(p['local_day'] for p in plan['assignments'])), 'worker_lease': api.worker_enabled})
            return 0
        if args.mode == 'run':
            reserve(api, plan);upload(api, plan)
        return 0 if verify(api, client, plan) else 1
    finally:
        api._worker_lease.close()


if __name__ == '__main__':
    raise SystemExit(main())
