"""Check complete delivered media, original-voice onset and visual proof frames."""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from services.editing import file_sha256,probe_media
from services.storage import atomic_json,utc_now
from utils.helpers import get_ffmpeg_path
OUT=ROOT/'output/ironman-batch-20261014'


def pcm(path,seconds):
    r=subprocess.run([get_ffmpeg_path(),'-v','error','-i',str(path),'-vn','-t',str(seconds),
        '-ar','16000','-ac','1','-f','f32le','pipe:1'],capture_output=True,check=True)
    return np.frombuffer(r.stdout,dtype='<f4')


def check(index):
    recipe=json.loads((OUT/'recipes'/f'clip-{index:03}.json').read_text(encoding='utf-8'))
    path=OUT/'clips'/f'clip-{index:03}'/'master.mp4'
    media=probe_media(path,get_ffmpeg_path());duration=sum(s['duration'] for s in recipe['scenes'])
    assert (media['width'],media['height'])==(1080,1920)
    assert media['has_audio'] and abs(media['duration']-duration)<.08
    result=subprocess.run([get_ffmpeg_path(),'-hide_banner','-i',str(path),
        '-af','silencedetect=n=-50dB:d=0.3,ebur128=peak=true',
        '-vf','blackdetect=d=0.15:pix_th=0.02','-f','null','-'],capture_output=True)
    log=result.stderr.decode(errors='replace');(path.parent/'qa-decode.log').write_text(log,encoding='utf-8')
    assert result.returncode==0,'Complete decode failed'
    assert 'silence_start' not in log,'Unexpected silent interval'
    assert 'black_start' not in log,'Unexpected black frame interval'
    voice_test=None
    if recipe.get('narration'):
        master,voice=pcm(path,1.3),pcm(recipe['narration']['path'],1.3)
        # A music-only opening cannot satisfy correlation with the source voice.
        base=voice[1600:14400];base=base-base.mean();scores=[]
        for offset in range(-800,801,16):
            candidate=master[1600+offset:14400+offset];candidate=candidate-candidate.mean()
            corr=float(np.dot(base,candidate)/(np.linalg.norm(base)*np.linalg.norm(candidate)+1e-10))
            scores.append((corr,offset/16000))
        correlation,offset=max(scores)
        assert correlation>.70 and abs(offset)<=.05,'Voice onset differs from the source'
        voice_test={'correlation':correlation,'offset_seconds':offset,'window_seconds':[.1,.9]}
    times={.2,1,4.8,5.2,max(.1,duration-.1)}
    at=0
    for scene in recipe['scenes']:
        times.update([at+min(.15,scene['duration']/3),at+scene['duration']/2,at+scene['duration']-.15])
        at+=scene['duration']
    for event in recipe.get('transitions',[]):
        times.update(event['at']+delta for delta in [-.2,0,.2])
    times=sorted(t for t in times if 0<=t<duration)
    cv2.setNumThreads(2);capture=cv2.VideoCapture(str(path))
    sheet=Image.new('RGB',(1080,410*((len(times)+4)//5)),'#181818');draw=ImageDraw.Draw(sheet)
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',17)
    for i,t in enumerate(times):
        capture.set(cv2.CAP_PROP_POS_MSEC,t*1000);ok,frame=capture.read();assert ok,f'Missing frame at {t}'
        picture=Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB));picture.thumbnail((216,384))
        x=i%5*216;y=i//5*410;sheet.paste(picture,(x,y+24));draw.text((x+4,y+3),f'{t:.2f}s',font=font,fill='white')
        if abs(t-1)<.001:picture.save(path.parent/'thumbnail.jpg',quality=92)
    capture.release();sheet.save(OUT/'review'/f'qa-clip-{index:03}.jpg',quality=92)
    integrated=re.findall(r'I:\s+(-?[\d.]+) LUFS',log);peaks=re.findall(r'Peak:\s+(-?[\d.]+) dBFS',log)
    data={'path':str(path.resolve()),'sha256':file_sha256(path),'duration_seconds':media['duration'],
        'complete_decode':True,'silence_intervals':[],'black_intervals':[],
        'original_voice_onset':voice_test,'integrated_lufs':float(integrated[-1]) if integrated else None,
        'true_peak_dbfs':float(peaks[-1]) if peaks else None,
        'visual_review_passed':False,'observed_at':utc_now()}
    atomic_json(path.parent/'qa-result.json',data)
    print(json.dumps({'index':index,**data},ensure_ascii=True),flush=True)
    return data


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--indices');parser.add_argument('--batch-dir',type=Path,default=OUT);args=parser.parse_args()
    OUT=args.batch_dir.resolve()
    indices=[int(x) for x in args.indices.split(',')] if args.indices else [r['index'] for r in json.loads((OUT/'batch.json').read_text(encoding='utf-8'))['clips']]
    for index in indices:check(index)
