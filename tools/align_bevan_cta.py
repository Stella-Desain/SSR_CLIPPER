"""Repair CTA opening words using the same audio in the supplied reference."""
import json, subprocess, sys
from pathlib import Path
import numpy as np
from scipy.signal import correlate
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from utils.helpers import get_ffmpeg_path
from services.editing import file_sha256
OUT=ROOT/'output/bevan-production-20261009'
reference=Path('E:/Downloads/Ruang_Berpikir_video_no_watermark (1).mp4')
cta=OUT/'assets/CTA_GMGN_Apps.mp4'
def samples(path):
    raw=subprocess.run([get_ffmpeg_path(),'-v','error','-i',str(path),'-vn','-ac','1','-ar','4000','-f','f32le','pipe:1'],check=True,capture_output=True).stdout
    return np.frombuffer(raw,dtype=np.float32)
a,b=samples(reference),samples(cta)
# Use the body of the shared CTA, away from its transition and opening.
sample=b[16000:72000]
score=correlate(a,sample,mode='valid',method='fft')
index=int(np.argmax(score))
lag=index/4000-4
aligned=a[index:index+len(sample)]
similarity=float(np.corrcoef(aligned,sample)[0,1])
print('CTA_ALIGNMENT',lag,similarity,flush=True)
if similarity < .65 or not 37<lag<40:
    raise ValueError('The reference and official CTA audio are not sufficiently matched.')
ref=json.loads((ROOT/'output/bevan-reference-20261009/Ruang_Berpikir_video_no_watermark (1).words.json').read_text(encoding='utf-8'))
path=OUT/'assets/CTA_GMGN_Apps.words.json'
payload=json.loads(path.read_text(encoding='utf-8'))
prefix=[{**w,'start':max(0,w['start']-lag),'end':min(3.12,w['end']-lag)} for w in ref['words']
        if lag<=w['start']<lag+3.12 and w['end']>w['start']]
payload['words']=prefix+[w for w in payload['words'] if w['start']>=3.12]
payload['opening_repair']={'method':'measured_audio_alignment_to_same_CTA_in_user_reference',
    'reference':str(reference),'reference_sha256':file_sha256(reference),'offset_seconds':lag,
    'correlation':similarity,'words':prefix}
path.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
print('OPENING_WORDS',[w['word'] for w in prefix])
