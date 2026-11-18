"""Prepare source excerpts for a chat review; never approve candidates."""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.storage import atomic_json
from services.highlight_profiles import SCORE_WEIGHTS
from services.speech_boundaries import seconds


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', required=True)
    args = parser.parse_args()
    directory = Path(args.directory).resolve()
    observed_path = directory / 'source/word-transcript.json'
    complete = observed_path.is_file()
    observed = json.loads((observed_path if complete else directory / 'source/word-transcript.partial.json').read_text(encoding='utf-8'))
    segments = observed['segments'] if complete else observed
    words = [w for s in segments for w in s.get('words', []) if w['end'] > w['start']]
    terminal = re.compile(r'[.!?][\s\"\'”’]*$')
    starts = sorted(set([w['start'] for i, w in enumerate(words) if i == 0 or terminal.search(words[i-1]['word'])]
                        + [s['words'][0]['start'] for s in segments if s.get('words')]))
    ends = sorted(set([w['end'] for w in words if terminal.search(w['word'])]
                      + [s['words'][-1]['end'] for s in segments if s.get('words')]))
    rows, review = [], []
    draft = (directory / 'candidate-draft.tsv').read_text(encoding='utf-8').splitlines()
    for identifier, line in enumerate(draft, 1):
        a, b, title, description, scores, music = line.split('|')
        a, b = seconds('00:' + a), seconds('00:' + b)
        if not complete and b + 8 > words[-1]['end']:
            continue
        possible_starts = [t for t in starts if abs(t-a) <= 6]
        possible_ends = [t for t in ends if abs(t-b) <= 6]
        if not possible_starts or not possible_ends:
            review.append(f'ID {identifier} NEEDS_MANUAL_BOUNDARIES {title} {a:.3f}->{b:.3f}')
            continue
        start = min(possible_starts, key=lambda t: abs(t-a))
        end = min(possible_ends, key=lambda t: abs(t-b))
        row = {'id': identifier, 'title': title, 'description': description, 'start': start, 'end': end,
            'scores': dict(zip(SCORE_WEIGHTS, map(int, scores.split(',')))),
            'reason': description, 'music_id': music, 'reviewed': False, 'gates': {}}
        rows.append(row)
        opening = [w for w in words if start-5 <= w['start'] <= start+8]
        ending = [w for w in words if end-9 <= w['start'] <= end+6]
        review.append(f"ID {identifier} {title}\nPROPOSED {start:.3f}->{end:.3f} ({end-start:.3f}s)\n"
            + 'OPEN: ' + ' '.join(f"[{w['start']:.2f}:{w['end']:.2f}]{w['word'].strip()}" for w in opening)
            + '\nEND: ' + ' '.join(f"[{w['start']:.2f}:{w['end']:.2f}]{w['word'].strip()}" for w in ending))
    atomic_json(directory / 'draft-aligned.json', rows)
    (directory / 'draft-aligned-review.txt').write_text('\n\n'.join(review) + '\n', encoding='utf-8')
    print(json.dumps({'reviewable': len(rows), 'source_seconds_observed': words[-1]['end'], 'complete': complete}))


if __name__ == '__main__':
    main()
