"""Deterministic native montage renderer driven by editable JSON recipes.

This renderer is intentionally independent of the dialogue/highlight pipeline.
It never adds voiceover, captions, CTA, or unrelated B-roll implicitly.
"""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .editing import file_sha256, probe_media
from .beat_effects import apply_beat_effects, validate_beat_effects
from .montage_layers import prepare_text_layers, apply_text_layers, audio_arguments, validate_layers
from .storage import atomic_json, digest
from utils.helpers import get_ffmpeg_path

RENDER_VERSION = 4
PREPARE_VERSION = 1  # Beat accents do not change the SDR source cache.
ROOT = Path(__file__).resolve().parents[1]


@lru_cache(maxsize=64)
def smooth_anchor_path(points, duration):
    samples = np.linspace(0, duration, max(2, round(duration * 30)))
    knots = np.array(points, dtype=np.float64)
    kernel_x = np.arange(-6, 7, dtype=np.float64)
    kernel = np.exp(-.5 * (kernel_x / 3) ** 2)
    kernel /= kernel.sum()
    curves = []
    for column in [1, 2]:
        raw = np.interp(samples, knots[:, 0], knots[:, column])
        curves.append(np.convolve(np.pad(raw, 6, mode='edge'), kernel, mode='valid'))
    return np.stack(curves, axis=-1)


def validate_recipe(recipe):
    if recipe.get('schema') != 'ssr-achievement-montage':
        raise ValueError('Unknown montage recipe')
    canvas = recipe.get('canvas', {'width': 1080, 'height': 1920, 'fps': 30})
    if (canvas.get('fps', 30) != 30 or any(not isinstance(canvas[k], int) or not 2 <= canvas[k] <= 4096 or canvas[k] % 2 for k in ['width', 'height'])):
        raise ValueError('Canvas must use even dimensions and the 30 fps renderer')
    hook = recipe['hook']
    rules = recipe.get('constraints', {})
    required_word = rules.get('hook_required_word', '')
    if ((required_word and required_word.upper() not in hook['text'].upper())
            or float(hook['duration']) < float(rules.get('min_hook_seconds', 0))):
        raise ValueError('Opening hook does not satisfy this campaign')
    total = sum(float(s['duration']) for s in recipe['scenes'])
    if not float(rules.get('min_seconds', .1)) <= total <= float(rules.get('max_seconds', 1800)):
        raise ValueError('Montage duration does not satisfy this campaign')
    validate_beat_effects(recipe.get('beat_effects'), float(hook['duration']), total)
    validate_layers(recipe, total)
    seen = []
    if recipe.get('cta', {}).get('required') and not any(s.get('role') == 'cta' for s in recipe['scenes']):
        raise ValueError('This campaign requires a CTA scene, but its asset is missing')
    for scene in recipe['scenes']:
        path = Path(scene['path'])
        if not path.is_file():
            raise ValueError('Missing source: ' + str(path))
        if scene.get('source_role') == 'editing_reference_only':
            raise ValueError('Finished reference edits cannot be production sources')
        start = float(scene.get('source_start', 0))
        rate = float(scene.get('playback_rate', 1))
        if not .1 <= rate <= 10:
            raise ValueError('Scene playback rate must be between 0.1 and 10')
        if rate != 1 and recipe.get('narration') and scene.get('role') != 'b_roll':
            raise ValueError('Retiming a dialogue picture would desync its original voice')
        end = start + float(scene['duration']) * rate
        for other_path, other_start, other_end in seen:
            if path == other_path and max(start, other_start) < min(end, other_end):
                raise ValueError('Repeated source range inside one montage')
        seen.append((path, start, end))
    for event in recipe.get('transitions', []):
        if event['at'] - event['duration'] / 2 < hook['duration']:
            raise ValueError('Film burn cannot obscure the opening hook')
    if not Path(recipe['music']['path']).is_file():
        raise ValueError('Missing licensed soundtrack')
    return total


def prepare_scene(scene, cache, ffmpeg):
    source = Path(scene['path'])
    if source.suffix.lower() in {'.png', '.jpg', '.jpeg'}:
        return source
    identity = {'file': file_sha256(source), 'start': scene.get('source_start', 0),
                'duration': scene['duration'], 'fps': 30, 'version': PREPARE_VERSION}
    rate = float(scene.get('playback_rate', 1))
    if rate != 1:
        identity['playback_rate'] = rate
    key = digest(identity)[:24]
    target = cache / (key + '.mp4')
    if target.exists():
        return target
    probe = subprocess.run([str(Path(ffmpeg).with_name('ffprobe.exe')), '-v', 'error',
        '-select_streams', 'v:0', '-show_entries', 'stream=color_transfer', '-of', 'json', str(source)], capture_output=True, check=True)
    transfer = json.loads(probe.stdout)['streams'][0].get('color_transfer')
    filters = ([f'setpts=(PTS-STARTPTS)/{rate}'] if rate != 1 else [])
    filters += ['fps=30', 'scale=w=min(iw\\,1920):h=-2']
    if transfer in {'arib-std-b67', 'smpte2084'}:
        filters += ['zscale=t=linear:npl=100', 'format=gbrpf32le',
                    'zscale=p=bt709', 'tonemap=tonemap=mobius:desat=0',
                    'zscale=t=bt709:m=bt709:r=tv']
    command = [ffmpeg, '-v', 'error', '-y', '-threads', '2', '-ss', str(scene.get('source_start', 0)),
               '-i', str(source), '-t', str(scene['duration']), '-an',
               '-vf', ','.join(filters), '-c:v', 'libx264',
               '-preset', 'veryfast', '-crf', '18', '-threads', '2', '-pix_fmt', 'yuv420p', str(target)]
    result = subprocess.run(command, capture_output=True)
    if result.returncode:
        target.unlink(missing_ok=True)
        raise RuntimeError(result.stderr.decode(errors='replace')[-1800:])
    actual = probe_media(target, ffmpeg)['duration']
    if actual < float(scene['duration']) - .06:
        target.unlink(missing_ok=True)
        raise ValueError('Source range extends beyond the available footage')
    return target


def frame_scene(frame, scene, progress, width, height):
    source_h, source_w = frame.shape[:2]
    mode = scene.get('fit', 'contain')
    if mode == 'context':
        # A wider portrait card preserves the whole face in close vlog shots.
        # This avoids tightening a 16:9 close-up to a full-height 9:16 crop.
        card_height = round(height * float(scene.get('context_height', .70)))
        inner = frame_scene(frame, {**scene, 'fit': 'fill'}, progress, width, card_height)
        output = np.full((height, width, 3), tuple(reversed(scene.get('matte_rgb', [24,24,24]))), dtype=np.uint8)
        top = (height-card_height)//2
        output[top:top+card_height] = inner
        return output
    if mode == 'inset_fill':
        margin = float(scene.get('margin', .05))
        inner_width, inner_height = round(width * (1 - 2 * margin)), round(height * (1 - 2 * margin))
        inner = frame_scene(frame, {**scene, 'fit': 'fill'}, progress, inner_width, inner_height)
        output = np.full((height, width, 3), tuple(reversed(scene.get('matte_rgb', [102, 102, 102]))), dtype=np.uint8)
        left, top = (width - inner_width) // 2, (height - inner_height) // 2
        output[top:top+inner_height, left:left+inner_width] = inner
        return output
    if mode == 'fill':
        crop_bottom = float(scene.get('crop_bottom', 0))
        if crop_bottom:
            frame = frame[:round(source_h * (1 - crop_bottom))]
            source_h, source_w = frame.shape[:2]
        eased = progress * progress * (3 - 2 * progress)
        zoom = float(scene.get('zoom', 1))
        zoom += (float(scene.get('zoom_end', zoom)) - zoom) * eased
        ratio = max(width / source_w, height / source_h) * zoom
        scaled = cv2.resize(frame, (round(source_w * ratio), round(source_h * ratio)), interpolation=cv2.INTER_CUBIC)
        # Authored anchor paths move continuously; they do not react to head jitter.
        a = scene.get('anchor', [.5, .5])
        b = scene.get('anchor_end', a)
        center = [a[0] + (b[0] - a[0]) * eased, a[1] + (b[1] - a[1]) * eased]
        if scene.get('anchor_path'):
            path = smooth_anchor_path(tuple(tuple(p) for p in scene['anchor_path']), float(scene['duration']))
            center = path[min(len(path)-1, round(progress*(len(path)-1)))]
        center_x = center[0] * scaled.shape[1]
        center_y = center[1] * scaled.shape[0]
        x = max(0, min(scaled.shape[1] - width, center_x - width / 2))
        y = max(0, min(scaled.shape[0] - height, center_y - height / 2))
        output = cv2.getRectSubPix(scaled, (width, height), (x + (width - 1) / 2, y + (height - 1) / 2))
    else:
        margin = float(scene.get('margin', .05))
        ratio = min(width * (1 - 2 * margin) / source_w, height * (1 - 2 * margin) / source_h)
        scaled = cv2.resize(frame, (round(source_w * ratio), round(source_h * ratio)), interpolation=cv2.INTER_CUBIC)
        color = tuple(reversed(scene.get('matte_rgb', [102, 102, 102])))
        output = np.full((height, width, 3), color, dtype=np.uint8)
        x, y = (width - scaled.shape[1]) // 2, (height - scaled.shape[0]) // 2
        output[y:y + scaled.shape[0], x:x + scaled.shape[1]] = scaled
    if scene.get('payoff_wobble'):
        angle = float(scene['payoff_wobble']) * math.sin(progress * math.pi * 4)
        matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.045)
        output = cv2.warpAffine(output, matrix, (width, height), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT_101)
        pulse = 1 + .06 * max(0, math.sin(progress * math.pi * 8))
        output = np.clip(output.astype(np.float32) * pulse, 0, 255).astype(np.uint8)
    if scene.get('gamma'):
        output = np.clip(255 * (output.astype(np.float32) / 255) ** (1 / float(scene['gamma'])), 0, 255).astype(np.uint8)
    return output


def make_hook(hook, width, height):
    x, y, w, h = [round(n * dimension) for n, dimension in zip(hook['bounds'], [width, height, width, height])]
    size = int(hook.get('font_size', 62))
    font_path = hook.get('font_path', 'C:/Windows/Fonts/ariblk.ttf')
    lines = hook['text'].split('\n')
    while True:
        font = ImageFont.truetype(font_path, size)
        if max(font.getlength(line) for line in lines) <= w - 60 or size <= 24:
            break
        size -= 1
    spacing = round(size * 1.32)
    h = max(h, spacing * len(lines) + 38)
    plate = Image.new('RGBA', (width, height))
    draw = ImageDraw.Draw(plate)
    draw.rectangle((x + 6, y + 9, x + w + 6, y + h + 9), fill=(0, 0, 0, 35))
    draw.rectangle((x, y, x + w, y + h), fill=hook.get('background', '#ffffff'))
    if hook.get('red_rule'):
        draw.rectangle((x, y - 9, x + w, y - 1), fill=hook.get('accent', '#e31327'))
    top = y + (h - spacing * len(lines)) / 2
    for index, line in enumerate(lines):
        left = x + 30 if hook.get('alignment') == 'left' else x + (w - font.getlength(line)) / 2
        baseline = top + index * spacing
        draw.text((left, baseline), line, font=font, fill=hook.get('color', '#000000'), anchor='lt')
        if hook.get('accent_word') and 'IRONMAN' in line:
            before = line.split('IRONMAN')[0]
            draw.text((left + font.getlength(before), baseline), 'IRONMAN', font=font,
                      fill=hook.get('accent', '#e31327'), anchor='lt')
    return np.array(plate)


def film_burn(frame, progress, intensity=.8, seed=0):
    """Finite warm organic flare with uneven moving edges and screen blending.

    Native adaptation of Registry's organic-light-leak-overlay: amber/red/gold
    layers, one rise/peak/recovery, no black blend plate or looping texture.
    """
    y, x = np.mgrid[0:480, 0:270].astype(np.float32)
    x /= 270
    y /= 480
    if seed % 2:
        x = 1 - x
    envelope = math.sin(math.pi * progress) ** 1.3 * intensity
    texture = .06 * np.sin(13 * y + seed + progress * 2) + .035 * np.sin(28 * y - progress * 4)
    edge = -.16 + .68 * math.sin(math.pi * progress)
    distance = (x - edge - texture) / .19
    amber = np.exp(-np.maximum(0, distance) ** 2) * np.exp(-((y - .58) / .8) ** 2)
    red = np.exp(-((x - .93 + .2 * progress) / .24) ** 2 - ((y - .27) / .72) ** 2)
    gold = np.exp(-((x - .1 - .65 * progress + .08 * y) / .12) ** 2)
    rgb = np.stack([amber + .55 * red + .45 * gold,
                    .52 * amber + .09 * red + .42 * gold,
                    .19 * amber + .07 * red + .28 * gold], axis=-1)
    overlay = cv2.resize(np.clip(rgb * envelope, 0, 1)[:, :, ::-1], (frame.shape[1], frame.shape[0]))
    return np.clip(255 - (255 - frame.astype(np.float32)) * (1 - overlay), 0, 255).astype(np.uint8)


def render_recipe(recipe_path, destination):
    cv2.setNumThreads(2)
    recipe_path, destination = Path(recipe_path), Path(destination)
    recipe_bytes = recipe_path.read_bytes()
    recipe = json.loads(recipe_bytes.decode('utf-8'))
    recipe_hash = hashlib.sha256(recipe_bytes).hexdigest()
    duration = validate_recipe(recipe)
    canvas = recipe.get('canvas', {'width': 1080, 'height': 1920, 'fps': 30})
    width, height, fps = canvas['width'], canvas['height'], 30
    destination.parent.mkdir(parents=True, exist_ok=True)
    cache = destination.parent.parent / 'scene-cache'
    cache.mkdir(exist_ok=True)
    ffmpeg = get_ffmpeg_path()
    prepared = [prepare_scene(s, cache, ffmpeg) for s in recipe['scenes']]
    hook = make_hook(recipe['hook'], width, height)
    hook_alpha = hook[:, :, 3:4].astype(np.float32) / 255
    hook_rgb = hook[:, :, :3][:, :, ::-1]
    music = recipe['music']
    text_layers = prepare_text_layers(recipe.get('text_overlays', []), width, height)
    audio_inputs, audio_options = audio_arguments(recipe, duration)
    log = destination.with_suffix('.encode.log')
    partial = destination.with_name(destination.stem + '.partial.mp4')
    command = [ffmpeg, '-y', '-v', 'warning', '-f', 'rawvideo', '-pix_fmt', 'bgr24',
               '-s', f'{width}x{height}', '-r', str(fps), '-i', 'pipe:0',
               *audio_inputs,
               '-map', '0:v:0', *audio_options, '-t', str(duration),
               '-c:v', 'h264_qsv', '-global_quality', '17', '-profile:v', 'high',
               '-g', '60', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000',
               '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709',
               '-movflags', '+faststart', str(partial)]
    frame_number = 0
    with log.open('w', encoding='utf-8') as errors:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=errors)
        try:
            for index, (scene, source) in enumerate(zip(recipe['scenes'], prepared)):
                is_image = source.suffix.lower() in {'.jpg', '.jpeg', '.png'}
                capture = None if is_image else cv2.VideoCapture(str(source))
                still = cv2.imread(str(source)) if is_image else None
                moving_still = scene.get('payoff_wobble') or 'zoom_end' in scene or 'anchor_end' in scene
                static_frame = frame_scene(still, scene, .5, width, height) if is_image and not moving_still else None
                static_hook_frame = None
                frames = round(float(scene['duration']) * fps)
                last_raw = None
                for n in range(frames):
                    t = frame_number / fps
                    if is_image:
                        raw = still
                    else:
                        success, raw = capture.read()
                        if not success:
                            # A VFR cut can round down by exactly one output frame.
                            # Hold that last decoded frame for <= 1/30 s; reject
                            # larger gaps rather than hiding missing footage.
                            if n == frames - 1 and last_raw is not None:
                                raw = last_raw
                                scene['tail_padding_frames'] = 1
                            else:
                                raise ValueError(f'Unexpected end of source in scene {index + 1}, frame {n}')
                        last_raw = raw
                    frame = static_frame.copy() if static_frame is not None else frame_scene(raw, scene, n / max(1, frames - 1), width, height)
                    frame = apply_beat_effects(frame, t, recipe.get('beat_effects'))
                    for event in recipe.get('transitions', []):
                        relative = (t - event['at'] + event['duration'] / 2) / event['duration']
                        if 0 < relative < 1:
                            frame = film_burn(frame, relative, event.get('intensity', .8), event.get('seed', 0))
                    if t < recipe['hook']['duration']:
                        entrance = recipe['hook'].get('entry_seconds', .15)
                        opacity = min(1, .35 + .65 * t / max(.001, entrance))
                        if recipe['hook'].get('exit_seconds'):
                            opacity = min(opacity, (recipe['hook']['duration'] - t) / recipe['hook']['exit_seconds'])
                        if static_frame is not None and opacity == 1 and static_hook_frame is not None:
                            frame = static_hook_frame.copy()
                        else:
                            alpha = hook_alpha * opacity
                            frame = (frame * (1 - alpha) + hook_rgb * alpha).astype(np.uint8)
                            if static_frame is not None and opacity == 1:
                                static_hook_frame = frame
                    frame = apply_text_layers(frame, t, text_layers)
                    process.stdin.write(frame.tobytes())
                    frame_number += 1
                if capture:
                    capture.release()
                print(f"{recipe['id']}: scene {index+1}/{len(prepared)}", flush=True)
        finally:
            process.stdin.close()
            code = process.wait()
        if code:
            raise RuntimeError(log.read_text(encoding='utf-8')[-2000:])
    partial.replace(destination)
    metadata = {'recipe': str(recipe_path.resolve()), 'recipe_sha256': recipe_hash,
                'recipe_snapshot': recipe,
                'renderer': 'native_achievement_montage', 'render_version': RENDER_VERSION,
                'duration_seconds': duration, 'final_path': str(destination.resolve()),
                'final_sha256': file_sha256(destination), 'title': recipe['title'],
                'hook_text': recipe['hook']['text'], 'editing_template': {'id': recipe['variant'], 'name': recipe['title']},
                'music': {'attribution': recipe['music']['attribution']},
                'beat_effects': recipe.get('beat_effects', {'enabled': False}),
                'original_narration': recipe.get('narration'),
                'timed_text_count': len(recipe.get('text_overlays', [])),
                'cta_present': any(s.get('role') == 'cta' for s in recipe['scenes']),
                'source_ranges': [{'source_id': s['source_id'], 'source_url': s['source_url'],
                                   'start_seconds': s.get('source_start', 0),
                                   'end_seconds': s.get('source_start', 0) + s['duration'] * s.get('playback_rate', 1),
                                   'playback_rate': s.get('playback_rate', 1),
                                   'visual_group': s['visual_group']} for s in recipe['scenes']]}
    atomic_json(destination.parent / 'data.json', metadata)
    return metadata
