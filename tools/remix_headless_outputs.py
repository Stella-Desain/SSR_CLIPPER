"""Lower music on a completed headless batch without re-encoding its picture."""
import argparse
import copy
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.editing import analyze_audio, bounded_ffmpeg_command, file_sha256, mix_music
from services.music_review import verify_music_balance
from services.storage import WorkflowStore, atomic_json, digest, utc_now
from services.workflow import WorkflowMixin
from utils.helpers import get_ffmpeg_path


def music_volume(value):
    value = float(value)
    if not math.isfinite(value) or not 0 < value <= 2:
        raise argparse.ArgumentTypeError("Music volume must be finite and between 0 and 2.")
    return value


def commit_pending_revisions(store, parents, clips, job_id, settings):
    with store.connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        for clip in clips:
            row = connection.execute("SELECT data FROM entities WHERE kind='clip' AND id=?", (clip['id'],)).fetchone()
            current = json.loads(row['data']) if row else {}
            parent = parents[clip['id']]
            if current.get('revision_id') != parent['revision_id'] or current.get('file_hash') != parent['file_hash']:
                raise ValueError("Clip changed during remix; existing revisions were not replaced.")
            if current.get('review_status') != 'pending':
                raise ValueError("Only pending clips can be replaced by this headless remix.")
            if connection.execute("SELECT 1 FROM publications WHERE clip_id=?", (clip['id'],)).fetchone():
                raise ValueError("Clip has a publication record; retain the existing revision.")
        for clip in clips:
            store._put(connection, 'clip', clip['id'], clip)
            store._put(connection, 'clip_revision', clip['revision_id'], clip)
        row = connection.execute("SELECT data FROM entities WHERE kind='job' AND id=?", (job_id,)).fetchone()
        if row:
            job = json.loads(row['data'])
            job.setdefault('execution', {})['music_remix'] = settings
            store._put(connection, 'job', job_id, job)


def video_hash(path, ffmpeg):
    result = subprocess.run(bounded_ffmpeg_command([str(ffmpeg), '-v', 'error', '-i', str(path),
        '-map', '0:v:0', '-c:v', 'copy', '-f', 'hash', '-hash', 'sha256', '-']),
        capture_output=True, check=True, timeout=180,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    return result.stdout.decode('ascii').strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--volume', type=music_volume, default=.2)
    parser.add_argument('--min-music-db', type=float, default=-18)
    parser.add_argument('--max-music-db', type=float, default=-8)
    args = parser.parse_args()
    directory = args.directory.resolve()
    run = json.loads((directory / 'run.json').read_text(encoding='utf-8'))
    original = ROOT / 'output' / ('job-' + run['job_id'].removeprefix('job_')[:16])
    target = original.with_name(original.name + f'-music{round(args.volume * 100):03d}')
    destination = WorkflowStore(ROOT / 'workflow.sqlite3')
    entries, parents = [], {}
    for source_dir in sorted(original.glob('clip-*')):
        metadata = json.loads((source_dir / 'data.json').read_text(encoding='utf-8'))
        parent = destination.get('clip', metadata['clip_id'])
        if not parent or parent['revision_id'] != metadata['revision_id'] or parent['review_status'] != 'pending':
            raise ValueError("Original clip is no longer the pending revision. Refusing to replace it.")
        for path, expected in ((source_dir / 'master.mp4', metadata['final_sha256']),
                               (metadata['dry_master']['path'], metadata['dry_master']['sha256']),
                               (metadata['music']['path'], metadata['music']['sha256'])):
            if file_sha256(path) != expected:
                raise ValueError("A source file changed; remix stopped before modifying the batch.")
        entries.append((source_dir, metadata))
        parents[parent['id']] = parent
    if not entries:
        raise ValueError("No completed clips found.")
    if target.exists():
        previous = json.loads((target / 'remix.json').read_text(encoding='utf-8'))
        if previous.get('parent_directory') != str(original) or previous.get('volume') != args.volume:
            raise ValueError("The remix directory belongs to another batch or volume.")
    target.mkdir(parents=True, exist_ok=True)
    staging = WorkflowStore(target / 'workflow.sqlite3')
    registry = SimpleNamespace(_get_store=lambda: staging)
    ffmpeg = get_ffmpeg_path()
    settings = {'volume': args.volume, 'source_gain': 1, 'picture_reencoded': False,
                'reason': 'User reported music too loud.', 'parent_directory': str(original),
                'output_directory': str(target), 'created_at': utc_now()}
    atomic_json(target / 'remix.json', {'status': 'running', **settings})
    staged, measurements = [], []
    for index, (source_dir, metadata) in enumerate(entries, 1):
        clip_dir = target / source_dir.name
        clip_dir.mkdir(exist_ok=True)
        final = clip_dir / 'master.mp4'
        dry = Path(metadata['dry_master']['path'])
        music = {**metadata['music'], 'volume': args.volume}
        mixed = mix_music(dry, music, final, ffmpeg)
        fingerprint = video_hash(final, ffmpeg)
        if fingerprint != video_hash(source_dir / 'master.mp4', ffmpeg):
            raise ValueError("Remix changed video packets; the original batch remains active.")
        balance = verify_music_balance(dry, final, mixed, ffmpeg)
        updated = copy.deepcopy(metadata)
        updated.update(final_path=str(final), final_sha256=file_sha256(final), music=mixed,
                       audio_analysis=analyze_audio(final, ffmpeg), music_balance=balance,
                       music_revision={'parent_clip_id': metadata['clip_id'],
                           'parent_revision_id': metadata['revision_id'], 'settings': settings,
                           'previous_volume': metadata['music']['volume'], 'video_packet_hash': fingerprint})
        updated['clip_plan']['music']['volume'] = args.volume
        updated['render_key'] = digest({'parent': metadata['render_key'], 'music_remix': args.volume,
                                        'dry_sha256': metadata['dry_master']['sha256']})
        previous_warnings = set(metadata.get('music_balance', {}).get('warnings', []))
        updated['warnings'] = [w for w in metadata.get('warnings', []) if w not in previous_warnings]
        updated['warnings'].extend(balance['warnings'])
        atomic_json(clip_dir / 'data.json', updated)
        verification = subprocess.run([sys.executable, str(ROOT / 'tools/verify_music_render.py'), str(clip_dir),
            '--min-music-db', str(args.min_music_db), '--max-music-db', str(args.max_music_db)],
            capture_output=True, text=True, timeout=600,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if verification.returncode:
            raise ValueError(f"Audio verification failed for {source_dir.name}: {verification.stderr[-1000:]}")
        report = json.loads((clip_dir / 'verification.json').read_text(encoding='utf-8'))
        measurements.append(report['audio_signal']['estimated_music_to_voice_db'])
        registered = WorkflowMixin._register_clip(registry, final, updated)
        atomic_json(clip_dir / 'data.json', registered)
        staged.append(registered)
        print(f"REMIXED {index}/{len(entries)} music={measurements[-1]:.2f} dB; picture unchanged", flush=True)
    shutil.copyfile(original / 'highlights.json', target / 'highlights.json')
    for parent in parents.values():
        if file_sha256(parent['path']) != parent['file_hash']:
            raise ValueError("Original file changed during remix; existing stock was not replaced.")
    commit_pending_revisions(destination, parents, staged, run['job_id'], settings)
    isolated = WorkflowStore(directory / 'workflow.sqlite3')
    commit_pending_revisions(isolated, parents, staged, run['job_id'], settings)
    summary = {'status': 'completed', **settings, 'clips': len(staged), 'all_audio_passed': True,
               'originals_preserved': True, 'music_to_voice_db_range': [min(measurements), max(measurements)],
               'review_status': 'pending', 'published': False}
    atomic_json(target / 'remix.json', summary)
    atomic_json(directory / 'music-remix.json', summary)
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
