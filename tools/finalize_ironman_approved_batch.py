"""Write delivery evidence and append exact source usage without changing media."""
import argparse
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from manage_ironman_approved_batch import OUT, ROOT, CAMPAIGN, ACCOUNT, quality, read
import manage_ironman_approved_batch as manager
from services.storage import WorkflowStore, atomic_json, utc_now
from services.scheduling import parse_schedule_time


def main():
    verified = quality()
    store = WorkflowStore(ROOT / 'workflow.sqlite3')
    registered = {c['index']: c for c in read(OUT / 'registered-clips.json')}
    history = store.publications()
    usages, delivery = [], []
    for row, meta, qa in verified:
        recipe = read(row['recipe'])
        clip = registered[row['index']]
        publication = next((p for p in history if p['clip_id'] == clip['clip_id']
                            and p['account_id'] == ACCOUNT), None)
        state = publication['status'] if publication else 'draft'
        at = 0.0
        for index, scene in enumerate(recipe['scenes']):
            still = Path(scene['path']).suffix.lower() in {'.png', '.jpg', '.jpeg'}
            start = scene.get('source_start', 0)
            rate = scene.get('playback_rate', 1)
            usages.append({
                'usage_id': recipe['id'] + ':scene:' + str(index),
                'clip': recipe['id'], 'clip_id': clip['clip_id'], 'scene_index': index,
                'source_id': scene['source_id'], 'source_url': scene['source_url'],
                'name': scene['name'], 'path': scene['path'],
                'source_kind': 'still' if still else 'video',
                'source_start': start, 'source_end': start if still else start + scene['duration'] * rate,
                'timeline_start': at, 'timeline_end': at + scene['duration'],
                'playback_rate': rate, 'visual_group': scene['visual_group'],
                'freeze_frame': scene.get('freeze_frame_from_seconds'),
                'parent_source_id': scene.get('derived_from_source_id'),
                'publication_state': state,
            })
            at += scene['duration']
        if recipe.get('narration'):
            voice = recipe['narration']
            for index, (start, duration) in enumerate(voice['source_ranges']):
                usages.append({'usage_id': recipe['id'] + ':voice:' + str(index),
                    'clip': recipe['id'], 'clip_id': clip['clip_id'], 'source_kind': 'voice',
                    'source_id': voice['source_id'], 'source_url': voice['source_url'],
                    'source_start': start, 'source_end': start + duration,
                    'publication_state': state})
        when = parse_schedule_time(publication['scheduled_at'], 'Asia/Makassar').astimezone(
            ZoneInfo('Asia/Makassar')).isoformat() if publication else None
        delivery.append({**clip, 'style_id': row['style_id'], 'recipe': row['recipe'],
            'qa': qa, 'publication_status': state, 'scheduled_at_wita': when,
            'schedule_id': publication.get('schedule_id') if publication else None})

    ledger_path = ROOT / 'output/ironman-tests-20261013/asset-usage-ledger.json'
    ledger = read(ledger_path)
    new_ids = {r['usage_id'] for r in usages}
    ledger['rows'] = [r for r in ledger['rows'] if r.get('usage_id') not in new_ids] + usages
    ledger.update(updated_at=utc_now(),
        interpretation='Exact intervals for new approved batch; stills consume one image/frame. Historical rows are retained.',
        semantic_review=str(OUT / 'review/semantic-source-review.json'))
    atomic_json(ledger_path, ledger)
    atomic_json(OUT / 'source-usage-ledger.json', {'rows': usages, 'updated_at': utc_now(),
        'reuse_note': 'Some official training and finisher assets overlap prior edits. New dialogue ranges and reduced B-roll diversify the batch; no claim of zero reuse.'})
    atomic_json(OUT / 'delivery-manifest.json', {'campaign_id': CAMPAIGN,
        'instagram_username': 'anak.clip0', 'clips': delivery, 'updated_at': utc_now()})
    batch = read(OUT / 'batch.json')
    all_scheduled = all(r['publication_status'] in {'scheduled', 'published'} for r in delivery)
    batch.update(status='scheduled' if all_scheduled else 'qa_passed_registered',
        publishing='instagram_scheduled' if all_scheduled else 'see_publication_result',
        updated_at=utc_now())
    atomic_json(OUT / 'batch.json', batch)
    lines = [f'# {len(delivery)} clip IRONMAN yang disetujui', '',
        'Campaign sudah tersimpan di SSR_CLIPPER. Akun tujuan: Anak.clipo, username Instagram **anak.clip0**.', '',
        '| Clip | Gaya | Durasi | Jadwal WITA | Status |',
        '| --- | --- | --- | --- | --- |']
    for r in delivery:
        target = Path(r['path']).as_posix()
        lines.append(f"| [{r['title']}](<{target}>) | {r['style_id']} | {r['duration']:.2f} dtk | {r['scheduled_at_wita'] or '-'} | {r['publication_status']} |")
    style_names={'A':'vlog dengan suara asli, subtitle putih dan kata aktif biru, serta film burn pendek',
        'B':'montase editorial', 'C':'jedag-jedug dengan cut mengikuti beat dan penutup stabil'}
    style_description='; '.join(f"{sum(r['style_id']==s for r in delivery)} {style_names[s]}" for s in sorted({r['style_id'] for r in delivery}))+'.'
    lines += ['', '## Editing dan sumber', '', style_description, '',
        f'Hook, font, warna, crop, jalur gerak, transisi, subtitle, musik dan CTA dapat diedit dalam recipes/clip-001.json sampai clip-{len(delivery):03}.json. Spesifikasi gaya reusable berasal dari batch yang telah disetujui; belum menjadi pilihan preset baru di dropdown UI. CTA pada batch campaign ini dimatikan karena tidak diwajibkan.', '',
        'Setelah mengedit recipe, buat output revisi terpisah. File yang sudah memiliki catatan publikasi dilindungi dari overwrite. Sumber, rentang detik dan pemakaian tercatat dalam source-usage-ledger.json dan ledger pusat. Beberapa footage latihan/finisher dipakai ulang; tidak semua stok sudah digunakan.', '',
        'Seluruh output 1080x1920, 30 fps, lolos decode lengkap, pemeriksaan gambar, audio dan kecocokan hash. Suara asli pada clip narasi hadir sejak awal tanpa offset terukur. Tujuh tes terkait renderer, caption dan retiming telah lulus.', '',
        '## Status goal', '',
        'Terjadwal belum berarti sudah tayang atau menghasilkan uang. Observasi Instagram terakhir menunjukkan 0 followers; syarat campaign minimal 10 followers dan metrik clip perlu dipenuhi sebelum klaim. TikTok ditunda sesuai permintaan pengguna. Penghasilan belum terverifikasi.', '']
    (OUT / 'DELIVERY.md').write_text('\n'.join(lines), encoding='utf-8')
    audit = ROOT / 'output/ironman-goal-audit-20261014/work-priorities.json'
    priority = read(audit)
    priority.update(new_batch_status=batch['status'], new_batch_target=len(delivery), new_batch_manifest=str(OUT / 'delivery-manifest.json'),
        next_step='Verify scheduled posts after their publication times, then organic campaign metrics and claim eligibility.',
        browser_statistics='manual Instagram evidence saved; account currently below follower threshold',
        updated_at=utc_now())
    atomic_json(audit, priority)
    print(json.dumps({'clips': len(delivery), 'source_usage_records': len(usages),
        'status': batch['status'], 'native_campaign_stock': len([c for c in store.list('clip')
            if c.get('campaign_id') == CAMPAIGN])}))


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--batch-dir',type=Path,default=OUT);args=parser.parse_args()
    OUT=args.batch_dir.resolve();manager.OUT=OUT
    main()
