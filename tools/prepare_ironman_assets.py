"""Download only connector-resolved official assets and create review sheets."""
import concurrent.futures
import hashlib
import json
from pathlib import Path

import cv2
import requests
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/ironman-tests-20261013'
ASSETS = OUT / 'assets'
ASSETS.mkdir(parents=True, exist_ok=True)


def acquire(job):
    meta = job['meta']
    target = ASSETS / (meta['id'] + Path(meta['title']).suffix)
    expected = int(meta['size'])
    if not target.exists() or target.stat().st_size != expected:
        response = requests.get(job['fetch']['file_uri']['download_url'], stream=True, timeout=(20, 120))
        response.raise_for_status()
        temp = target.with_suffix('.part')
        with temp.open('wb') as stream:
            for chunk in response.iter_content(1024 * 1024):
                stream.write(chunk)
        if temp.stat().st_size != expected:
            raise ValueError('Size mismatch for ' + meta['title'])
        temp.replace(target)
    capture = cv2.VideoCapture(str(target))
    fps = capture.get(cv2.CAP_PROP_FPS)
    count = capture.get(cv2.CAP_PROP_FRAME_COUNT)
    duration = count / fps
    frames = []
    for fraction in [.1, .5, .85]:
        timestamp = duration * fraction
        capture.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
        success, frame = capture.read()
        if success:
            pic = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            pic.thumbnail((250, 360))
            dest = ASSETS / (meta['id'] + f'-{fraction}.jpg')
            pic.save(dest)
            frames.append({'seconds': round(timestamp, 3), 'path': str(dest)})
    result = {**meta, 'path': str(target), 'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
              'duration': duration, 'fps': fps, 'width': capture.get(cv2.CAP_PROP_FRAME_WIDTH),
              'height': capture.get(cv2.CAP_PROP_FRAME_HEIGHT), 'frames': frames,
              'official_source': True, 'visual_review': 'pending'}
    capture.release()
    print('Ready:', meta['title'], round(duration, 2), flush=True)
    return result


def main():
    private = OUT / 'download-jobs.private.json'
    jobs = json.loads(private.read_text(encoding='utf-8'))
    with concurrent.futures.ThreadPoolExecutor(4) as pool:
        assets = list(pool.map(acquire, jobs))
    index = OUT / 'assets-index.json'
    previous = json.loads(index.read_text(encoding='utf-8')) if index.exists() else []
    combined = {a['id']: a for a in previous}
    combined.update({a['id']: a for a in assets})
    assets = list(combined.values())
    index.write_text(json.dumps(assets, indent=2), encoding='utf-8')
    private.unlink()
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 17)
    for offset in range(0, len(assets), 7):
        batch = assets[offset:offset + 7]
        sheet = Image.new('RGB', (780, 420 * len(batch)), '#202020')
        draw = ImageDraw.Draw(sheet)
        for row, asset in enumerate(batch):
            draw.text((10, row * 420 + 6), asset['title'] + ' | ' + asset['id'], font=font, fill='white')
            for col, frame in enumerate(asset['frames']):
                pic = Image.open(frame['path'])
                sheet.paste(pic, (col * 260 + (260 - pic.width) // 2, row * 420 + 34))
                draw.text((col * 260 + 5, row * 420 + 398), str(frame['seconds']) + 's', font=font, fill='white')
        sheet.save(OUT / f'asset-review-{offset // 7 + 1}.jpg')


if __name__ == '__main__':
    main()
