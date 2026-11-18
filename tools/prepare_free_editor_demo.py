"""Prepare two randomly selected, reviewed source passages and reference sheets."""
from pathlib import Path
import json
import secrets
import subprocess
import sys
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.speech_boundaries import seconds
from services.storage import atomic_json

FFMPEG = str(ROOT / 'ffmpeg/ffmpeg.exe')
FFPROBE = str(ROOT / 'ffmpeg/ffprobe.exe')
DIRECTORY = ROOT / 'output' / 'editor-free-20261007'
SOURCE = ROOT / 'output/_headless/tD4zgAa-PqM-20261006/source/source.mp4'
WORDS = ROOT / 'output/_headless/tD4zgAa-PqM-20261006/source/reviewed-source-words.json'
REFERENCES = [Path('E:/Downloads/Kresna_Radithya_video_no_watermark.mp4'),
    Path('E:/Downloads/YoaClips_video_no_watermark (1).mp4'),
    Path('E:/Downloads/Timothy_Buffet_Indonesia_video_no_watermark.mp4')]


def run(command):
    subprocess.run(command, check=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))


def sheet(path, output, times, frame_width=320, columns=3):
    frames = []
    for index, t in enumerate(times):
        frame = output.with_name(output.stem + f'-{index}.jpg')
        run([FFMPEG, '-hide_banner', '-loglevel', 'error', '-threads', '1', '-y',
            '-ss', str(t), '-i', str(path), '-frames:v', '1', '-vf', f'scale={frame_width}:-1', str(frame)])
        frames.append(Image.open(frame).convert('RGB'))
    w, h = frames[0].size
    canvas = Image.new('RGB', (w*columns, (h+30)*((len(frames)+columns-1)//columns)), '#13171b')
    draw = ImageDraw.Draw(canvas)
    for i, frame in enumerate(frames):
        x, y = (i % columns)*w, (i//columns)*(h+30)
        canvas.paste(frame, (x,y))
        draw.text((x+8,y+h+7), f'{times[i]:.2f} s', fill='white')
    canvas.save(output)


def main():
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    ref_dir = DIRECTORY / 'reference-analysis'
    ref_dir.mkdir(exist_ok=True)
    for i, p in enumerate(REFERENCES, 1):
        duration = float(subprocess.check_output([FFPROBE, '-v','error','-show_entries',
            'format=duration','-of','default=nw=1:nk=1',str(p)], text=True))
        times = [min(duration-.25, t*duration) for t in (.02,.14,.30,.48,.70,.93)]
        sheet(p, ref_dir/f'reference-{i}.jpg', times, frame_width=270 if i != 2 else 420)
        run([FFMPEG,'-hide_banner','-loglevel','error','-y','-i',str(p),'-vn','-ac','1','-ar','16000',str(ref_dir/f'reference-{i}.wav')])
    selection_path = DIRECTORY / 'selection.json'
    if not selection_path.is_file():
        plan = json.loads((ROOT/'output/job-129d2adda72b4e00/highlights.json').read_text(encoding='utf-8'))['highlights']
        generator = secrets.SystemRandom()
        first, second = generator.sample(plan,2)
        while min(seconds(first['end_time']), seconds(second['end_time'])) > max(seconds(first['start_time']), seconds(second['start_time'])):
            second = generator.choice(plan)
        selected=[]
        for item in (first,second):
            selected.append({'title':item['title'],'description':item['description'],
                'start':seconds(item['start_time']),'end':seconds(item['end_time']),
                'highlight':{key:value for key,value in item.items() if key not in ('editing_template','agent_music_id')},
                'editing_mode':'bespoke_editor', 'campaign_template_used':False})
        atomic_json(selection_path, {'source_url':'https://www.youtube.com/watch?v=tD4zgAa-PqM',
            'source_path':str(SOURCE),'selection_method':'system_random_sample_of_51_validated_highlights_nonoverlapping',
            'campaign_id':'camp_43ef11ba', 'clips':selected})
    selection = json.loads(selection_path.read_text(encoding='utf-8'))
    observed=json.loads(WORDS.read_text(encoding='utf-8'))
    all_words=[w for segment in observed['segments'] for w in segment.get('words',[])]
    for i, item in enumerate(selection['clips'],1):
        directory=DIRECTORY/f'video-{i:02d}'
        directory.mkdir(exist_ok=True)
        start,end=item['start'],item['end']
        words=[{'text':w['word'].strip(),'start':round(w['start']-start,3),'end':round(w['end']-start,3)}
            for w in all_words if w['end']>start+.001 and w['start']<end-.001]
        assert words and words[0]['start'] >= -.02 and words[-1]['end'] <= end-start+.02
        atomic_json(directory/'words.json',words)
        context=[s for s in observed['segments'] if s['end']>start-15 and s['start']<end+15]
        (directory/'context.txt').write_text('\n'.join(f"{s['start']:.2f}-{s['end']:.2f} {s['text']}" for s in context),encoding='utf-8')
        sheet(SOURCE,directory/'source-sheet.jpg',[start+t*(end-start) for t in (.02,.2,.4,.6,.8,.97)],frame_width=500)
        print(json.dumps({'index':i,'title':item['title'],'start':start,'end':end,'duration':end-start,
            'transcript':' '.join(w['text'] for w in words)},ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
