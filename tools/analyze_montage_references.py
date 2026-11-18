"""Save local reference evidence without importing finished edits as source footage."""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import cv2
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.editing import file_sha256, probe_media
from utils.helpers import get_ffmpeg_path


def analyze(source, label, destination):
    info = probe_media(source, get_ffmpeg_path())
    # Candidate boundaries, to be reviewed rather than presented as ground truth.
    process = subprocess.run([get_ffmpeg_path(), '-hide_banner', '-loglevel', 'info',
        '-i', str(source), '-vf', "select='gt(scene,0.15)',showinfo", '-an', '-f', 'null', '-'],
        capture_output=True, text=True, encoding='utf-8', errors='replace', check=True, timeout=120)
    cuts = [float(value) for value in re.findall(r'pts_time:([\d.]+)', process.stderr)]
    moments = sorted(set([float(t) for t in range(int(info['duration'])+1)]
                         + [max(0, info['duration']-.2)]))
    moments = [t for t in moments if t < info['duration']]
    folder = destination / label
    folder.mkdir(parents=True, exist_ok=True)
    sheet = Image.new('RGB', (6*192, ((len(moments)+5)//6)*365), '#161616')
    draw = ImageDraw.Draw(sheet)
    capture = cv2.VideoCapture(str(source))
    samples = []
    try:
        for index, seconds in enumerate(moments):
            capture.set(cv2.CAP_PROP_POS_MSEC, seconds*1000)
            ok, frame = capture.read()
            if not ok:
                raise RuntimeError(f'Cannot read {label} at {seconds:.3f}s')
            picture = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            path = folder / f'{seconds:06.2f}.jpg'
            picture.save(path, quality=94)
            samples.append({'seconds': seconds, 'frame': str(path.resolve())})
            picture.thumbnail((192, 341))
            x, y = (index%6)*192, (index//6)*365
            sheet.paste(picture, (x, y))
            draw.text((x+6, y+343), f'{label} {seconds:.2f}s', fill='white')
        for number, (start, end) in enumerate(zip([0]+cuts, cuts+[info['duration']]), 1):
            moment = (start+end)/2
            capture.set(cv2.CAP_PROP_POS_MSEC, moment*1000)
            ok, frame = capture.read()
            if ok:
                cv2.imwrite(str(folder / f'shot-{number:02d}-{start:06.2f}-{end:06.2f}.jpg'), frame)
    finally:
        capture.release()
    sheet.save(folder/'contact-sheet.jpg', quality=95)
    return {'id': label, 'path': str(source.resolve()), 'sha256': file_sha256(source),
        'role': 'editing_reference_only', 'metadata': info,
        'candidate_cut_seconds': cuts, 'cut_method': 'ffmpeg_scene_threshold_0.15_not_yet_manually_confirmed',
        'samples': samples}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sources', nargs='+', type=Path)
    parser.add_argument('--output', type=Path, default=ROOT/'output/ironman-reference-20261013')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    report = [analyze(source, chr(65+index), args.output) for index, source in enumerate(args.sources)]
    (args.output/'local-evidence.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    for row in report:
        print(row['id'], row['metadata'], 'candidate_cuts', row['candidate_cut_seconds'], flush=True)
