"""Local word-timestamp transcription for campaign production evidence."""
import argparse
import hashlib
import json
from pathlib import Path
from faster_whisper import WhisperModel

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('sources', nargs='+')
parser.add_argument('--output', required=True)
args = parser.parse_args()
output = Path(args.output)
output.mkdir(parents=True, exist_ok=True)
model_root = Path.home() / '.cache/huggingface/hub/models--mobiuslabsgmbh--faster-whisper-large-v3-turbo/snapshots'
model_path = next(p for p in model_root.iterdir() if (p / 'model.bin').is_file())
model = WhisperModel(str(model_path), device='cpu', compute_type='int8', cpu_threads=6)
for index, value in enumerate(args.sources, 1):
    source = Path(value).resolve()
    destination = output / (source.stem + '.words.json')
    if destination.is_file():
        print('CACHED', destination, flush=True)
        continue
    print('TRANSCRIBING', source.name, flush=True)
    segments, info = model.transcribe(str(source), language='id', word_timestamps=True,
        vad_filter=True, beam_size=5,
        initial_prompt='Bevan Pramudito, GMGN, crypto, memecoin, trading, narrative, wallet, financial freedom.')
    rows = []
    for segment in segments:
        rows.append({'start': segment.start, 'end': segment.end, 'text': segment.text,
            'words': [{'word': w.word, 'start': w.start, 'end': w.end, 'probability': w.probability}
                      for w in segment.words or []]})
        print(f'{segment.start:.2f}-{segment.end:.2f}: {segment.text}', flush=True)
    h = hashlib.sha256()
    with source.open('rb') as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b''):
            h.update(chunk)
    payload = {'source': str(source), 'source_sha256': h.hexdigest(), 'model': 'faster-whisper-large-v3-turbo-local-int8',
        'language': info.language, 'duration': info.duration, 'segments': rows,
        'words': [w for s in rows for w in s['words']]}
    destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print('SAVED', destination, flush=True)
