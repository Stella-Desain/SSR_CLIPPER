"""Extract the two original passages, prepare honest captions and original scores."""
from pathlib import Path
import json
import shutil
import subprocess
import sys
import wave
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'output/editor-free-20261007'
FFMPEG=str(ROOT/'ffmpeg/ffmpeg.exe')


def ffmpeg(args):
    subprocess.run([FFMPEG,'-hide_banner','-loglevel','error','-y','-filter_threads','1',*args],
        check=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))


def save_wav(path, audio, rate=48000):
    with wave.open(str(path),'wb') as stream:
        stream.setnchannels(2); stream.setsampwidth(2); stream.setframerate(rate)
        stream.writeframes((np.clip(audio,-.99,.99)*32767).astype('<i2').tobytes())


def score(duration, index, rate=48000):
    length=int((duration+.65)*rate)
    audio=np.zeros((length,2),dtype=np.float32)
    rng=np.random.default_rng(731+index)
    def tone(at,note,dur,amplitude=.09,pan=0,kind='bell'):
        offset=int(at*rate); n=min(int(dur*rate),length-offset)
        if n<=0:return
        t=np.arange(n,dtype=np.float32)/rate
        hz=440*2**((note-69)/12)
        if kind=='pad':
            value=np.sin(2*np.pi*hz*t)+.3*np.sin(2*np.pi*(hz*1.002)*t)+.18*np.sin(2*np.pi*hz*2*t)
            env=np.minimum(t/1.15,1)*np.minimum((dur-t)/1.4,1)
        elif kind=='bass':
            value=np.sin(2*np.pi*hz*t)+.12*np.sin(2*np.pi*hz*2*t)
            env=np.minimum(t/.02,1)*np.exp(-t*2.1)
        else:
            value=np.sin(2*np.pi*hz*t)+.25*np.sin(2*np.pi*hz*2*t)*np.exp(-t*2)+.08*np.sin(2*np.pi*hz*3*t)*np.exp(-t*5)
            env=np.minimum(t/.018,1)*np.exp(-t*1.5)
        value=value*env*amplitude
        audio[offset:offset+n,0]+=value*np.sqrt((1-pan)/2)
        audio[offset:offset+n,1]+=value*np.sqrt((1+pan)/2)
    chords=([50,57,60,64],[46,53,57,60],[53,60,64,67],[48,55,59,62])
    step=6.0 if index==1 else 4.8
    for bar,at in enumerate(np.arange(0,duration,step)):
        chord=chords[bar%4]
        for j,note in enumerate(chord):tone(at,note,step+1.4,.018 if index==1 else .013,(-.45+j*.30),'pad')
        for j,note in enumerate(chord+[chord[2]+12,chord[1]+12]):
            tone(at+.15+j*(.8 if index==1 else .55),note+12,3.3,.07 if index==1 else .05,(-.55+j*.20))
        if index==2:
            for beat in range(4):tone(at+beat*1.2,chord[0]-12,.7,.038,0,'bass')
    # Quiet, short pulses accent the appearance of conceptual branches.
    for at in ([4.65,14.5,20.2,34.9,39.0] if index==1 else [3.9,10.8,20.1,31.5,34.7,40.9]):
        tone(at,81 if index==1 else 76,.45,.035,-.2)
        tone(at+.07,88 if index==1 else 83,.38,.02,.2)
    for delay,level in ((.17,.23),(.29,.13),(.47,.07)):
        n=int(delay*rate)
        audio[n:]+=audio[:-n,::-1].copy()*level
    fade_in=np.minimum(np.arange(length)/(rate*1.2),1)
    fade_out=np.minimum((length-1-np.arange(length))/(rate*1.1),1)
    audio*=np.minimum(fade_in,fade_out)[:,None]
    # A measurable, conservative music stem; final ducking follows narration.
    audio*=.26/max(float(np.max(np.abs(audio))),.001)
    return audio


def main():
    selection=json.loads((BASE/'selection.json').read_text(encoding='utf-8'))
    for i,item in enumerate(selection['clips'],1):
        folder=BASE/f'video-{i:02d}'/'composition'
        folder.mkdir(exist_ok=True)
        fonts=folder/'fonts';fonts.mkdir(exist_ok=True)
        shutil.copy2(ROOT/'assets/fonts/PodcastBlack.ttf',fonts/'MontserratBlack.ttf')
        shutil.copy2('C:/Windows/Fonts/georgia.ttf',fonts/'Georgia.ttf')
        shutil.copy2('C:/Windows/Fonts/consola.ttf',fonts/'Consolas.ttf')
        duration=item['end']-item['start']
        output=folder/'source.mp4'
        if not output.is_file():
            ffmpeg(['-threads','2','-ss',str(item['start']),'-i',selection['source_path'],
                '-t',str(duration),'-map','0:v:0','-map','0:a:0',
                '-vf','scale=1920:1080:flags=lanczos','-c:v','libx264','-preset','fast','-crf','15',
                '-pix_fmt','yuv420p','-c:a','aac','-b:a','256k','-movflags','+faststart','-threads','2',str(output)])
        # Extract speech directly from the original audio, so a video encoder's
        # frame rounding cannot shorten the final word or shift subtitle times.
        ffmpeg(['-threads','1','-ss',str(item['start']),'-i',selection['source_path'],
            '-t',str(duration),'-vn','-ac','2','-ar','48000',str(folder/'voice.wav')])
        ffmpeg(['-i',str(output),'-ss',str(duration-.045),'-frames:v','1',str(folder/'last-frame.jpg')])
        music=folder/'music-original.wav'
        save_wav(music,score(duration,i))
        ffmpeg(['-i',str(folder/'voice.wav'),'-i',str(music),'-filter_complex',
            f'[0:a]loudnorm=I=-16:TP=-2:LRA=9,aresample=48000,apad=pad_dur=0.55,asplit=2[voice][side];'
            f'[1:a]volume=0.30[music];[music][side]sidechaincompress=threshold=0.018:ratio=4:attack=20:release=350[ducked];'
            f'[voice][ducked]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.88:level=false:latency=true,apad=whole_dur={duration+.55},atrim=duration={duration+.55},afade=t=out:st={duration+.05}:d=0.5[a]',
            '-map','[a]','-t',str(duration+.55),'-ac','2','-ar','48000',str(folder/'mix.wav')])
        words=json.loads((BASE/f'video-{i:02d}'/'words.json').read_text(encoding='utf-8'))
        # Keep the observed wording and timing; only remove isolated ASR hyphen artifacts.
        for w in words:
            w['text']=w['text'].replace(' -','-')
            if w['text'].startswith('-'): w['text']=w['text'][1:]
        (folder/'transcript.json').write_text(json.dumps(words,ensure_ascii=False),encoding='utf-8')
        (folder/'editor-assets.json').write_text(json.dumps({'source_start':item['start'],'source_end':item['end'],
            'speech_duration':duration,'final_duration':duration+.55,'music':'Original procedural composition by this editing session',
            'music_not_taken_from_references':True,'caption_timing':'observed source word timestamps'},ensure_ascii=False,indent=2),encoding='utf-8')
        print(f'ASSETS_READY {i} {duration:.2f}',flush=True)


if __name__=='__main__':main()
