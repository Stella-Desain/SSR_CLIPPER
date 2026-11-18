"""Two source-independent edits measured from the user's Timothy references.

User speech and timing are retained. B-roll comes from immutable campaign assets,
never from the burned-in reference video or its soundtrack.
"""
from __future__ import annotations

import math
from pathlib import Path
import tempfile
import unicodedata

from .editing import EditingValidationError, _run, probe_media, file_sha256, render_composition, validate_render_canvas
from .ruang_templates import RUANG_TEMPLATES

REFERENCE_TEMPLATES = {
    "timothy_focus": {"width": 1440, "height": 1080, "fps": 30, "anchor_x": .34,
        "name": "Tegas 4:3", "font": "RobotoVariable.ttf"},
    "timothy_cinematic": {"width": 1920, "height": 1080, "fps": 30, "anchor_x": .5,
        "name": "Sinematik 16:9", "font": "PodcastBlack.ttf"},
}
REFERENCE_TEMPLATES.update(RUANG_TEMPLATES)
KEY_WORDS = {"pemenang", "sukses", "uang", "tanggung", "jawab", "laki-laki", "lakukan", "juara", "berani", "gagal", "menang"}
FILLER_WORDS = {"ya", "iya", "dan", "lu", "lo", "gitu", "itu", "jadi", "lah", "deh", "kan", "oke", "nah", "eh"}


def template_spec(template_id):
    if template_id not in REFERENCE_TEMPLATES:
        raise EditingValidationError("Template referensi tidak dikenal.")
    return REFERENCE_TEMPLATES[template_id]


def _field(item, key, default=None):
    return item.get(key, default) if isinstance(item, dict) else getattr(item, key, default)


def timed_words(transcript, duration, time_offset=0):
    if not math.isfinite(duration) or duration <= 0 or not math.isfinite(time_offset):
        raise EditingValidationError("Durasi atau offset subtitle tidak valid.")
    words = list(_field(transcript, "words") or [])
    if not words:
        for segment in _field(transcript, "segments", []) or []:
            words.extend(_field(segment, "words", []) or [])
    if not words:
        raise EditingValidationError("Template ini memerlukan waktu subtitle per kata. Pilih Caption Maker yang mendukung word timestamps.")
    result = []
    for word in words:
        text = " ".join(str(_field(word, "word", _field(word, "text", ""))).split())
        try:
            start, end = float(_field(word, "start")) + time_offset, float(_field(word, "end")) + time_offset
        except (TypeError, ValueError):
            raise EditingValidationError("Waktu subtitle per kata tidak valid.") from None
        if not math.isfinite(start) or not math.isfinite(end):
            raise EditingValidationError("Waktu subtitle per kata tidak valid.")
        if text and end > start and end > 0 and start < duration:
            result.append({"text": text, "start": max(0, start), "end": min(end, duration)})
    result.sort(key=lambda word: word["start"])
    for index in range(len(result)-1):
        result[index]["end"] = min(result[index]["end"], result[index+1]["start"])
    result = [word for word in result if word["end"] > word["start"]]
    if not result:
        raise EditingValidationError("Tidak ada subtitle per kata di dalam durasi clip.")
    return result


def caption_phrases(transcript, duration, time_offset=0, emphasis_breaks=False):
    """Short speech phrases, bounded by pauses and actual word timestamps."""
    words = timed_words(transcript, duration, time_offset)
    phrases, current = [], []
    for word_index, word in enumerate(words):
        if current and (word["start"]-current[-1]["end"] > .22
                or word["end"]-current[0]["start"] > 1.65 or len(current) >= 5
                or len(" ".join(item["text"] for item in current+[word])) > 32):
            phrases.append({"text": " ".join(item["text"] for item in current), "start": current[0]["start"], "end": current[-1]["end"]})
            current = []
        current.append(word)
        # Keep the emphasized word at the end of its own phrase. Otherwise a
        # later filler such as "ya dan lu" could become the oversized takeaway.
        tail = _clean(" ".join(item["text"] for item in current)).split()
        next_token = _clean(words[word_index+1]["text"]) if word_index+1 < len(words) else ""
        follows_pair = tail and ((tail[-1] == "tanggung" and next_token == "jawab")
            or (tail[-1] == "lakukan" and next_token in {"sekarang", "aja", "sesuatu", "sendiri", "itu", "ini", "semua"}))
        completes_pair = len(tail) >= 2 and tail[-2] == "lakukan"
        emphasis_end = emphasis_breaks and tail and (completes_pair or (tail[-1] in KEY_WORDS and not follows_pair))
        if word["text"].rstrip().endswith((".", "?", "!", ";")) or emphasis_end:
            phrases.append({"text": " ".join(item["text"] for item in current), "start": current[0]["start"], "end": current[-1]["end"]})
            current = []
    if current:
        phrases.append({"text": " ".join(item["text"] for item in current), "start": current[0]["start"], "end": current[-1]["end"]})
    return phrases


def font_path(template_id):
    from utils.helpers import get_bundle_dir
    path = get_bundle_dir() / "assets" / "fonts" / template_spec(template_id)["font"]
    if not path.is_file():
        raise EditingValidationError("Font template tidak tersedia. Periksa file aplikasi.")
    return path


def _clean(text, upper=False):
    text = "".join(char for char in text if not unicodedata.category(char).startswith("P") or char in {"-", "'"})
    text = " ".join(text.replace(" -", "-").split())
    return text.upper() if upper else text.lower()


def _lines(text, font, maximum):
    lines, line = [], ""
    for word in text.split():
        proposed = (line+" "+word).strip()
        if line and font.getlength(proposed) > maximum:
            lines.append(line)
            line = word
        else:
            line = proposed
    if line:
        lines.append(line)
    return lines


def caption_emphasis(text, last=False):
    tokens = set(_clean(text).split())
    return bool(tokens & KEY_WORDS) or bool(last and tokens - FILLER_WORDS)


def draw_caption(text, template_id, *, emphasize=False, last=False, entry=1):
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    spec = template_spec(template_id)
    width, height = spec["width"], spec["height"]
    focus = template_id == "timothy_focus"
    text = _clean(text, focus)
    image = Image.new("RGBA", (width, height))
    if not text:
        return image
    family = font_path(template_id)
    size = 62 if focus else 66
    maximum = width * (.48 if focus else .86)
    font = ImageFont.truetype(str(family), size)
    lines = _lines(text, font, maximum)
    if focus:
        while max(font.getlength(line) for line in lines) > maximum and size > 28:
            size -= 2
            font = ImageFont.truetype(str(family), size)
            lines = _lines(text, font, maximum)
        top, center, gap = height*.245, width*.65, 64
        for line in lines:
            ImageDraw.Draw(image).text((center, top), line, font=font, anchor="mt", fill=(255,255,255,255),
                                      stroke_width=1, stroke_fill=(25,25,25,220))
            top += gap
        return image
    # Large takeaway below a smaller setup, following the reference hierarchy.
    pieces = text.split()
    if emphasize:
        main = " ".join(pieces[-2:])
        setup = " ".join(pieces[:-2])
        big_size = 140
        big = ImageFont.truetype(str(family), big_size)
        while big.getlength(main) > maximum and big_size > 40:
            big_size -= 3
            big = ImageFont.truetype(str(family), big_size)
        if setup:
            while font.getlength(setup) > maximum and size > 24:
                size -= 2
                font = ImageFont.truetype(str(family), size)
            ImageDraw.Draw(image).text((width*.5,height*.57),setup,font=font,anchor="mt",fill="white",stroke_width=2,stroke_fill=(0,0,0,180))
        accented = last or bool(set(main.split()) & {"laki-laki", "uang", "lakukan"})
        color = (226,101,25,255) if accented else (255,255,255,255)
        ImageDraw.Draw(image).text((width*.5,height*.64),main,font=big,anchor="mt",fill=color,stroke_width=1,stroke_fill=(0,0,0,160))
    else:
        for index, line in enumerate(lines):
            ImageDraw.Draw(image).text((width*.5,height*.78+index*76),line,font=font,anchor="mt",fill="white",stroke_width=2,stroke_fill=(0,0,0,180))
    if entry < 1:
        image = image.filter(ImageFilter.GaussianBlur(2.5*(1-entry)))
        image.putalpha(image.getchannel("A").point(lambda alpha: round(alpha*entry)))
    return image


def render_captions(input_path, output_path, transcript, template_id, ffmpeg_path="ffmpeg", time_offset=0, runner=None):
    if template_id in RUANG_TEMPLATES:
        from .ruang_templates import render_captions as render_ruang_captions
        return render_ruang_captions(input_path, output_path, transcript, template_id, ffmpeg_path, time_offset, runner)
    from PIL import Image
    spec = template_spec(template_id)
    info = probe_media(input_path, ffmpeg_path)
    if (info["width"],info["height"]) != (spec["width"],spec["height"]):
        raise EditingValidationError("Ukuran video tidak sesuai template referensi.")
    phrases = caption_phrases(transcript, info["duration"], time_offset, emphasis_breaks=template_id == "timothy_cinematic")
    with tempfile.TemporaryDirectory(prefix="ssr-reference-captions-") as directory:
        root = Path(directory)
        Image.new("RGBA",(spec["width"],spec["height"])).save(root/"blank.png")
        lines, cursor = ["ffconcat version 1.0"], 0.0
        def add(name, length):
            if length > .00001:
                lines.extend([f"file '{name}'", "option framerate 1000", f"duration {length:.6f}"])
        for index, phrase in enumerate(phrases):
            add("blank.png",phrase["start"]-cursor)
            emphasized = caption_emphasis(phrase["text"], last=index == len(phrases)-1)
            length = phrase["end"]-phrase["start"]
            name = f"caption-{index:04d}.png"
            draw_caption(phrase["text"],template_id,emphasize=emphasized,last=index==len(phrases)-1).save(root/name)
            if template_id == "timothy_cinematic" and length > .2:
                for frame, opacity in ((0,.45),(1,.78)):
                    entry_name=f"caption-{index:04d}-entry-{frame}.png"
                    draw_caption(phrase["text"],template_id,emphasize=emphasized,last=index==len(phrases)-1,entry=opacity).save(root/entry_name)
                    add(entry_name,.05)
                length -= .1
            add(name,length)
            cursor = phrase["end"]
        add("blank.png",max(0,info["duration"]-cursor))
        lines.extend(["file 'blank.png'", "option framerate 1000"])
        timeline=root/"captions.ffconcat"
        timeline.write_text("\n".join(lines)+"\n",encoding="utf-8")
        command=[str(ffmpeg_path),"-y","-hide_banner","-loglevel","error","-i",str(input_path),
            "-f","concat","-safe","0","-i",str(timeline),"-filter_complex",
            f"[1:v]fps={spec['fps']},format=rgba[sub];[0:v][sub]overlay=eof_action=pass:format=auto,format=yuv420p[out]",
            "-map","[out]","-map","0:a?","-c:v","libx264","-preset","fast","-crf","18","-c:a","copy",
            "-t",str(info["duration"]),"-movflags","+faststart",str(output_path)]
        runner(command,info["duration"]) if runner else _run(command)
    actual=probe_media(output_path,ffmpeg_path)
    validate_render_canvas(actual, info, "Subtitle referensi")
    if abs(actual["duration"]-info["duration"])>.1:
        raise EditingValidationError("Durasi berubah saat subtitle template dirender.")
    return actual


def broll_assets(campaign):
    return [asset for asset in campaign.get("assets",[]) if asset.get("role")=="broll"]


def broll_plan(campaign, duration, ffmpeg_path="ffmpeg"):
    if not math.isfinite(duration) or duration <= 0:
        raise EditingValidationError("Durasi B-roll tidak valid.")
    assets=broll_assets(campaign)
    if not assets:
        raise EditingValidationError("Template Sinematik 16:9 memerlukan aset B-roll. Tambahkan video/gambar dengan peran B-roll di campaign.")
    validated=[]
    for asset in assets:
        path=Path(asset["path"])
        if not path.is_file() or (asset.get("sha256") and file_sha256(path)!=asset["sha256"]):
            raise EditingValidationError("Aset B-roll berubah atau tidak tersedia: "+asset.get("name",path.name))
        info=probe_media(path,ffmpeg_path)
        if not info["has_video"]:
            raise EditingValidationError("B-roll harus berupa video atau gambar.")
        still=path.suffix.lower() in {".png",".jpg",".jpeg",".webp"}
        start=float(asset.get("start_seconds",0))
        end=float(asset.get("end_seconds") or info["duration"] or start+3)
        if not math.isfinite(start) or not math.isfinite(end) or start<0 or end<=start or (not still and end>info["duration"]+.05):
            raise EditingValidationError("Rentang aset B-roll tidak valid.")
        validated.append({"path":str(path),"asset_id":asset.get("id"),"sha256":asset.get("sha256") or file_sha256(path),
                          "start_seconds":start,"available_seconds":end-start,"is_image":still})
    plan, cursor, index=[],min(3.0,duration),0
    # Alternate dialogue view and supporting footage while retaining its audio.
    while cursor<duration-.08:
        asset=validated[index%len(validated)]
        length=min(3.0,duration-cursor,asset["available_seconds"])
        if length<.08:
            raise EditingValidationError("Aset B-roll terlalu singkat. Pilih rentang minimal 0,08 detik.")
        plan.append({**asset,"at_seconds":cursor,"duration_seconds":length})
        cursor+=length+2.0
        index+=1
    return plan


def render_layout(input_path, output_path, template_id, campaign=None, ffmpeg_path="ffmpeg", runner=None, story_duration=None, title="", highlight=None):
    if template_id in RUANG_TEMPLATES:
        from .ruang_templates import render_layout as render_ruang_layout
        return render_ruang_layout(input_path, output_path, template_id, campaign, ffmpeg_path,
                                  runner, story_duration, title, highlight)
    spec=template_spec(template_id)
    info=probe_media(input_path,ffmpeg_path)
    if (info["width"],info["height"])!=(spec["width"],spec["height"]):
        raise EditingValidationError("Ukuran framing tidak sesuai template referensi.")
    with tempfile.TemporaryDirectory(prefix="ssr-reference-layout-") as directory:
        root=Path(directory)
        visual=Path(input_path)
        shots=[]
        if template_id=="timothy_cinematic":
            # Campaign endcards and inserts keep their own timeline and pixels.
            story_length = info["duration"] if story_duration is None else min(info["duration"], story_duration)
            shots=broll_plan(campaign or {},story_length,ffmpeg_path)
            segments, cursor=[],0.0
            for shot in shots:
                if shot["at_seconds"]>cursor:
                    segments.append({"path":str(input_path),"start_seconds":cursor,"end_seconds":shot["at_seconds"]})
                segments.append({"path":shot["path"],"start_seconds":shot["start_seconds"],
                    "end_seconds":shot["start_seconds"]+shot["duration_seconds"],"is_image":shot["is_image"]})
                cursor=shot["at_seconds"]+shot["duration_seconds"]
            if cursor<info["duration"]:
                segments.append({"path":str(input_path),"start_seconds":cursor,"end_seconds":info["duration"]})
            visual=root/"broll.mp4"
            render_composition(segments,visual,ffmpeg_path,width=spec["width"],height=spec["height"])
            # Composition audio is deliberately discarded below. Only source
            # speech belongs to this clip, irrespective of B-roll soundtracks.
            filter_text="eq=brightness=-0.05:saturation=0.85:contrast=1.06,colorbalance=rs=0.025:bs=-0.025,vignette=PI/5"
            command=[str(ffmpeg_path),"-y","-hide_banner","-loglevel","error","-i",str(visual),"-i",str(input_path),
                "-vf",filter_text,"-map","0:v","-map","1:a?","-c:v","libx264","-preset","fast","-crf","18",
                "-c:a","copy","-t",str(info["duration"]),"-movflags","+faststart",str(output_path)]
        else:
            from PIL import Image
            import numpy as np
            yy,xx=np.mgrid[0:spec["height"],0:spec["width"]]
            right=np.clip((xx/spec["width"]-.54)/.46,0,1)**1.6*.65
            edge=np.clip(((xx/spec["width"]-.35)**2+(yy/spec["height"]-.48)**2)/.62,0,1)*.22
            mask=np.zeros((spec["height"],spec["width"],4),dtype=np.uint8)
            mask[:,:,3]=np.clip((right+edge)*255,0,210).astype(np.uint8)
            overlay=root/"vignette.png"
            Image.fromarray(mask).save(overlay)
            command=[str(ffmpeg_path),"-y","-hide_banner","-loglevel","error","-i",str(input_path),"-i",str(overlay),
                "-filter_complex","[0:v][1:v]overlay=0:0:format=auto,format=yuv420p[out]","-map","[out]","-map","0:a?",
                "-c:v","libx264","-preset","fast","-crf","18","-c:a","copy","-t",str(info["duration"]),
                "-movflags","+faststart",str(output_path)]
        runner(command,info["duration"]) if runner else _run(command)
    actual=probe_media(output_path,ffmpeg_path)
    validate_render_canvas(actual, spec, "Template referensi")
    if abs(actual["duration"]-info["duration"])>.1 or actual["has_audio"]!=info["has_audio"]:
        raise EditingValidationError("Durasi atau audio berubah saat template referensi dirender.")
    return {"template_id":template_id,"version":1,"canvas":{key:spec[key] for key in ("width","height","fps")},
            "broll":shots,"source_audio_preserved":True,"font_sha256":file_sha256(font_path(template_id))}
