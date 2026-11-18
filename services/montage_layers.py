"""Editable timed text and an explicit original-voice mix for native montages."""
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


def prepare_text_layers(layers, width, height):
    prepared = []
    for layer in layers:
        font = ImageFont.truetype(layer.get('font_path', 'C:/Windows/Fonts/ariblk.ttf'), int(layer.get('font_size', 70)))
        text = layer['text']
        while font.getlength(text) > width * .84 and font.size > 24:
            font = ImageFont.truetype(font.path, font.size - 1)
        stroke = int(layer.get('stroke_width', 4))
        bounds = font.getbbox(text, stroke_width=stroke)
        padding = 18
        w, h = bounds[2] - bounds[0] + padding * 2, bounds[3] - bounds[1] + padding * 2
        plate = Image.new('RGBA', (w, h))
        draw = ImageDraw.Draw(plate)
        if layer.get('background'):
            draw.rounded_rectangle((0, 0, w - 1, h - 1), radius=14, fill=layer['background'])
        active = layer.get('highlight_index')
        if active is not None:
            words = text.split()
            prefix = ' '.join(words[:active]) + (' ' if active else '')
            left = padding - bounds[0] + font.getlength(prefix)
            right = left + font.getlength(words[active])
            draw.rounded_rectangle((left - 8, 3, right + 8, h - 4), radius=10,
                                   fill=layer.get('highlight_color', '#1677FF'))
        draw.text((padding - bounds[0], padding - bounds[1]), text, font=font,
                  fill=layer.get('color', '#ffffff'), stroke_width=stroke,
                  stroke_fill=layer.get('stroke_color', '#101010'))
        pixels = np.array(plate)
        prepared.append((layer, pixels))
    return prepared


def apply_text_layers(frame, t, layers):
    height, width = frame.shape[:2]
    for layer, pixels in layers:
        if not layer['start'] <= t < layer['start'] + layer['duration']:
            continue
        entry = min(1., (t - layer.get('phrase_start', layer['start'])) / max(.001, layer.get('entry_seconds', .07)))
        scale = .92 + .08 * entry
        rgba = cv2.resize(pixels, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC) if entry < 1 else pixels
        h, w = rgba.shape[:2]
        center = layer.get('position', [.5, .77])
        x, y = round(center[0] * width - w / 2), round(center[1] * height - h / 2)
        left, top, right, bottom = max(0, x), max(0, y), min(width, x+w), min(height, y+h)
        if right <= left or bottom <= top:
            continue
        rgba = rgba[top-y:bottom-y, left-x:right-x]
        alpha = rgba[:, :, 3:4].astype(np.float32) / 255
        target = frame[top:bottom, left:right]
        target[:] = np.clip(target * (1-alpha) + rgba[:, :, :3][:, :, ::-1] * alpha, 0, 255).astype(np.uint8)
    return frame


def audio_arguments(recipe, duration):
    """Return FFmpeg inputs, map and filters; source 0 is the raw video pipe."""
    music = recipe['music']
    inputs = ['-ss', str(music.get('start', 0)), '-i', music['path']]
    final = f'loudnorm=I=-16:TP=-1.5:LRA=9,afade=t=in:d=0.04,afade=t=out:st={duration-.35}:d=0.35'
    narration = recipe.get('narration')
    if not narration:
        return inputs, ['-map', '1:a:0', '-af', final]
    inputs += ['-i', narration['path']]
    voice_duration = float(narration['duration'])
    # The official vlog may already carry a music bed. Avoid competing songs:
    # the new bed stays very low under its voice, then rises after the sentence.
    gain = float(music.get('volume_after_voice', .48))
    expression = f"if(lt(t,{voice_duration}),0.012,{gain}*min(1,(t-{voice_duration})/0.25))"
    filters = (f"[1:a]atrim=duration={duration},asetpts=PTS-STARTPTS,volume='{expression}':eval=frame[bed];"
               f"[2:a]atrim=duration={voice_duration},asetpts=PTS-STARTPTS,aresample=48000,apad,atrim=duration={duration}[voice];"
               f'[voice][bed]amix=inputs=2:normalize=0:duration=longest,{final}[mix]')
    return inputs, ['-filter_complex', filters, '-map', '[mix]']


def validate_layers(recipe, duration):
    narration = recipe.get('narration')
    if narration and (not Path(narration['path']).is_file() or not 0 < narration['duration'] <= duration):
        raise ValueError('Original narration is missing or exceeds the timeline')
    for layer in recipe.get('text_overlays', []):
        if not layer.get('text') or not 0 <= layer['start'] < layer['start'] + layer['duration'] <= duration + .001:
            raise ValueError('Invalid timed text layer')
        if 'highlight_index' in layer and (not isinstance(layer['highlight_index'], int)
                or not 0 <= layer['highlight_index'] < len(layer['text'].split())):
            raise ValueError('Active caption word is outside its phrase')
