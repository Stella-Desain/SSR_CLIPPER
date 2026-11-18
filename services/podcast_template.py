"""Measured square podcast layout and deterministic word captions.

Caption bitmaps keep the bundled font and subtle fixed highlight identical on
machines with different system fonts. No user media, network, or AI at import.
"""
from __future__ import annotations

import math
from pathlib import Path
import tempfile
import unicodedata

from .editing import EditingValidationError, _run, probe_media, validate_render_canvas

WIDTH = HEIGHT = 720
FPS = 30
APERTURE = (10, 5, 710, 713)  # Exclusive right/bottom bounds measured at 720px.
CORNER_RADIUS = 50
CAPTION_CENTER = (360, 416)
CAP_HEIGHT = 26
FONT_FILE = "PodcastBlack.ttf"


def font_path():
    from utils.helpers import get_bundle_dir
    path = get_bundle_dir() / "assets" / "fonts" / FONT_FILE
    if not path.is_file():
        raise EditingValidationError("Font template Podcast Kotak tidak tersedia. Periksa file aplikasi.")
    return path


def _field(item, key, default=None):
    return item.get(key, default) if isinstance(item, dict) else getattr(item, key, default)


def caption_words(transcript, time_offset=0, duration=None):
    """Use actual word timestamps; never guess equal word lengths from a sentence."""
    words = _field(transcript, "words") or []
    if not words:
        for segment in _field(transcript, "segments", []) or []:
            words.extend(_field(segment, "words", []) or [])
    if not words:
        raise EditingValidationError("Template Podcast Kotak membutuhkan waktu per kata. Pilih model Caption Maker yang mendukung word timestamps.")
    result = []
    for word in words:
        text = str(_field(word, "word", _field(word, "text", ""))).strip().upper()
        while text and unicodedata.category(text[0]).startswith("P"):
            text = text[1:]
        while text and unicodedata.category(text[-1]).startswith("P"):
            text = text[:-1]
        try:
            start = float(_field(word, "start")) + time_offset
            end = float(_field(word, "end")) + time_offset
        except (TypeError, ValueError):
            raise EditingValidationError("Waktu subtitle per kata tidak valid.") from None
        if not math.isfinite(start) or not math.isfinite(end):
            raise EditingValidationError("Waktu subtitle per kata tidak valid.")
        if not text or end <= start or end <= 0 or (duration is not None and start >= duration):
            continue
        result.append({"text": text.replace("\n", " "), "start": max(0, start),
                       "end": min(end, duration) if duration is not None else end})
    result.sort(key=lambda word: word["start"])
    # Timestamp overlap must not create two captions at once.
    for index in range(len(result)-1):
        result[index]["end"] = min(result[index]["end"], result[index+1]["start"])
    result = [word for word in result if word["end"] > word["start"]]
    if not result:
        raise EditingValidationError("Tidak ada subtitle per kata di dalam durasi clip.")
    return result


def draw_caption(text):
    """RGBA caption at reference coordinates, rendered above native resolution."""
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    import numpy as np
    font = ImageFont.truetype(str(font_path()), 120)
    box = font.getbbox(text, anchor="ls")
    glyph = Image.new("L", (max(1, box[2]-box[0]+4), max(1, box[3]-box[1]+4)))
    ImageDraw.Draw(glyph).text((2-box[0], 2-box[1]), text, font=font, fill=255, anchor="ls")
    ink_box = glyph.getbbox()
    if ink_box is None:
        raise EditingValidationError("Teks subtitle tidak memiliki karakter yang dapat ditampilkan.")
    glyph = glyph.crop(ink_box)
    # One font scale/baseline retains natural overshoot (S/O are taller than K).
    # Horizontal scale matches KESUKSESAN's measured 201px; long tokens fit.
    reference_box = font.getbbox("KESUKSESAN", anchor="ls")
    reference_width = reference_box[2]-reference_box[0]
    vertical_scale = CAP_HEIGHT / (reference_box[3]-reference_box[1])
    target_width = max(1, round(glyph.width * 201 / reference_width))
    factor = min(1, 656 / target_width)
    target_width = max(1, round(target_width * factor))
    target_height = max(1, round(glyph.height * vertical_scale * factor))
    glyph = glyph.resize((target_width*3, target_height*3), Image.Resampling.LANCZOS)
    mask = Image.new("L", (WIDTH*3, HEIGHT*3))
    left = round((CAPTION_CENTER[0] - target_width/2)*3)
    top = round((428.4 + (box[1]+ink_box[1]-2) * vertical_scale * factor)*3)
    mask.paste(glyph, (left, top))
    mask = mask.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
    shadow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    shadow.putalpha(mask.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(.6)))
    yy, xx = np.mgrid[0:HEIGHT, 0:WIDTH]
    glint = np.exp(-.5 * (((xx-332)/12)**2 + ((yy-409)/4)**2))
    color = np.empty((HEIGHT, WIDTH, 4), dtype=np.uint8)
    for channel, target in enumerate((118, 156, 172)):
        color[:, :, channel] = np.clip(252 + (target-252)*glint, 0, 255).astype(np.uint8)
    color[:, :, 3] = np.asarray(mask)
    return Image.alpha_composite(shadow, Image.fromarray(color))


def render_layout(input_path, output_path, ffmpeg_path="ffmpeg", runner=None):
    """Overlay a smooth black rounded aperture on a square, already framed video."""
    from PIL import Image, ImageDraw
    info = probe_media(input_path, ffmpeg_path)
    if (info["width"], info["height"]) != (WIDTH, HEIGHT):
        raise EditingValidationError("Podcast Kotak membutuhkan framing 720 × 720 sebelum bingkai dipasang.")
    with tempfile.TemporaryDirectory(prefix="ssr-podcast-mask-") as directory:
        mask_path = Path(directory) / "border.png"
        mask = Image.new("RGBA", (WIDTH*3, HEIGHT*3), (0, 0, 0, 255))
        box = (APERTURE[0]*3, APERTURE[1]*3, APERTURE[2]*3-1, APERTURE[3]*3-1)
        ImageDraw.Draw(mask).rounded_rectangle(box, radius=CORNER_RADIUS*3, fill=(0, 0, 0, 0))
        mask.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS).save(mask_path)
        command = [str(ffmpeg_path), "-y", "-hide_banner", "-loglevel", "error", "-i", str(input_path), "-i", str(mask_path),
            "-filter_complex", "[0:v]setsar=1,fps=30[v];[v][1:v]overlay=0:0:format=auto,format=yuv420p[out]",
            "-map", "[out]", "-map", "0:a?", "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "copy", "-t", str(info["duration"]), "-movflags", "+faststart", str(output_path)]
        (runner(command, info["duration"]) if runner else _run(command))
    actual = probe_media(output_path, ffmpeg_path)
    validate_render_canvas(actual, info, "Bingkai Podcast Kotak")
    return actual


def render_word_captions(input_path, output_path, transcript, ffmpeg_path="ffmpeg", time_offset=0, runner=None):
    info = probe_media(input_path, ffmpeg_path)
    if (info["width"], info["height"]) != (WIDTH, HEIGHT):
        raise EditingValidationError("Ukuran video tidak sesuai template Podcast Kotak.")
    words = caption_words(transcript, time_offset, info["duration"])
    from PIL import Image
    with tempfile.TemporaryDirectory(prefix="ssr-podcast-captions-") as directory:
        root = Path(directory)
        Image.new("RGBA", (WIDTH, HEIGHT)).save(root / "blank.png")
        lines = ["ffconcat version 1.0"]
        def add(name, duration):
            if duration > .00001:
                lines.extend([f"file '{name}'", "option framerate 1000", f"duration {duration:.6f}"])
        cursor, bitmaps = 0.0, {}
        for word in words:
            add("blank.png", word["start"]-cursor)
            name = bitmaps.get(word["text"])
            if name is None:
                name = f"word-{len(bitmaps):04d}.png"
                draw_caption(word["text"]).save(root / name)
                bitmaps[word["text"]] = name
            add(name, word["end"]-word["start"])
            cursor = word["end"]
        add("blank.png", max(0, info["duration"]-cursor))
        lines.extend(["file 'blank.png'", "option framerate 1000"])
        timeline = root / "captions.ffconcat"
        timeline.write_text("\n".join(lines)+"\n", encoding="utf-8")
        command = [str(ffmpeg_path), "-y", "-hide_banner", "-loglevel", "error", "-i", str(input_path),
            "-f", "concat", "-safe", "0", "-i", str(timeline), "-filter_complex",
            "[1:v]fps=30,format=rgba[sub];[0:v][sub]overlay=eof_action=pass:format=auto,format=yuv420p[out]",
            "-map", "[out]", "-map", "0:a?", "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "copy", "-t", str(info["duration"]), "-movflags", "+faststart", str(output_path)]
        (runner(command, info["duration"]) if runner else _run(command))
    actual = probe_media(output_path, ffmpeg_path)
    validate_render_canvas(actual, info, "Subtitle Podcast Kotak")
    if abs(actual["duration"] - info["duration"]) > .1:
        raise EditingValidationError("Durasi berubah saat subtitle dirender.")
    return actual
