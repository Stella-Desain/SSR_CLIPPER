"""Prepare verified local campaign artwork, timestamps and licensed music."""
import json
import sys
from pathlib import Path
import requests
from PIL import Image, ImageDraw
from faster_whisper import WhisperModel

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'output/bevan-production-20261009'
assets = OUT/'assets'

# Isolate the official frog + wordmark. Other brands in the source stay excluded.
original = Image.open(assets/'gmgn-official-screen.png').convert('RGBA')
mark = original.crop((688, 54, 903, 117))
pixels = mark.load()
for y in range(mark.height):
    for x in range(mark.width):
        r,g,b,a = pixels[x,y]
        if max(r,g,b) < 95:
            pixels[x,y] = (0,0,0,0)
        elif max(r,g,b)-min(r,g,b) < 12:
            pixels[x,y] = (0,0,0, round(255*(max(r,g,b)-40)/215))
mark = mark.resize((650,190), Image.Resampling.NEAREST)
plate = Image.new('RGBA',(710,220))
ImageDraw.Draw(plate).rounded_rectangle((0,0,709,219),radius=35,fill='white')
plate.alpha_composite(mark,(30,15))
plate.save(assets/'gmgn-cta-plate.png')
if '--logo-only' in sys.argv:
    sys.exit(0)

# VAD skipped the fast opening sentence of the clean CTA: rerun its first 6 s.
model_root = Path.home()/'.cache/huggingface/hub/models--mobiuslabsgmbh--faster-whisper-large-v3-turbo/snapshots'
model_path = next(p for p in model_root.iterdir() if (p/'model.bin').is_file())
model = WhisperModel(str(model_path),device='cpu',compute_type='int8',cpu_threads=6)
segments,_ = model.transcribe(str(assets/'CTA_GMGN_Apps.mp4'),language='id',word_timestamps=True,
    vad_filter=False,beam_size=5,clip_timestamps='0,6',
    initial_prompt='Oke jadi gue biasa trading meme pakai GMGN karena yang pertama tools mereka sangat advance.')
first = [{'word':w.word,'start':w.start,'end':w.end,'probability':w.probability}
         for s in segments for w in s.words or [] if w.start < 3.12 and w.end>w.start]
print('CTA_OPENING', first,flush=True)
path = assets/'CTA_GMGN_Apps.words.json'
payload = json.loads(path.read_text(encoding='utf-8'))
payload['words'] = first + [w for w in payload['words'] if w['start']>=3.12]
payload['opening_repair'] = {'method':'same_source_whisper_no_vad_first_6_seconds','words':first}
path.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
