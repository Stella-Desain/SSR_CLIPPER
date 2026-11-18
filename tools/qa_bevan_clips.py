"""Verify final video, synchronized source speech, CTA isolation and campaign copy."""
import json,sys,subprocess,argparse
from pathlib import Path
import numpy as np
import cv2
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.stdout.reconfigure(encoding='utf-8',errors='replace')
from services.editing import probe_media,file_sha256
from utils.helpers import get_ffmpeg_path
from app import WebAPI
from services.face_tracking import CAMERA_VERSION
api=WebAPI.__new__(WebAPI);api.config_file=str(ROOT/'config.json');api.worker_enabled=False
def audio(path,start,duration):
    raw=subprocess.run([get_ffmpeg_path(),'-v','error','-ss',str(start),'-t',str(duration),'-i',str(path),
        '-vn','-ac','1','-ar','8000','-f','f32le','pipe:1'],capture_output=True,check=True).stdout
    return np.frombuffer(raw,dtype=np.float32)
def similarity(first,second):
    count=min(len(first),len(second));best=-1
    # AAC seek/encoder priming tolerance, bounded to 80 milliseconds.
    for lag in range(-640,641,8):
        x,y=(first[max(0,lag):count],second[:count-max(0,lag)]) if lag>=0 else (first[:count+lag],second[-lag:count])
        if len(x)>100:best=max(best,float(np.corrcoef(x,y)[0,1]))
    return best
reports=[]
parser=argparse.ArgumentParser();parser.add_argument('--clips',nargs='+',type=int,default=[1,2])
parser.add_argument('--output',default='output/bevan-revision-20261009');args=parser.parse_args()
OUT=(ROOT/args.output).resolve()
def leading_silence(samples):
    # Voice onset at 20 ms resolution, allowing normal AAC encoder priming.
    for i in range(0,len(samples),160):
        if np.sqrt(np.mean(samples[i:i+160]**2))>.01:
            return i/8000
    return len(samples)/8000
for index in args.clips:
    folder=OUT/'clips'/f'clip-{index:03d}'
    metadata=json.loads((folder/'data.json').read_text(encoding='utf-8'))
    path=folder/'master.mp4';info=probe_media(path,get_ffmpeg_path())
    template=metadata['template_render'];intro=template['intro_seconds'];cta_at=template['cta_at_seconds']
    assert (info['width'],info['height'])==(1080,1920) and abs(info['fps']-30)<.01
    assert 15<=info['duration']<=180 and info['has_audio']
    assert file_sha256(path)==metadata['final_sha256']
    assert template['cta_duration_seconds']>=22.8
    assert template['cta_text']=='Cek Bio untuk akses GMGN'
    assert all(s['at_seconds']+s['duration_seconds']<=template['story_duration']+.01 for s in template['broll'])
    assert len(template['broll'])<=2
    assert template['story_broll_ratio']<=.12
    assert len({s['sha256'] for s in template['broll']})==len(template['broll'])
    assert all(s['matched_visual_tags'] for s in template['broll'])
    assert metadata['has_captions'] and metadata['music']['mixed'] and not metadata['blockers']
    for platform in ('tiktok','instagram'):
        for term in ('@bevanpramudt','#bevanpramudito','#memecoin','#narrativelabs','#gmgn','#crypto'):
            assert term in metadata['captions'][platform],(platform,term)
    dry=folder/'master_without_music.mp4'
    voice=similarity(audio(dry,intro+2,8),audio(folder/'temp_portrait.mp4',2,8))
    cta_source=Path(metadata['clip_plan']['endcard']['path'])
    cta=similarity(audio(dry,cta_at+4,12),audio(cta_source,4,12))
    cta_opening=similarity(audio(dry,cta_at+.12,2.8),audio(cta_source,.12,2.8))
    final_cta_opening=similarity(audio(path,cta_at+.12,2.8),audio(cta_source,.12,2.8))
    source_onset=leading_silence(audio(cta_source,0,3))
    final_onset=leading_silence(audio(dry,cta_at,3))
    assert voice>.95 and cta>.95 and cta_opening>.95,(voice,cta,cta_opening)
    assert final_cta_opening>.90,final_cta_opening
    assert source_onset<.25 and final_onset<.25,(source_onset,final_onset)
    camera=json.loads((folder/'camera.json').read_text(encoding='utf-8'))
    assert camera['camera_version']==CAMERA_VERSION
    assert camera['max_pan_step_pixels']<=camera['max_pan_pixels_per_second']/camera['render_fps']+.001
    old_folder=ROOT/'output/bevan-production-20261009/clips'/f'clip-{index:03d}'
    old_camera=json.loads((old_folder/'camera.json').read_text(encoding='utf-8'))
    def sampled_pan(c):
        d=c['decisions']
        return sum(abs(b['x']-a['x']) for a,b in zip(d,d[1:])
                   if a['mode']==b['mode']=='speaker' and a['track_id']==b['track_id'] and not b['scene_cut'])
    cap=cv2.VideoCapture(str(path))
    moments=[.5,3,5.8,10.2,12.2,21.5,30.5,cta_at+.3,cta_at+3.5,cta_at+15,info['duration']-.5]
    sheet=Image.new('RGB',(4*270,3*515),'#171717');draw=ImageDraw.Draw(sheet)
    for number,t in enumerate(moments):
        cap.set(cv2.CAP_PROP_POS_MSEC,t*1000);ok,frame=cap.read();assert ok
        im=Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB));im.thumbnail((270,480))
        sheet.paste(im,((number%4)*270,(number//4)*515));draw.text(((number%4)*270+8,(number//4)*515+485),f'{t:.2f}s',fill='white')
    cap.release();sheet.save(OUT/f'clip-{index:03d}-qa.jpg',quality=95)
    metadata['qa_evidence']={'technical':'pass','source_voice_correlation':voice,'official_cta_audio_correlation':cta,
        'cta_opening_audio_correlation':cta_opening,'cta_source_leading_silence_seconds':source_onset,
        'final_mix_cta_opening_audio_correlation':final_cta_opening,
        'cta_render_leading_silence_seconds':final_onset,'broll_policy':'pass',
        'tracking':{'camera_version':camera['camera_version'],'max_pan_step_pixels':camera['max_pan_step_pixels'],
                    'sampled_pan_before':sampled_pan(old_camera),'sampled_pan_after':sampled_pan(camera)},
        'campaign_render_rules':'pass','publication_status':'not_published','bio_link_verified':False,
        'contact_sheet':str(OUT/f'clip-{index:03d}-qa.jpg')}
    metadata['revision_id']=api._register_clip(path,metadata)['revision_id']
    (folder/'data.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    reports.append({'clip':index,'template':template['template_id'],'duration_seconds':info['duration'],
        'cta_at_seconds':cta_at,'cta_seconds':template['cta_duration_seconds'],'voice_correlation':voice,
        'cta_correlation':cta,'cta_opening_correlation':cta_opening,'final_mix_cta_opening_correlation':final_cta_opening,
        'cta_source_leading_silence_seconds':source_onset,
        'cta_render_leading_silence_seconds':final_onset,'story_broll_count':len(template['broll']),
        'story_broll_ratio':template['story_broll_ratio'],'tracking':metadata['qa_evidence']['tracking'],
        'fps':info['fps'],'final_sha256':metadata['final_sha256'],
        'audio':metadata['audio_analysis'],'music_balance':metadata['music_balance'],'warnings':metadata['warnings']})
    (folder/'PUBLICATION_CAPTION.txt').write_text(metadata['captions']['tiktok'],encoding='utf-8')
report_path=OUT/'QA_REPORT.json'
previous=json.loads(report_path.read_text(encoding='utf-8')) if report_path.is_file() else []
reports=sorted([r for r in previous if r['clip'] not in args.clips]+reports,key=lambda r:r['clip'])
report_path.write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(reports,ensure_ascii=False,indent=2))
