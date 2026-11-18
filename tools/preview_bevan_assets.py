"""Contact sheet of public thumbnails to select official campaign B-roll."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request, urlopen
import io
import json
import argparse
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/bevan-production-20261009'
parser = argparse.ArgumentParser()
parser.add_argument('--root', action='store_true')
args = parser.parse_args()
catalog = json.loads((OUT / ('root-assets-catalog.json' if args.root else 'assets-catalog.json')).read_text(encoding='utf-8'))
selected = sorted(catalog, key=lambda row: row['size'])[:56 if args.root else 28]
def get(row):
    try:
        request = Request('https://drive.google.com/thumbnail?id=' + row['id'] + '&sz=w300', headers={'User-Agent': 'Mozilla/5.0'})
        with urlopen(request, timeout=25) as handle:
            thumbnail = Image.open(io.BytesIO(handle.read())).convert('RGB')
        thumbnail.thumbnail((200, 250))
        return row, thumbnail, None
    except Exception as exc:
        return row, None, str(exc)
sheet = Image.new('RGB', (7 * 200, ((len(selected)+6)//7) * 285), '#161616')
draw = ImageDraw.Draw(sheet)
for index, (row, thumbnail, error) in enumerate(ThreadPoolExecutor(max_workers=7).map(get, selected)):
    x, y = (index % 7) * 200, (index // 7) * 285
    if thumbnail:
        sheet.paste(thumbnail, (x + (200-thumbnail.width)//2, y))
    draw.text((x+4, y+252), f"{index+1}. {row['name'][:25]}", fill='white')
    draw.text((x+4, y+266), row['id'][:14], fill='white')
    if error:
        draw.text((x+4, y+80), error[:25], fill='red')
prefix = 'root-' if args.root else ''
sheet.save(OUT / (prefix+'official-broll-thumbnails.jpg'), quality=94)
(OUT / (prefix+'thumbnail-selection.json')).write_text(json.dumps(selected, indent=2), encoding='utf-8')
print('THUMBNAIL_SHEET_READY', OUT / 'official-broll-thumbnails.jpg')
