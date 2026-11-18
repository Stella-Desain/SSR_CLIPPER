"""Inspect finished editorial samples and build a local review page."""
from pathlib import Path
import hashlib
import html
import json
import subprocess
import sys
import wave

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.editing import analyze_audio, probe_media

BASE = ROOT / 'output/editor-free-20261007'
FFMPEG = ROOT / 'ffmpeg/ffmpeg.exe'


def run(args):
    result = subprocess.run([str(a) for a in args], capture_output=True,
                            encoding='utf-8', errors='replace', timeout=240,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.returncode:
        raise RuntimeError(result.stderr[-2500:])
    return result


def speech_alignment(movie, voice_path, speech_duration):
    """Correlate observed speech with the encoded MP4 at both ends."""
    with wave.open(str(voice_path), 'rb') as wav:
        channels, rate = wav.getnchannels(), wav.getframerate()
        voice = np.frombuffer(wav.readframes(wav.getnframes()), dtype='<i2')
        voice = voice.reshape(-1, channels).mean(axis=1)[::4] / 32768.0
    sample_rate = rate // 4
    values = {}
    for name, start in [('opening', 0.0), ('ending', max(0.0, speech_duration - 6))]:
        # Binary output bypasses the text-mode helper.
        raw = subprocess.run([str(FFMPEG), '-v', 'error', '-threads', '2', '-ss', str(start),
                              '-i', str(movie), '-t', '6', '-vn', '-ac', '1', '-ar', str(sample_rate),
                              '-f', 'f32le', '-acodec', 'pcm_f32le', '-'], capture_output=True, timeout=60,
                             creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if raw.returncode:
            raise RuntimeError(raw.stderr.decode('utf-8', errors='replace'))
        b = np.frombuffer(raw.stdout, dtype='<f4').astype(np.float64)
        offset = int(round(start * sample_rate))
        a = voice[offset:offset + len(b)]
        b = b[:len(a)]
        a, b = a - a.mean(), b - b.mean()
        size = 1 << (len(a) + len(b) - 1).bit_length()
        correlation = np.fft.irfft(np.fft.rfft(b, size) * np.conjugate(np.fft.rfft(a, size)), size)
        lags = np.arange(-2400, 2401)
        best = int(lags[np.argmax(correlation[lags % size])])
        values[name] = best / sample_rate
        assert abs(values[name]) <= .025, values
    return values


def main():
    selection = json.loads((BASE / 'selection.json').read_text(encoding='utf-8'))
    requested = int(sys.argv[1]) if len(sys.argv) > 1 else None
    report = []
    cards = []
    descriptions = [
        'Framing dekat, ilustrasi akar yang tumbuh, subtitle mengikuti ucapan, dan musik kontemplatif.',
        'Diagram skill tree bergerak, contoh kemampuan bisnis, framing pembicara, dan musik ritmis yang tenang.',
    ]
    for i, item in enumerate(selection['clips'], 1):
        folder = BASE / f'video-{i:02d}'
        movie = folder / 'master.mp4'
        composition = folder / 'composition'
        if requested and i != requested:
            saved = folder / 'verification.json'
            if not saved.is_file():
                continue
            prior = json.loads(saved.read_text(encoding='utf-8'))
            assert hashlib.sha256(movie.read_bytes()).hexdigest() == prior['sha256']
            report.append(prior)
            continue
        expected = item['end'] - item['start'] + .55
        media = probe_media(movie, str(FFMPEG))
        assert media['width'] == 1080 and media['height'] == 1920, media
        assert abs(media['fps'] - 24) < .001, media
        assert abs(media['duration'] - expected) < .06, media
        assert media['has_audio'], media
        decoded = run([FFMPEG, '-v', 'error', '-threads', '2', '-i', movie,
                       '-map', '0:v:0', '-map', '0:a:0', '-f', 'null', '-'])
        assert not decoded.stderr.strip(), decoded.stderr
        audio = analyze_audio(movie, str(FFMPEG), media)
        assert audio['status'] == 'measured', audio
        assert audio['true_peak_dbtp'] < 0, audio
        alignment = speech_alignment(movie, composition / 'voice.wav', item['end'] - item['start'])
        check = json.loads((composition / 'check-result.json').read_text(encoding='utf-8-sig'))
        assert check['ok'], check
        for phase in ('lint', 'runtime', 'layout', 'contrast'):
            assert check[phase]['errorCount'] == 0 and check[phase]['warningCount'] == 0, check[phase]
        with wave.open(str(composition / 'mix.wav'), 'rb') as wav:
            audio_length = wav.getnframes() / wav.getframerate()
            assert abs(audio_length - expected) < .0001
        observed = json.loads((folder / 'words.json').read_text(encoding='utf-8'))
        captions = json.loads((composition / 'caption-groups.json').read_text(encoding='utf-8'))
        caption_text = ''.join(w['text'] for g in captions for w in g['words'])
        assert caption_text == ''.join(w['text'] for w in observed), 'Caption words are missing'
        assert max(w['end'] for w in observed) <= item['end'] - item['start'] + .001
        frames = folder / 'final-frames'
        frames.mkdir(exist_ok=True)
        times = [1.8, 7.8, 18.5, 32.4, 37.8, expected - .18] if i == 1 else [1.8, 8.0, 18.5, 32.3, 41.5, expected - .18]
        sheet = Image.new('RGB', (1080, 1350), '#161719')
        draw = ImageDraw.Draw(sheet)
        for index, timestamp in enumerate(times):
            frame = frames / f'{index+1:02d}-{timestamp:.2f}.jpg'
            run([FFMPEG, '-v', 'error', '-threads', '2', '-ss', str(timestamp),
                 '-i', movie, '-frames:v', '1', '-q:v', '2', '-y', frame])
            with Image.open(frame) as image:
                x, y = (index % 3) * 360, (index // 3) * 675
                sheet.paste(image.resize((360, 640), Image.Resampling.LANCZOS), (x, y))
                draw.text((x+12, y+650), f'{timestamp:.2f}s', fill='white')
                if index == 0:
                    image.save(folder / 'poster.jpg', quality=92)
        sheet.save(folder / 'final-contact-sheet.jpg', quality=94)
        digest = hashlib.sha256(movie.read_bytes()).hexdigest()
        report.append({
            'title': item['title'], 'file': str(movie.resolve()), 'sha256': digest,
            'source_url': selection['source_url'], 'source_start': item['start'], 'source_end': item['end'],
            'expected_duration': expected, 'media': media, 'audio': audio,
            'composition_check': check, 'full_decode_passed': True,
            'all_observed_words_captioned': True, 'music': 'Original procedural score; separate per video',
            'encoded_mp4_speech_alignment_lag_seconds': alignment,
            'editing_mode': 'bespoke_authored_in_current_chat', 'campaign_template_used': False,
            'editorial_notes': descriptions[i-1],
        })
        (folder / 'verification.json').write_text(json.dumps(report[-1], ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps([{'title': x['title'], 'media': x['media'], 'audio': x['audio'],
                      'speech_alignment': x['encoded_mp4_speech_alignment_lag_seconds']} for x in report], ensure_ascii=False))
    if len(report) != 2:
        return
    for i, item in enumerate(report, 1):
        title = html.escape(item['title'])
        media = item['media']
        cards.append(f'''<article><h2>{i}. {title}</h2>
<p>{media['duration']:.2f} detik · 1080 × 1920 · 24 fps</p>
<video controls preload="metadata" playsinline poster="video-{i:02d}/poster.jpg" src="video-{i:02d}/master.mp4"></video>
<p>{html.escape(descriptions[i-1])}</p>
<a href="video-{i:02d}/master.mp4" download>Unduh MP4</a></article>''')
    (BASE / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    (BASE / 'PREVIEW.html').write_text('''<!doctype html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Dua video · Editor bebas</title>
<style>html{color-scheme:dark}*{box-sizing:border-box}body{margin:0;background:#161719;color:#f5f0e2;font:16px/1.6 system-ui,sans-serif;padding:32px}
main{max-width:1050px;margin:auto}h1{font-size:32px;line-height:1.2;margin-bottom:12px}h2{font-size:21px;line-height:1.35}
.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px;margin-top:28px}article{background:#212323;border:1px solid #40443a;border-radius:20px;padding:24px}
video{display:block;width:100%;max-height:75vh;background:#111;aspect-ratio:9/16;border-radius:12px}p{color:#d4d2c9}a{display:inline-block;color:#d7e6ac;padding:9px 0}
@media(max-width:680px){body{padding:20px}.grid{grid-template-columns:1fr}}
</style></head><body><main><h1>Dua video, editing bebas.</h1>
<p>Sumber Timothy Ronald. Dua highlight dipilih acak dari kandidat yang sebelumnya lolos pemeriksaan. Setiap video memakai komposisi baru dan musik asli yang berbeda.</p>
<section class="grid">''' + '\n'.join(cards) + '</section></main></body></html>', encoding='utf-8')
    lines = ['# Dua video dengan editing bebas', '',
             'Tidak memerlukan tambahan skill editor untuk eksperimen ini. Komposisi dibuat khusus dengan HyperFrames dan dirender melalui FFmpeg.', '',
             f'Sumber: {selection["source_url"]}',
             'Sumber 4K yang sudah tersimpan digunakan kembali; hanya dua rentang terpilih yang diambil untuk komposisi.',
             'Pemilihan acak disimpan di selection.json. Template campaign sebelumnya tidak digunakan.', '',
             '## Hasil', '']
    for i, item in enumerate(report, 1):
        lines += [f'### {i}. {item["title"]}', '',
                  f'- File: video-{i:02d}/master.mp4',
                  f'- Rentang sumber: {item["source_start"]:.2f}–{item["source_end"]:.2f} detik.',
                  f'- Durasi final: {item["media"]["duration"]:.3f} detik, termasuk penutup 0.55 detik setelah ucapan.',
                  f'- Editing: {item["editorial_notes"]}',
                  f'- Audio final: {item["audio"]["integrated_lufs"]} LUFS; puncak {item["audio"]["true_peak_dbtp"]} dBTP.', '']
    lines += ['## Pemeriksaan', '',
              '- Kedua file MP4 berhasil didekode sampai akhir tanpa error.',
              '- 1080 × 1920, 24 fps, dengan track audio.',
              '- Pemeriksaan komposisi, tata letak, runtime, dan kontras: tidak ada error atau warning.',
              '- Semua kata pada transkrip sumber terpilih masuk subtitle; kata majemuk yang terpisah tanda hubung disatukan.',
              '- Waveform ucapan sumber dibandingkan dengan audio MP4 pada awal dan akhir; selisih maksimum 25 milidetik.',
              '- Musik dibuat untuk masing-masing video dan diturunkan otomatis saat pembicara berbicara.',
              '- Gambar final diambil dari MP4 hasil render untuk pemeriksaan visual.', '',
              'Pemeriksaan ini memastikan aspek teknis. Penilaian rasa editing tetap membutuhkan menonton dan mendengar hasil final.', '',
              '## Referensi gaya', '',
              '- E:/Downloads/Kresna_Radithya_video_no_watermark.mp4',
              '- E:/Downloads/YoaClips_video_no_watermark (1).mp4',
              '- E:/Downloads/Timothy_Buffet_Indonesia_video_no_watermark.mp4', '',
              'Referensi digunakan sebagai arahan teks, framing, dan visual yang relevan. Musik dan footage referensi tidak disalin.',
              'Keputusan editing dibuat di percakapan ini; tidak ada klaim panggilan model API yang terverifikasi.',
              'PREVIEW.html menampilkan kedua hasil final. Folder composition menyimpan sumber project yang dapat direvisi.', '']
    (BASE / 'HASIL.md').write_text('\n'.join(lines), encoding='utf-8')


if __name__ == '__main__':
    main()
