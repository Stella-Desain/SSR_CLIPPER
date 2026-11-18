"""Validate explicit chat-reviewed decisions against observed source words.

This helper does not infer audience fit or decide which story is complete.
"""
from __future__ import annotations
import argparse
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.editing import file_sha256, probe_media
from services.storage import atomic_json
from services.campaigns import normalize_campaign
from services.speech_boundaries import SpeechBoundaryAligner, parse_cues, seconds, timestamp
from services.highlight_profiles import _speech_cues, evaluate_selection, normalize_highlight_profile, profile_fingerprint, GATES
from utils.helpers import get_ffmpeg_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', required=True)
    parser.add_argument('--campaign', default='camp_43ef11ba')
    args = parser.parse_args()
    directory = Path(args.directory).resolve()
    observed = json.loads((directory / 'source/word-transcript.json').read_text(encoding='utf-8'))
    decisions = json.loads((directory / 'reviewed-decisions.json').read_text(encoding='utf-8'))
    source = directory / 'source/source.mp4'
    if file_sha256(source) != observed['source_sha256']:
        raise ValueError('Transkrip tidak berasal dari sumber run ini.')
    corrections_path = directory / 'transcript-corrections.json'
    if corrections_path.is_file():
        corrections = json.loads(corrections_path.read_text(encoding='utf-8'))
        if corrections.get('reviewed') is not True:
            raise ValueError('Koreksi ejaan transkrip belum diperiksa.')
        applied = []
        for segment in observed['segments']:
            ws = segment.get('words', [])
            for word in ws:
                token = word['word'].strip()
                target = corrections.get('replacements', {}).get(token.casefold())
                for timed in corrections.get('timed_replacements', []):
                    if token.casefold() == timed['from'].casefold() and timed['start_min'] <= word['start'] <= timed['start_max']:
                        target = timed['to']
                if target:
                    applied.append({'start': word['start'], 'end': word['end'], 'from': token, 'to': target})
                    word['word'] = ' ' + target
            for merge in corrections.get('merges', []):
                for i in range(len(ws)-len(merge['from'])+1):
                    group = ws[i:i+len(merge['from'])]
                    if ([w['word'].strip().casefold() for w in group] == [t.casefold() for t in merge['from']]
                            and merge['start_min'] <= group[0]['start'] <= merge['start_max']):
                        combined = {**group[0], 'end': group[-1]['end'], 'word': ' ' + merge['to']}
                        applied.append({'start': combined['start'], 'end': combined['end'],
                                        'from': ' '.join(merge['from']), 'to': merge['to']})
                        ws[i:i+len(group)] = [combined]
                        break
            segment['text'] = ''.join(w['word'] for w in ws).strip()
        observed['lexical_corrections'] = applied
        observed['lexical_correction_review'] = str(corrections_path)
    cfg = json.loads((ROOT / 'config.json').read_text(encoding='utf-8'))
    campaign = normalize_campaign(next(c for c in cfg['campaigns'] if c['id'] == args.campaign))
    profile = normalize_highlight_profile(campaign['highlight_profile'], campaign)
    words = [copy.deepcopy(w) for s in observed['segments'] for w in s.get('words', []) if w['end'] > w['start']]
    cuts = {float(d[k]) for d in decisions for k in ('start', 'end')}
    endings = {float(d['end']) for d in decisions}
    segments = []
    for original in observed['segments']:
        group = []
        for word in original.get('words', []):
            if word['end'] <= word['start']:
                continue
            if group and any(group[-1]['end'] <= cut <= word['start'] for cut in cuts):
                segments.append({'start': group[0]['start'], 'end': group[-1]['end'],
                                 'text': ''.join(w['word'] for w in group).strip(), 'words': group})
                group = []
            group.append(copy.deepcopy(word))
        if group:
            segments.append({'start': group[0]['start'], 'end': group[-1]['end'],
                             'text': ''.join(w['word'] for w in group).strip(), 'words': group})
    for segment in segments:
        if any(abs(segment['end'] - end) < .002 for end in endings):
            segment['text'] = segment['text'].rstrip('.?!') + '.'
    transcript = '\n'.join(f"[{timestamp(s['start'])} - {timestamp(s['end'])}] {s['text']}" for s in segments)
    srt = '\n\n'.join(f"{i}\n{timestamp(s['start'])} --> {timestamp(s['end'])}\n{s['text']}" for i, s in enumerate(segments, 1)) + '\n'
    srt_path = directory / 'source/reviewed-source.srt'
    srt_path.write_text(srt, encoding='utf-8')
    observed.update(segments=segments, boundary_review=str(directory / 'reviewed-decisions.json'))
    words_path = directory / 'source/reviewed-source-words.json'
    atomic_json(words_path, observed)
    media = probe_media(source, get_ffmpeg_path())
    aligner = SpeechBoundaryAligner(transcript, media['duration'], path=source, ffmpeg=get_ffmpeg_path())
    cues = parse_cues(transcript)
    accepted, rejected, seen = [], [], set()
    for d in decisions:
        try:
            if d.get('reviewed') is not True or not isinstance(d.get('gates'), dict):
                raise ValueError('Penilaian semantik belum diperiksa dalam chat.')
            start, end = float(d['start']), float(d['end'])
            if (start, end) in seen:
                raise ValueError('Rentang kandidat duplikat.')
            seen.add((start, end))
            included_words = [w for w in words if w['end'] > start + .001 and w['start'] < end - .001]
            if not included_words or included_words[0]['start'] < start - .002 or included_words[-1]['end'] > end + .002:
                raise ValueError('Rentang memotong kata yang teramati.')
            item = {'decision_id': d['id'], 'title': d['title'], 'description': d['description'],
                    'start_time': timestamp(start), 'end_time': timestamp(end), 'agent_music_id': str(d['music_id']),
                    'agent_music_start': float(d.get('music_start', 0)), 'agent_music_reason': d.get('music_reason', '')}
            item = aligner.align(item, campaign['brief']['durasi_min'], campaign['brief']['durasi_max'])
            if abs(seconds(item['end_time']) - end) > .002:
                raise ValueError('Batas akhir berubah setelah pemeriksaan; perlu review ulang.')
            included = _speech_cues(cues, start, end)
            mid = max(2, len(included)//2)
            proof = [('opening', included[:2]), ('message', included[mid:mid+2]), ('ending', included[-2:])]
            evidence = [{'part': part, 'start_time': timestamp(max(start, group[0]['start'])),
                         'end_time': timestamp(min(end, group[-1]['end'])), 'quote': ' '.join(s['text'] for s in group)}
                        for part, group in proof if group]
            item['hook_text'] = ' '.join(s['text'] for s in included[:2])
            item['selection'] = {'version': 1, 'profile_hash': profile_fingerprint(profile),
                'scores': d['scores'], 'gates': {g: d['gates'].get(g) for g in GATES},
                'reason': d['reason'], 'matched_patterns': d.get('matched_patterns', []), 'evidence': evidence}
            assessment = evaluate_selection(item, profile, transcript, media['duration'])
            if not assessment['accepted']:
                raise ValueError('; '.join(assessment['reasons']))
            item['selection'] = assessment['selection']
            item['decision_provenance'] = {'source': 'current_codex_chat', 'verified_remote_model': None,
                'user_authorized_chat_decisions': True, 'timing': 'observed_local_source_words',
                'profile_hash': profile_fingerprint(profile), 'source_sha256': observed['source_sha256']}
            accepted.append(item)
            print(f"ACCEPTED {d['id']} {start:.3f} {end:.3f} {end-start:.3f} {d['title']}")
        except (ValueError, IndexError) as exc:
            rejected.append({'decision_id': d['id'], 'title': d['title'], 'reason': str(exc)})
            print(f"REJECTED {d['id']} {exc}")
    atomic_json(directory / 'reviewed-highlight-plan.json', {'highlights': accepted, 'rejected': rejected,
        'source_transcript': str(srt_path), 'source_words': str(words_path),
        'authorization': 'Render every passing candidate; direct chat decisions authorized after API HTTP 530.'})
    print(json.dumps({'accepted': len(accepted), 'rejected': len(rejected)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
