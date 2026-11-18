"""Reusable portrait edits measured from the user's Ruang Berpikir references.

Campaign footage, speech, hook copy, logo and CTA are inputs, never baked into
the presets. The opening is a music-only B-roll hook; all source speech follows.
"""
from __future__ import annotations

import copy
import math
from pathlib import Path
import re
import tempfile
import unicodedata

from .editing import EditingValidationError, _run, endcard_settings, file_sha256, probe_media, validate_render_canvas

RUANG_TEMPLATES = {
    'ruang_founder': {'width': 1080, 'height': 1920, 'fps': 30, 'anchor_x': .5,
        'name': 'Ruang · Founder Story', 'font': 'RuangBebasNeue.ttf',
        'intro_seconds': 5.2, 'broll_gap_seconds': 10.0, 'broll_seconds': 2.0,
        'broll_max_ratio': .12, 'broll_max_shots': 2},
    'ruang_witness': {'width': 1080, 'height': 1920, 'fps': 30, 'anchor_x': .5,
        'name': 'Ruang · Witness Proof', 'font': 'RuangBebasNeue.ttf',
        'intro_seconds': 5.2, 'broll_gap_seconds': 12.0, 'broll_seconds': 1.8,
        'broll_max_ratio': .10, 'broll_max_shots': 2},
}

RUANG_RENDER_VERSION = 3


def font_path(template_id):
    from utils.helpers import get_bundle_dir
    path = get_bundle_dir() / 'assets/fonts' / RUANG_TEMPLATES[template_id]['font']
    if not path.is_file():
        raise EditingValidationError('Font Ruang belum tersedia dalam aplikasi.')
    return path


def style_options(campaign):
    result = (campaign or {}).get('editing', {}).get('reference_style', {})
    if not isinstance(result, dict):
        raise EditingValidationError('Pengaturan gaya referensi harus berupa object.')
    for key in ('hook_accent', 'hook_background', 'hook_text_color'):
        if key in result and not re.fullmatch(r'#[0-9a-fA-F]{6}', str(result[key])):
            raise EditingValidationError('Warna hook harus menggunakan format #RRGGBB.')
    return copy.deepcopy(result)


def checked_broll(campaign, ffmpeg='ffmpeg'):
    result = []
    for asset in (campaign or {}).get('assets', []):
        if asset.get('role') != 'broll':
            continue
        path = Path(asset.get('path', ''))
        if not path.is_file() or (asset.get('sha256') and file_sha256(path) != asset['sha256']):
            raise EditingValidationError('Aset B-roll hilang atau berubah: ' + asset.get('name', path.name))
        info = probe_media(path, ffmpeg)
        if not info['has_video']:
            raise EditingValidationError('B-roll harus berupa video atau gambar.')
        still = path.suffix.lower() in {'.png', '.jpg', '.jpeg', '.webp'}
        start = float(asset.get('start_seconds', 0))
        end = float(asset.get('end_seconds') or info['duration'] or start + 6)
        if not math.isfinite(start + end) or start < 0 or end <= start or (not still and end > info['duration'] + .05):
            raise EditingValidationError('Rentang B-roll tidak valid.')
        result.append({'asset_id': asset.get('id'), 'path': str(path.resolve()),
            'sha256': asset.get('sha256') or file_sha256(path), 'start_seconds': start,
            'available_seconds': end-start, 'is_image': still, 'tags': asset.get('tags', []),
            'opener': bool(asset.get('opener')), 'name': asset.get('name', path.stem)})
    if not result:
        raise EditingValidationError('Template Ruang memerlukan aset B-roll resmi campaign.')
    return result


def broll_plan(campaign, duration, template_id, ffmpeg='ffmpeg', cues=None):
    """Insert unique, visually tagged shots only at matching narrative cues.

    Empty/unmatched cues retain the speaker. Broad topic or benefit words do
    not prove that a shot depicts what is being said. The opener is not reused.
    """
    assets = checked_broll(campaign, ffmpeg)
    spec = RUANG_TEMPLATES[template_id]
    events, used, spent = [], set(), 0.0
    budget = duration * spec['broll_max_ratio']
    broad = {'crypto', 'kripto', 'money', 'cuan', 'profit', 'sukses', 'advantage',
             'kelebihan', 'freedom', 'success', 'trading', 'transparan'}
    def normalized(value):
        return ' '.join(re.findall(r'\w+', str(value).casefold()))
    for cue in sorted(cues or [], key=lambda c: float(c.get('start', 0))):
        at = float(cue.get('start', 0))
        if not math.isfinite(at) or at < 5 or at > duration - 5:
            continue
        if events and at < events[-1]['at_seconds'] + events[-1]['duration_seconds'] + spec['broll_gap_seconds']:
            continue
        text = normalized(cue.get('text', ''))
        ranked = []
        for asset in assets:
            identity = asset.get('sha256') or asset.get('asset_id') or asset.get('path') or asset['name']
            if asset.get('opener') or identity in used:
                continue
            tags = [normalized(tag) for tag in asset.get('tags', [])]
            matches = [tag for tag in tags if tag and tag not in broad and f' {tag} ' in f' {text} ']
            if matches:
                ranked.append((max(len(tag.split()) for tag in matches), len(matches), asset, identity, matches))
        if not ranked:
            continue
        _, _, asset, identity, matches = max(ranked, key=lambda item: item[:2])
        length = min(spec['broll_seconds'], asset['available_seconds'], duration-at-3, budget-spent)
        if length < 1.0:
            continue
        events.append({**asset, 'at_seconds': round(at, 3), 'duration_seconds': round(length, 3),
                       'cue': text, 'matched_visual_tags': matches, 'transition': 'hard_cut'})
        used.add(identity)
        spent += length
        if len(events) >= spec['broll_max_shots']:
            break
    return events


def _fit_lines(text, font, width):
    lines, current = [], ''
    for token in text.split():
        candidate = (current + ' ' + token).strip()
        if current and font.getlength(candidate) > width:
            lines.append(current)
            current = token
        else:
            current = candidate
    return lines + ([current] if current else [])


def hook_card(destination, template_id, title, description, options=None):
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    image = Image.new('RGBA', (1080, 1920))
    shadow = Image.new('RGBA', image.size)
    ImageDraw.Draw(shadow).rounded_rectangle((53, 1232, 897, 1605), radius=24, fill=(0,0,0,180))
    image.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(6)))
    draw = ImageDraw.Draw(image)
    options = options or {}
    accent = options.get('hook_accent', '#cf003b')
    draw.rounded_rectangle((45, 1224, 885, 1599), radius=24, fill=options.get('hook_background', '#ffffff'))
    draw.rounded_rectangle((45, 1132, 885, 1209), radius=18, fill=accent)
    title = str(title).upper().strip() or 'CERITA DI BALIKNYA'
    description = str(description).upper().strip()
    font_file = font_path(template_id)
    size = 90
    while size >= 38:
        font = ImageFont.truetype(str(font_file), size)
        lines = _fit_lines(title, font, 730)
        if len(lines) <= 2 and max(font.getlength(line) for line in lines) <= 730:
            break
        size -= 2
    y = 1283
    for line in lines[:2]:
        draw.text((105, y), line, font=font, fill=accent, anchor='lt')
        y += round(size*.88)
    body_size = 61
    while body_size >= 30:
        body_font = ImageFont.truetype(str(font_file), body_size)
        body = _fit_lines(description, body_font, 730)
        if len(body) <= 3 and y + len(body)*body_size*.86 <= 1555:
            break
        body_size -= 1
    for line in body[:3]:
        draw.text((105, y+8), line, font=body_font, fill=options.get('hook_text_color', '#111111'), anchor='lt')
        y += round(body_size*.86)
    image.save(destination)


def _ass_time(value):
    centiseconds = round(max(0, value)*100)
    hours, remainder = divmod(centiseconds, 360000)
    minutes, remainder = divmod(remainder, 6000)
    seconds, remainder = divmod(remainder, 100)
    return f'{hours}:{minutes:02d}:{seconds:02d}.{remainder:02d}'


def _ass_safe(text):
    return str(text).replace('\\', '').replace('{', '').replace('}', '').replace('\n', ' ')


def _ass_header():
    return '''[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Word,Bebas Neue,94,&H00FFFFFF,&H00FFFFFF,&H00000000,&H90000000,0,0,0,0,100,100,0,0,1,4,3,5,40,40,0,1
Style: Strip,Bebas Neue,44,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,5,0,0,0,1
Style: CTA,Bebas Neue,66,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,2,2,5,30,30,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''


def _filter_path(path):
    return str(Path(path).resolve()).replace('\\', '/').replace(':', '\\:').replace("'", "'\\''")


def _visual_segments(segments, destination, spec, ffmpeg, runner=None):
    command = [str(ffmpeg), '-y', '-hide_banner', '-loglevel', 'error', '-filter_complex_threads', '1']
    filters, joins = [], []
    total = 0
    for i, segment in enumerate(segments):
        length = segment['end_seconds']-segment['start_seconds']
        total += length
        if segment.get('is_image'):
            command += ['-loop', '1', '-t', str(length), '-i', segment['path']]
        else:
            command += ['-ss', str(segment['start_seconds']), '-t', str(length), '-i', segment['path']]
        motion = ''
        if 'available_seconds' in segment:
            frames = max(2, round(length*30))
            motion = f",zoompan=z='1+0.06*on/{frames-1}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s=1080x1920:fps=30"
        filters.append(f'[{i}:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30{motion},trim=duration={length},setpts=PTS-STARTPTS[v{i}]')
        joins.append(f'[v{i}]')
    filters.append(''.join(joins) + f'concat=n={len(segments)}:v=1:a=0[out]')
    command += ['-filter_complex', ';'.join(filters), '-map', '[out]', '-an', '-c:v', 'libx264',
                '-preset', 'fast', '-crf', '18', '-threads', '2', '-pix_fmt', 'yuv420p',
                '-t', str(total), '-movflags', '+faststart', str(destination)]
    runner(command, total) if runner else _run(command, timeout=max(600, total*15))


def render_layout(input_path, output_path, template_id, campaign=None, ffmpeg_path='ffmpeg',
                  runner=None, story_duration=None, title='', highlight=None):
    spec = RUANG_TEMPLATES[template_id]
    campaign, highlight = campaign or {}, highlight or {}
    options = style_options(campaign)
    source = probe_media(input_path, ffmpeg_path)
    story = source['duration'] if story_duration is None else float(story_duration)
    if not 0 < story <= source['duration'] + .05:
        raise EditingValidationError('Durasi cerita tidak valid.')
    endcard = endcard_settings(campaign)
    remaining = max(0, source['duration']-story)
    has_cta = bool(endcard['path']) and remaining > .1
    if endcard['required'] and not has_cta:
        raise EditingValidationError('CTA/penutup wajib campaign belum tersedia dalam video.')
    cta_duration = min(remaining, float(endcard['duration_seconds'])) if has_cta else 0
    minimum_cta = float(options.get('cta_min_seconds', 0)) if has_cta else 0
    if not math.isfinite(minimum_cta) or minimum_cta < 0:
        raise EditingValidationError('Batas durasi CTA tidak valid.')
    if has_cta and cta_duration < minimum_cta-.1:
        raise EditingValidationError(f'Footage CTA harus memenuhi minimum campaign {minimum_cta:g} detik.')
    intro = spec['intro_seconds']
    total = source['duration'] + intro
    maximum = float(campaign.get('brief', {}).get('durasi_max') or 180)
    if total > maximum + .15:
        raise EditingValidationError('Hook, cerita dan CTA melebihi durasi maksimum campaign.')
    assets = checked_broll(campaign, ffmpeg_path)
    opener = next((asset for asset in assets if asset['opener']), assets[0])
    if opener['available_seconds'] + .05 < intro:
        raise EditingValidationError('B-roll pembuka harus tersedia selama 5,2 detik.')
    shots = broll_plan(campaign, story, template_id, ffmpeg_path, highlight.get('editing_cues'))
    segments = [{**opener, 'end_seconds': opener['start_seconds']+intro}]
    cursor = 0
    for shot in shots:
        at = shot['at_seconds']
        if at > cursor:
            segments.append({'path': str(input_path), 'start_seconds': cursor, 'end_seconds': at})
        segments.append({**shot, 'end_seconds': shot['start_seconds'] + shot['duration_seconds']})
        cursor = at + shot['duration_seconds']
    if cursor < source['duration']:
        segments.append({'path': str(input_path), 'start_seconds': cursor, 'end_seconds': source['duration']})
    cta_at = total - cta_duration if has_cta else None
    cta_text = options.get('cta_text', '') if has_cta else ''
    with tempfile.TemporaryDirectory(prefix='ssr-ruang-') as directory:
        root = Path(directory)
        visual, card, overlays = root/'visual.mp4', root/'hook.png', root/'overlays.ass'
        _visual_segments(segments, visual, spec, ffmpeg_path, runner)
        hook_card(card, template_id, options.get('hook_title') or highlight.get('hook_title') or title,
                  options.get('hook_description') or highlight.get('hook_description') or title, options)
        strip = options.get('hook_strip', 'LIKE, COMMENT & FOLLOW')
        strip = (' ' + _ass_safe(strip).upper() + ' |')*6
        content = _ass_header()
        content += f'Dialogue: 1,0:00:00.00,{_ass_time(intro)},Strip,,0,0,0,,{{\\clip(45,1132,885,1209)\\move(960,1170,-200,1170)\\fad(100,150)}}{strip}\n'
        if cta_text:
            content += f'Dialogue: 1,{_ass_time(cta_at)},{_ass_time(total)},CTA,,0,0,0,,{{\\pos(540,338)}}“{_ass_safe(cta_text).upper()}”\n'
        overlays.write_text(content, encoding='utf-8')
        fonts = font_path(template_id).parent
        command = [str(ffmpeg_path), '-y', '-hide_banner', '-loglevel', 'error', '-filter_complex_threads', '1',
                   '-i', str(visual), '-i', str(input_path), '-i', str(card)]
        chain = f'[0:v]vignette=PI/4.7,eq=contrast=1.06:saturation=1.04[graded];[2:v]loop=loop={round(intro*30)}:size=1:start=0,setpts=N/(30*TB),format=rgba,fade=t=in:st=0:d=0.1:alpha=1,fade=t=out:st={intro-.15}:d=0.15:alpha=1[card];[graded][card]overlay=0:0:enable=\'lt(t,{intro})\'[hooked]'
        logo = options.get('cta_logo_path') if has_cta else None
        label = 'hooked'
        if logo:
            path = Path(logo)
            if not path.is_file() or (options.get('cta_logo_sha256') and file_sha256(path) != options['cta_logo_sha256']):
                raise EditingValidationError('Logo CTA hilang atau berubah.')
            command += ['-i', str(path)]
            chain += f';[3:v]format=rgba,scale=710:220:force_original_aspect_ratio=decrease,pad=710:220:(ow-iw)/2:(oh-ih)/2:color=0x00000000[logo];[hooked][logo]overlay=185:402:enable=\'gte(t,{cta_at})\'[branded]'
            label = 'branded'
        if cta_text:
            chain += f';[{label}]drawbox=x=0:y=0:w=iw:h=ih:color=0xcf003b@0.16:t=fill:enable=\'between(t,{cta_at},{cta_at+.1})\'[flash]'
            label = 'flash'
        chain += f";[{label}]subtitles='{_filter_path(overlays)}':fontsdir='{_filter_path(fonts)}',format=yuv420p[out]"
        audio_label = 'audio'
        if source['has_audio']:
            chain += f';[1:a]adelay={round(intro*1000)}:all=1,apad,atrim=duration={total}[voice]'
            sfx = options.get('cta_sfx_path')
            if sfx and has_cta:
                sfx_path = Path(sfx)
                if not sfx_path.is_file() or (options.get('cta_sfx_sha256') and file_sha256(sfx_path) != options['cta_sfx_sha256']):
                    raise EditingValidationError('SFX CTA hilang atau berubah.')
                sfx_index = 4 if logo else 3
                command += ['-i', str(sfx_path)]
                chain += f';[{sfx_index}:a]volume=0.24,adelay={round(cta_at*1000)}:all=1[sfx];[voice][sfx]amix=inputs=2:duration=first:normalize=0,alimiter=limit=.95:level=0[audio]'
            else:
                audio_label = 'voice'
        command += ['-filter_complex', chain, '-map', '[out]']
        if source['has_audio']:
            command += ['-map', '['+audio_label+']', '-c:a', 'aac', '-b:a', '192k']
        command += ['-c:v', 'libx264', '-preset', 'fast', '-crf', '18', '-threads', '2', '-t', str(total),
                    '-movflags', '+faststart', str(output_path)]
        runner(command, total) if runner else _run(command, timeout=max(600, total*15))
    actual = probe_media(output_path, ffmpeg_path)
    validate_render_canvas(actual, spec, "Template Ruang")
    if abs(actual['duration']-total) > .15 or actual['has_audio'] != source['has_audio']:
        raise EditingValidationError('Durasi atau audio template Ruang tidak sesuai rencana.')
    return {'template_id': template_id, 'version': RUANG_RENDER_VERSION, 'intro_seconds': intro, 'story_duration': story,
        'cta_present': has_cta, 'cta_required': endcard['required'],
        'cta_at_seconds': cta_at, 'cta_duration_seconds': cta_duration,
        'canvas': {key: spec[key] for key in ('width','height','fps')}, 'broll': shots,
        'opener': opener, 'broll_policy': 'sparse_unique_visual_matches_only',
        'story_broll_ratio': sum(shot['duration_seconds'] for shot in shots) / story,
        'source_audio_preserved': True, 'font_sha256': file_sha256(font_path(template_id)),
        'hook_title': options.get('hook_title') or highlight.get('hook_title') or title,
        'hook_description': options.get('hook_description') or highlight.get('hook_description') or title,
        'hook_style': {key: options.get(key, default) for key,default in
            [('hook_accent','#cf003b'),('hook_background','#ffffff'),('hook_text_color','#111111')]},
        'cta_text': cta_text}


def render_captions(input_path, output_path, transcript, template_id, ffmpeg_path='ffmpeg', time_offset=0, runner=None):
    from .reference_templates import timed_words
    info = probe_media(input_path, ffmpeg_path)
    words = timed_words(transcript, info['duration'], time_offset)
    with tempfile.TemporaryDirectory(prefix='ssr-ruang-words-') as directory:
        ass = Path(directory)/'words.ass'
        content = _ass_header()
        for word in words:
            text = ''.join(c for c in word['text'] if not unicodedata.category(c).startswith('P')).upper()
            text = _ass_safe(text)
            if text:
                content += f'Dialogue: 2,{_ass_time(word["start"])},{_ass_time(word["end"])},Word,,0,0,0,,{{\\pos(540,1120)\\fscx80\\fscy80\\t(0,90,\\fscx100\\fscy100)}}{text}\n'
        ass.write_text(content, encoding='utf-8')
        command = [str(ffmpeg_path), '-y', '-hide_banner', '-loglevel', 'error', '-i', str(input_path),
            '-vf', f"subtitles='{_filter_path(ass)}':fontsdir='{_filter_path(font_path(template_id).parent)}'",
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '18', '-threads', '2', '-pix_fmt', 'yuv420p',
            '-c:a', 'copy', '-t', str(info['duration']), '-movflags', '+faststart', str(output_path)]
        runner(command, info['duration']) if runner else _run(command, timeout=max(600, info['duration']*15))
    actual = probe_media(output_path, ffmpeg_path)
    validate_render_canvas(actual, info, "Subtitle Ruang")
    if abs(actual['duration']-info['duration']) > .15:
        raise EditingValidationError('Subtitle mengubah durasi template Ruang.')
    return actual
