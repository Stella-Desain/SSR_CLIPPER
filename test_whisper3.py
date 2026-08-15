import sys
import json
import traceback
sys.path.append('.')
from clipper_core import AutoClipperCore
from openai import OpenAI

with open('config.json', 'r') as f:
    config = json.load(f)

# Mock OpenAI client
dummy_client = OpenAI(api_key='dummy')
core = AutoClipperCore(
    client=dummy_client,
    ai_providers=config.get('ai_providers', {}),
    local_whisper_settings=config.get('local_whisper', {}),
    log_callback=lambda x: print(str(x).encode('ascii', 'replace').decode('ascii'))
)
try:
    print('Testing whisper...')
    audio_path = 'output/5 Kebohongan Tentang Hidup Yang Membuat Orang Indonesia Tetap Miskin-3/20260814-174210-01/master.mp4'
    res = core._whisper_transcribe_words(audio_path)
    print(f'Success, words: {len(res)}')
except Exception as e:
    traceback.print_exc()
