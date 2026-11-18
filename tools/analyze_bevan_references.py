"""Extract review frames from the two user-supplied reference films."""
from pathlib import Path
import json
import subprocess
import cv2
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output' / 'bevan-reference-20261009'
OUT.mkdir(parents=True, exist_ok=True)
FILES = [Path('E:/Downloads/Ruang_Berpikir_video_no_watermark.mp4'),
         Path('E:/Downloads/Ruang_Berpikir_video_no_watermark (1).mp4')]
report = []
for number, source in enumerate(FILES, 1):
    metadata = json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(source)]))
    duration = float(metadata['format']['duration'])
    cap = cv2.VideoCapture(str(source))
    times = list(range(0, int(duration), 3)) + [max(0, duration - 0.5)]
    sheet = Image.new('RGB', (6 * 192, ((len(times) + 5) // 6) * 365), '#161616')
    draw = ImageDraw.Draw(sheet)
    for i, seconds in enumerate(times):
        cap.set(cv2.CAP_PROP_POS_MSEC, seconds * 1000)
        ok, frame = cap.read()
        if not ok:
            continue
        frame_image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        frame_image.save(OUT / f'ref-{number}-{seconds:06.2f}.jpg', quality=94)
        frame_image.thumbnail((192, 341))
        x, y = (i % 6) * 192, (i // 6) * 365
        sheet.paste(frame_image, (x, y))
        draw.text((x + 5, y + 342), f'{seconds:.2f}s', fill='white')
    cap.release()
    sheet.save(OUT / f'reference-{number}-contact-sheet.jpg', quality=94)
    report.append({'file': str(source), 'metadata': metadata, 'sample_times': times})
(OUT / 'media-probe.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(str(OUT))
