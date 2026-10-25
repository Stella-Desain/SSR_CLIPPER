import sys
import json
import traceback
sys.path.append('.')
from clipper_core import AutoClipperCore

with open('config.json', 'r') as f:
    config = json.load(f)

core = AutoClipperCore(config)
try:
    print('Extracting audio...')
    audio_path = 'output/5 Kebohongan Tentang Hidup Yang Membuat Orang Indonesia Tetap Miskin-3/20260814-174210-01/master.mp4'
    res = core._whisper_transcribe_words(audio_path)
    print(f'Success, words: {len(res)}')
except Exception as e:
    traceback.print_exc()
