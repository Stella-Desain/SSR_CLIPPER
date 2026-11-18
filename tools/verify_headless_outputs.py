"""Check every rendered file and create a local review index without opening UI."""
import argparse
import html
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.editing import file_sha256, probe_media
from services.speech_boundaries import seconds
from services.storage import atomic_json
from utils.helpers import get_ffmpeg_path


def editorial_notes(flags, decision_id=None):
    notes = []
    for flag in flags:
        targeted = 'decision_id' in flag or 'decision_ids' in flag
        matches = decision_id == flag.get('decision_id') or decision_id in flag.get('decision_ids', [])
        if (decision_id is None and not targeted) or (decision_id is not None and targeted and matches):
            notes.append(flag['note'])
    return notes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', required=True)
    parser.add_argument('--source-words', type=Path)
    parser.add_argument('--clips-directory', type=Path)
    parser.add_argument('--review-directory', type=Path)
    args = parser.parse_args()
    directory = Path(args.directory).resolve()
    run = json.loads((directory / 'run.json').read_text(encoding='utf-8'))
    editorial_path = directory / 'editorial-review.json'
    editorial = json.loads(editorial_path.read_text(encoding='utf-8')) if editorial_path.is_file() else {}
    review_flags = editorial.get('review_flags', [])
    folder = ROOT / 'output' / ('job-' + run['job_id'].removeprefix('job_')[:16])
    if args.clips_directory:
        folder = args.clips_directory.resolve()
    review_folder = args.review_directory.resolve() if args.review_directory else folder
    review_folder.mkdir(parents=True, exist_ok=True)
    plan = json.loads((folder / 'highlights.json').read_text(encoding='utf-8'))['highlights']
    words_path = args.source_words or directory / 'source/reviewed-source-words.json'
    if not words_path.is_file() and not args.source_words:
        words_path = directory / 'source/word-transcript.json'
    source = json.loads(words_path.read_text(encoding='utf-8'))
    words = [w for s in source['segments'] for w in s.get('words', []) if w['end'] > w['start']]
    results = []
    for index, highlight in enumerate(plan, 1):
        clip_dir = folder / f'clip-{index:03d}'
        if not (clip_dir / 'data.json').is_file():
            results.append({'index': index, 'title': highlight['title'], 'issues': ['missing_completed_clip']})
            continue
        metadata = json.loads((clip_dir / 'data.json').read_text(encoding='utf-8'))
        final = clip_dir / 'master.mp4'
        media = probe_media(final, get_ffmpeg_path())
        start, end = (seconds(highlight[k]) for k in ('start_time', 'end_time'))
        included = [w for w in words if w['end'] > start + .001 and w['start'] < end - .001]
        canvas = metadata['clip_plan']['template'].get('canvas', {'width': 1080, 'height': 1920})
        checks = {
            'valid_video_audio': media['has_video'] and media['has_audio'],
            'audio_measurement': metadata.get('audio_analysis', {}).get('status') == 'measured',
            'template_canvas': (media['width'], media['height']) == (canvas['width'], canvas['height']),
            'duration_matches_source': abs(media['duration'] - (end-start)) < .15,
            'campaign_duration': 28 <= media['duration'] <= 70.1,
            'music_verified': metadata.get('music', {}).get('mixed') is True and bool(metadata.get('music', {}).get('sha256')),
            'captions_present': metadata.get('has_captions') is True,
            'source_evidence': metadata.get('selection', {}).get('verified_source') is True,
            'caption_source_matches': metadata.get('caption_transcript_provenance', {}).get('source_sha256') == source['source_sha256'],
            'file_hash_matches': metadata.get('final_sha256') == file_sha256(final),
            'no_blockers': not metadata.get('blockers'),
            'no_mid_word_cut': bool(included) and included[0]['start'] >= start-.02 and included[-1]['end'] <= end+.02,
        }
        tail = subprocess.run([get_ffmpeg_path(), '-hide_banner', '-loglevel', 'error', '-threads', '1',
            '-ss', str(max(0, media['duration']-2)), '-i', str(final), '-map', '0:v:0', '-map', '0:a:0',
            '-threads', '1', '-f', 'null', '-'], capture_output=True, timeout=45,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        checks['tail_decodes'] = tail.returncode == 0
        issues = [name for name, passed in checks.items() if not passed]
        results.append({'index': index, 'title': metadata['title'], 'path': str(final),
            'template': metadata['editing_template']['preset_id'], 'duration': media['duration'],
            'canvas': [media['width'], media['height']], 'checks': checks, 'issues': issues,
            'last_words': ' '.join(w['word'].strip() for w in included[-10:]), 'warnings': metadata.get('warnings', []),
            'music_volume': metadata.get('music', {}).get('volume'),
            'review_notes': editorial_notes(review_flags, highlight.get('decision_id'))})
        print(f"VERIFIED {index}/{len(plan)} {'PASS' if not issues else issues}", flush=True)
    report = {'planned': len(plan), 'completed': sum('path' in r for r in results),
        'passed': sum(not r['issues'] for r in results), 'all_passed': all(not r['issues'] for r in results),
        'render_workers': run['execution']['render_workers'],
        'templates': dict(Counter(r.get('template') for r in results if 'template' in r)),
        'review_notes': editorial_notes(review_flags), 'clips': results}
    volumes = {r['music_volume'] for r in results if r.get('music_volume') is not None}
    mix_note = f'Musik {next(iter(volumes)) * 100:.0f}%.' if len(volumes) == 1 else ''
    atomic_json(directory / 'verification.json', report)
    execution = run['execution']
    model_note = (f"Model API terverifikasi melalui field balasan provider: {execution['verified_remote_model']}; "
                  f"reasoning: {execution['requested_reasoning_effort']}.") if execution.get('verified_remote_model') else (
        'Penilaian highlight dilakukan langsung dalam percakapan atas persetujuan pengguna; model API tidak terverifikasi.')
    lines = ['# Hasil clip Timothy Ronald', '',
        f"{report['completed']}/{len(plan)} clip selesai; {report['passed']} lolos pemeriksaan teknis.", '',
        model_note,
        f"Pekerjaan dijalankan tanpa GUI dengan {execution['render_workers']} worker render. Hasil menunggu review. {mix_note}", '',
        '| No. | Clip | Template | Durasi | Pemeriksaan |', '|---|---|---|---|---|']
    cards = []
    for r in results:
        if 'path' not in r:
            continue
        relative = Path(os.path.relpath(r['path'], review_folder)).as_posix()
        r['review_path'] = relative
        verdict = 'Lolos' if not r['issues'] else ', '.join(r['issues'])
        lines.append(f"| {r['index']} | [{r['title']}]({relative}) | {r['template']} | {r['duration']:.2f} dtk | {verdict} |")
        warning = ''.join(f'<p class="review-note">{html.escape(note)}</p>' for note in r.get('warnings', []))
        warning += ''.join(f'<p class="review-note">{html.escape(note)}</p>' for note in r['review_notes'])
        volume_label = f' · Musik {r["music_volume"] * 100:.0f}%' if r['music_volume'] is not None else ''
        cards.append(f'<article><h2>{r["index"]:02d}. {html.escape(r["title"])}</h2>{warning}<video controls preload="none" src="{relative}"></video><p>{html.escape(r["template"])} · {r["duration"]:.2f} detik · {r["canvas"][0]}×{r["canvas"][1]}{volume_label}</p><p>Akhir ucapan: {html.escape(r["last_words"])}</p></article>')
    if report['review_notes'] or any(r.get('review_notes') for r in results):
        lines += ['', '## Catatan sebelum publikasi', '']
        lines.extend(f'- {note}' for note in report['review_notes'])
        for r in results:
            lines.extend(f'- Clip {r["index"]:02d}: {note}' for note in r.get('review_notes', []))
    close_mix = [r for r in results if any(w.startswith('Musik terukur dekat') for w in r.get('warnings', []))]
    if close_mix:
        lines += ['', '## Pemeriksaan musik saat review', '',
                  'Musik terukur dekat dengan level suara sumber. Periksa kejelasan dialog dan benturan vokal pada clip berikut: ' +
                  ', '.join(f'{r["index"]:02d}' for r in close_mix) + '. Level mix dipertahankan sesuai permintaan.']
    flagged = [r for r in results if any(w.startswith('Puncak audio') for w in r.get('warnings', []))]
    if flagged:
        lines += ['', '## Pemeriksaan audio saat review', '',
                  f'{len(flagged)} clip memiliki peringatan puncak audio. Ini belum memastikan distorsi yang terdengar. Level mix dipertahankan sesuai permintaan.', '']
        lines.extend(f'- [{r["index"]:02d}. {r["title"]}]({r["review_path"]}): periksa suara saat review.' for r in flagged)
    (review_folder / 'HASIL.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    global_notes = f'<p>{html.escape(mix_note)}</p>' + ''.join(f'<p class="review-note">{html.escape(note)}</p>' for note in report['review_notes'])
    (review_folder / 'PREVIEW.html').write_text('<!doctype html><html lang="id"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Clip Timothy Ronald</title><style>body{margin:0;padding:24px;background:#f5f6f4;color:#17201a;font:16px system-ui}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr));gap:20px}article{min-width:0;background:white;border-radius:8px;padding:20px}h2{font-size:18px;overflow-wrap:anywhere}video{display:block;width:100%;max-height:500px;background:#111;border-radius:8px}p{line-height:1.5;overflow-wrap:anywhere}.review-note{background:#fff3cd;color:#614700;padding:10px;border-radius:8px}</style><h1>Clip Timothy Ronald</h1><p>' + f'{report["completed"]} clip selesai; {report["passed"]} lolos pemeriksaan teknis. Hasil menunggu review.' + '</p>' + global_notes + '<main>' + ''.join(cards) + '</main></html>', encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'clips'}, ensure_ascii=False))
    return 0 if report['all_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
