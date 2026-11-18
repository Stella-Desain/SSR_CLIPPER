"""Download an unchanged source and observe word times without a desktop window."""
from __future__ import annotations
import argparse
import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, 'reconfigure'):
        stream.reconfigure(encoding='utf-8', errors='replace')

from clipper_core import AutoClipperCore
from services.editing import file_sha256, fingerprint_source
from services.storage import atomic_json
from services.speech_boundaries import timestamp
from utils.helpers import get_ffmpeg_path, get_ytdlp_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source')
    parser.add_argument('--directory', required=True)
    parser.add_argument('--word-times', action='store_true')
    args = parser.parse_args()
    directory = Path(args.directory).resolve()
    source_dir = directory / 'source'
    source_dir.mkdir(parents=True, exist_ok=True)
    cfg = json.loads((ROOT / 'config.json').read_text(encoding='utf-8'))
    identity = fingerprint_source(args.source)
    source = source_dir / 'source.mp4'
    analysis_path = source_dir / 'analysis.json'
    log_path = directory / 'prepare.log'

    def log(message):
        print(message, flush=True)
        with log_path.open('a', encoding='utf-8') as handle:
            handle.write(str(message) + '\n')

    if not source.is_file():
        import yt_dlp
        original_downloader = yt_dlp.YoutubeDL
        def downloader(options, *values, **kwargs):
            return original_downloader({**options, 'concurrent_fragment_downloads': 4, 'noprogress': True}, *values, **kwargs)
        yt_dlp.YoutubeDL = downloader
        core = AutoClipperCore(client=None, ai_providers=cfg['ai_providers'],
            ffmpeg_path=get_ffmpeg_path(), ytdlp_path=get_ytdlp_path(),
            output_dir=str(source_dir), subtitle_language='id',
            local_whisper_settings={'enabled': True}, log_callback=log)
        previous = list((source_dir / '_temp').glob('job-*/source.id.srt'))
        if previous:
            # Continue the exact partial download left by an interrupted command.
            core.temp_dir = previous[0].parent
        try:
            try:
                downloaded, srt, info = core.download_video(args.source)
            except Exception as exc:
                if not getattr(exc, 'video_path', None):
                    raise
                downloaded, srt, info = exc.video_path, None, getattr(exc, 'video_info', {})
            shutil.copy2(downloaded, source)
            if srt and Path(srt).is_file():
                shutil.copy2(srt, source_dir / 'youtube-source.srt')
            atomic_json(analysis_path, {'source_id': identity['source_id'], 'video_path': str(source), 'video_info': info})
        finally:
            core.cleanup()
    if args.word_times and not (source_dir / 'word-transcript.json').is_file():
        from faster_whisper import WhisperModel
        models = list((Path.home() / '.cache/huggingface/hub/models--mobiuslabsgmbh--faster-whisper-large-v3-turbo/snapshots').glob('*/model.bin'))
        if not models:
            raise FileNotFoundError('Model transkripsi sumber lokal tidak tersedia.')
        partial = source_dir / 'word-transcript.partial.json'
        rows = json.loads(partial.read_text(encoding='utf-8')) if partial.is_file() else []
        resume = max(0, rows[-1]['end'] - 2) if rows else 0
        rows = [row for row in rows if row['end'] <= resume]
        log(f'WORD_TIMES_START resume={resume:.2f}')
        model = WhisperModel(str(models[-1].parent), device='cpu', compute_type='int8', cpu_threads=4)
        segments, info = model.transcribe(str(source), language='id', beam_size=5,
            word_timestamps=True, vad_filter=False, clip_timestamps=str(resume), condition_on_previous_text=False)
        started = time.monotonic()
        for segment in segments:
            rows.append({'start': segment.start, 'end': segment.end, 'text': segment.text,
                'words': [{'start': w.start, 'end': w.end, 'word': w.word, 'probability': w.probability} for w in segment.words or []]})
            atomic_json(partial, rows)
            log(f'WORD_TIMES {segment.end:.2f}/{info.duration:.2f} elapsed={time.monotonic()-started:.1f}s')
        atomic_json(source_dir / 'word-transcript.json', {'model': 'faster-whisper-large-v3-turbo',
            'language': info.language, 'source_duration': info.duration, 'kind': 'observed_local_asr_word_times',
            'segments': rows, 'source_video': str(source), 'source_sha256': file_sha256(source)})
    words_path = source_dir / 'word-transcript.json'
    if words_path.is_file():
        words = json.loads(words_path.read_text(encoding='utf-8'))
        srt = '\n\n'.join(f"{i}\n{timestamp(s['start'])} --> {timestamp(s['end'])}\n{s['text'].strip()}" for i, s in enumerate(words['segments'], 1)) + '\n'
        (source_dir / 'source.srt').write_text(srt, encoding='utf-8')
    log('SOURCE_PREPARATION_COMPLETE')


if __name__ == '__main__':
    main()
