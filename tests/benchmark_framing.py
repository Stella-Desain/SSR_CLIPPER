"""Compare local framing implementations without AI calls or source mutations.

python tests/benchmark_framing.py --source INPUT [--source INPUT] --output DIRECTORY
Creates three short samples per source, videos, contact sheets and a JSON report.
"""
import argparse
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from clipper_core import AutoClipperCore
from services.editing import file_sha256, probe_media, bounded_ffmpeg_command
from services.framing import frame_video


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', action='append')
    parser.add_argument('--recheck', action='append', help='Re-render samples from an earlier report with the current renderer')
    parser.add_argument('--output', required=True)
    parser.add_argument('--seconds', type=float, default=4)
    args = parser.parse_args()
    root = Path(args.output).resolve()
    root.mkdir(parents=True, exist_ok=True)
    if (root / 'report.json').exists():
        parser.error('Choose a new output directory to preserve the previous benchmark.')
    if args.recheck:
        recheck(args.recheck, root)
        return
    if not args.source:
        parser.error('Provide --source or --recheck.')
    sources = [Path(p).resolve() for p in args.source]
    report = {'sources': [], 'cases': [], 'settings': {'duration': args.seconds, 'encoder': 'libx264 fast crf18', 'detector': 'opencv'}}
    for source_index, source in enumerate(sources, 1):
        before = file_sha256(source)
        info = probe_media(source)
        report['sources'].append({'path': str(source), 'sha256': before, **info})
        length = min(args.seconds, info['duration'])
        for position, fraction in [('start', 0), ('middle', .5), ('end', 1)]:
            start = max(0, (info['duration'] - length) * fraction)
            folder = root / f'{source_index:02d}-{position}'
            folder.mkdir(exist_ok=True)
            sample = folder / 'source.mp4'
            subprocess.run(bounded_ffmpeg_command(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-ss', str(start), '-i', str(source),
                '-t', str(length), '-map', '0:v:0', '-map', '0:a?', '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
                '-pix_fmt', 'yuv420p', '-fps_mode', 'passthrough', '-c:a', 'aac', str(sample)]), check=True, capture_output=True, timeout=120)
            case = {'id': folder.name, 'source': source_index, 'start_seconds': start, 'input': probe_media(sample)}
            core = AutoClipperCore(client=None, output_dir=str(folder / 'work'), log_callback=lambda *_: None)
            core.face_tracking_mode = 'opencv'
            core.campaign_config = {'editing': {'framing': 'speaker'}}
            core.get_video_encoder_args = lambda: ['-c:v', 'libx264', '-preset', 'fast', '-crf', '18', '-threads', '2']
            try:
                for name, renderer in [('old', core.convert_to_portrait_opencv_with_progress),
                                       ('new', lambda src, out, cb: frame_video(core, src, out, cb))]:
                    output = folder / f'{name}.mp4'
                    began = time.perf_counter()
                    try:
                        with redirect_stdout(io.StringIO()):
                            renderer(str(sample), str(output), lambda *_: None)
                        case[name] = {'seconds': round(time.perf_counter() - began, 3), **probe_media(output)}
                        if name == 'new':
                            camera = json.loads((folder / 'camera.json').read_text(encoding='utf-8'))
                            case[name]['camera'] = camera
                    except Exception as exc:
                        case[name] = {'error': str(exc), 'seconds': round(time.perf_counter() - began, 3)}
                contact_sheet(folder, length / 2)
            finally:
                core.cleanup()
            report['cases'].append(case)
            (root / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps({'case': case['id'], 'old': case['old'].get('seconds'), 'new': case['new'].get('seconds'),
                'fit_frames': case['new'].get('camera', {}).get('fit_frames'), 'error': case['new'].get('error') or case['old'].get('error')}, ensure_ascii=False), flush=True)
        report['sources'][-1]['unchanged'] = file_sha256(source) == before
    (root / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(str(root / 'report.json'), flush=True)


def recheck(reports, root):
    result = {'reports': reports, 'cases': [], 'sources': []}
    for report_index, report_path in enumerate(reports, 1):
        report_path = Path(report_path).resolve()
        report = json.loads(report_path.read_text(encoding='utf-8'))
        for source in report['sources']:
            result['sources'].append({**source, 'unchanged': file_sha256(source['path']) == source['sha256']})
        for case in report['cases']:
            previous = report_path.parent / case['id']
            sample = previous / 'source.mp4'
            folder = root / f'{report_index}-{case["id"]}'
            folder.mkdir(parents=True, exist_ok=True)
            core = AutoClipperCore(client=None, output_dir=folder/'work', log_callback=lambda *_:None)
            core.campaign_config = {'editing': {'framing':'speaker'}}
            output = folder / 'new.mp4'
            item = {'id': folder.name, 'source_path':str(sample), 'input':probe_media(sample)}
            began = time.perf_counter()
            try:
                frame_video(core, sample, output, lambda *_:None)
                item['new'] = {**probe_media(output), 'seconds':round(time.perf_counter()-began,3),
                    'camera':json.loads((folder/'camera.json').read_text(encoding='utf-8'))}
                contact_sheet(folder, item['input']['duration']/2, {'source':sample,'old':previous/'old.mp4','new':output})
            except Exception as exc:
                item['error'] = str(exc)
            finally:
                core.cleanup()
            result['cases'].append(item)
            (root/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps({'case':item['id'],'error':item.get('error'),'seconds':item.get('new',{}).get('seconds')}),flush=True)


def contact_sheet(folder, seconds, paths=None):
    import cv2
    from PIL import Image, ImageDraw
    canvas = Image.new('RGB', (1200, 610), '#eeeeee')
    draw = ImageDraw.Draw(canvas)
    for name, x, width in [('source', 10, 560), ('old', 590, 270), ('new', 900, 270)]:
        path = paths[name] if paths else folder / f'{name}.mp4'
        cap = cv2.VideoCapture(str(path))
        cap.set(cv2.CAP_PROP_POS_MSEC, seconds * 1000)
        ok, frame = cap.read()
        cap.release()
        if ok:
            image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            image.thumbnail((width, 550))
            canvas.paste(image, (x, 50 + (550-image.height)//2))
        draw.text((x, 15), f'{folder.name} / {name}', fill='#111111')
    canvas.save(folder / 'comparison.jpg', quality=92)


if __name__ == '__main__':
    main()
