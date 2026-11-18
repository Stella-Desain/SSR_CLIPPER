"""Decode the complete renders and collect visual/audio checks before publishing."""
import json
import pathlib
import re
import subprocess
import sys
import concurrent.futures

import cv2
from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.editing import file_sha256, probe_media
from services.storage import atomic_json
from utils.helpers import get_ffmpeg_path

OUT = ROOT / 'output/ironman-tests-20261013'


def check(index):
    file = OUT / 'clips' / f'clip-{index:03}' / 'master.mp4'
    recipe = json.loads((OUT / 'recipes' / f'ironman-test-{index:02}.json').read_text(encoding='utf-8'))
    media = probe_media(file, get_ffmpeg_path())
    expected = sum(s['duration'] for s in recipe['scenes'])
    assert media['width'] == 1080 and media['height'] == 1920
    assert media['has_audio'] and abs(media['duration'] - expected) < .08
    result = subprocess.run([get_ffmpeg_path(), '-hide_banner', '-i', str(file),
        '-af', 'silencedetect=n=-50dB:d=0.3,ebur128=peak=true',
        '-vf', 'blackdetect=d=0.15:pix_th=0.02', '-f', 'null', '-'], capture_output=True)
    log = result.stderr.decode(errors='replace')
    assert result.returncode == 0, 'Full decode failed'
    assert 'silence_start' not in log, 'Unexpected silent audio interval'
    assert 'black_start' not in log, 'Unexpected black frame interval'
    (file.parent / 'qa-decode.log').write_text(log, encoding='utf-8')
    times = sorted(set([1, 4.8, 5.2, expected-1] + [float(t) for t in range(6, int(expected), 2)]
                       + [e['at'] + offset for e in recipe['transitions'] for offset in [-.2, 0, .2]]))
    cv2.setNumThreads(2)
    capture = cv2.VideoCapture(str(file))
    sheet = Image.new('RGB', (1350, 510 * ((len(times)+4)//5)), '#222222')
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 19)
    for n, t in enumerate(times):
        capture.set(cv2.CAP_PROP_POS_MSEC, t*1000)
        ok, frame = capture.read()
        assert ok, f'Cannot seek to {t}'
        pic = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        pic.thumbnail((270,480))
        x,y=n%5*270,n//5*510
        sheet.paste(pic,(x,y+28))
        draw.text((x+3,y+3),f'{t:.2f}s',font=font,fill='white')
    capture.release()
    sheet.save(OUT / f'qa-clip-{index:03}.jpg')
    loudness = re.findall(r'I:\s+(-?[\d.]+) LUFS', log)
    peaks = re.findall(r'Peak:\s+(-?[\d.]+) dBFS', log)
    return {'path': str(file.resolve()), 'sha256': file_sha256(file), 'duration_seconds': media['duration'],
            'complete_decode': True, 'audio_present_from_start': True, 'black_intervals': [],
            'silence_intervals': [], 'integrated_lufs': float(loudness[-1]) if loudness else None,
            'true_peak_dbfs': float(peaks[-1]) if peaks else None,
            'hook_seconds': recipe['hook']['duration'], 'transitions': recipe['transitions']}


if __name__ == '__main__':
    with concurrent.futures.ThreadPoolExecutor(2) as pool:
        results = list(pool.map(check, [1,2,3]))
    atomic_json(OUT / 'qa-result.json', {'passed': True, 'visual_review_passed': False, 'clips': results})
    print(json.dumps(results, ensure_ascii=True), flush=True)
