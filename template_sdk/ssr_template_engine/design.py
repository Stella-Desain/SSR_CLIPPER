"""Portable native designs and FFmpeg compiler, independent of the editor UI.

The source duration, never sample/preview duration, owns the render timeline.
No network, GUI, Python dependencies or expression/script execution is needed.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile
import time
import uuid
import zipfile

from .package import TemplateError, _safe_name, sha256, manifest_digest

FORMAT = "ssr-design-template"
DesignError = TemplateError
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
FONT_EXTENSIONS = {".ttf", ".otf"}


def _font_families(path):
    """Read SFNT family names without requiring a font library on consumers."""
    data = Path(path).read_bytes()
    try:
        if data[:4] not in {b"\x00\x01\x00\x00", b"OTTO", b"true"}:
            raise ValueError("SFNT signature")
        count = struct.unpack_from(">H", data, 4)[0]
        name_data = None
        for index in range(count):
            tag, _, offset, length = struct.unpack_from(">4sIII", data, 12 + 16*index)
            if tag == b"name":
                name_data = data[offset:offset+length]
                break
        if not name_data:
            raise ValueError("name table")
        _, count, strings = struct.unpack_from(">HHH", name_data, 0)
        families = set()
        for index in range(count):
            platform, _, _, name_id, length, offset = struct.unpack_from(">HHHHHH", name_data, 6 + 12*index)
            if name_id not in {1, 16}:
                continue
            raw = name_data[strings+offset:strings+offset+length]
            family = raw.decode("utf-16-be" if platform in {0, 3} else "mac_roman").strip()
            if family:
                families.add(family.casefold())
        if not families:
            raise ValueError("family names")
        return families
    except (ValueError, struct.error, UnicodeError) as exc:
        raise DesignError("Font paket rusak atau tidak didukung: " + Path(path).name) from exc


def _number(value, name, minimum=0, maximum=4096):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise DesignError(f"{name} harus angka antara {minimum} dan {maximum}.")
    return float(value)


def _color(value, name):
    if not isinstance(value, str) or not re.fullmatch(r"#[a-fA-F0-9]{6}(?:[a-fA-F0-9]{2})?", value):
        raise DesignError(f"{name} harus warna #RRGGBB atau #RRGGBBAA.")
    return value.lower()


def new_design(name="Template baru", ratio="9:16", design_id=None):
    sizes = {"9:16": (1080, 1920), "1:1": (1080, 1080), "16:9": (1920, 1080)}
    if ratio not in sizes:
        raise DesignError("Pilih rasio 9:16, 1:1, atau 16:9.")
    width, height = sizes[ratio]
    return {"schema_version": 1, "id": design_id or "design-" + uuid.uuid4().hex[:16], "name": name,
        "canvas": {"width": width, "height": height, "fps": 30, "background": "#101820"},
        "layers": [{"id": "video", "name": "Video highlight", "type": "video", "x": 0, "y": 0,
            "width": width, "height": height, "rotation": 0, "visible": True, "locked": False,
            "fit": "cover", "framing": "center", "timing": {"mode": "full", "start": 0, "duration": 4}}],
        "assets": [], "audio": {"voice_volume": 1, "music_volume": .12, "ducking": True, "fade_in": .5, "fade_out": 1},
        "preview": {"video_path": "", "subtitle_path": "", "music_path": "", "title": "Judul clip", "duration": 30}}


def validate_design(model, asset_root=None):
    if not isinstance(model, dict) or model.get("schema_version") != 1:
        raise DesignError("Versi desain template belum didukung.")
    result = copy.deepcopy(model)
    if not re.fullmatch(r"[a-z][a-z0-9_-]{1,63}", str(result.get("id", ""))):
        raise DesignError("ID desain template tidak valid.")
    if not isinstance(result.get("name"), str) or not 1 <= len(result["name"].strip()) <= 120:
        raise DesignError("Nama template wajib diisi, maksimal 120 karakter.")
    canvas = result.get("canvas")
    if not isinstance(canvas, dict):
        raise DesignError("Kanvas desain belum tersedia.")
    for key in ("width", "height"):
        value = _number(canvas.get(key), "Kanvas " + key, 32, 4096)
        if not value.is_integer() or int(value) % 2:
            raise DesignError("Ukuran kanvas harus piksel genap.")
    _number(canvas.get("fps", 30), "FPS", 1, 60)
    canvas.setdefault("fps", 30)
    canvas["background"] = _color(canvas.get("background", "#101820"), "Latar kanvas")
    assets, seen_assets = result.get("assets", []), set()
    if not isinstance(assets, list) or len(assets) > 128:
        raise DesignError("Daftar aset template tidak valid (maksimal 128).")
    for asset in assets:
        if not isinstance(asset, dict) or not isinstance(asset.get("id"), str) or asset["id"] in seen_assets:
            raise DesignError("ID aset harus unik.")
        seen_assets.add(asset["id"])
        if asset.get("kind") not in {"image", "font"}:
            raise DesignError("Paket produksi hanya memuat gambar dan font; video dan musik contoh disimpan terpisah.")
        path = _safe_name(asset.get("path", ""))
        allowed = IMAGE_EXTENSIONS if asset["kind"] == "image" else FONT_EXTENSIONS
        if not path.startswith("assets/") or Path(path).suffix.lower() not in allowed:
            raise DesignError("Path aset template harus berupa gambar/font di assets/.")
        if asset_root is not None:
            target, root = (Path(asset_root) / path).resolve(), Path(asset_root).resolve()
            if not target.is_relative_to(root) or not target.is_file() or target.is_symlink():
                raise DesignError("Aset template tidak tersedia: " + str(asset.get("name") or path))
            if asset["kind"] == "font":
                families = _font_families(target)
                if asset.get("font_family") and asset["font_family"].casefold() not in families:
                    raise DesignError("Nama font aset tidak sesuai file font: " + asset["font_family"])
    result["assets"] = assets
    layers, seen, videos, subtitles = result.get("layers"), set(), 0, 0
    if not isinstance(layers, list) or not 1 <= len(layers) <= 64:
        raise DesignError("Desain memerlukan 1–64 layer.")
    for layer in layers:
        if not isinstance(layer, dict) or not isinstance(layer.get("id"), str) or layer["id"] in seen:
            raise DesignError("ID layer harus unik.")
        seen.add(layer["id"])
        kind = layer.get("type")
        if kind not in {"video", "subtitle", "text", "image", "rect"}:
            raise DesignError("Jenis layer belum didukung.")
        for key in ("x", "y"):
            _number(layer.get(key, 0), "Posisi " + key, -4096, 4096)
            layer.setdefault(key, 0)
        for key in ("width", "height"):
            _number(layer.get(key), "Ukuran " + key, 1, 8192)
        if layer.get("rotation", 0) != 0:
            raise DesignError("Rotasi belum tersedia pada renderer; gunakan 0°.")
        for key, default in (("visible", True), ("locked", False)):
            layer.setdefault(key, default)
            if not isinstance(layer[key], bool):
                raise DesignError("Status layer harus benar atau salah.")
        timing = layer.setdefault("timing", {"mode": "full", "start": 0, "duration": 4})
        if not isinstance(timing, dict) or timing.get("mode") not in {"full", "start", "end", "percent"}:
            raise DesignError("Waktu layer tidak valid.")
        limit = 100 if timing["mode"] == "percent" else 3600
        _number(timing.setdefault("start", 0), "Awal layer", 0, limit)
        _number(timing.setdefault("duration", 4), "Durasi layer", 0, limit)
        if kind == "video":
            videos += 1
            if timing["mode"] != "full" or not layer["visible"]:
                raise DesignError("Video highlight harus terlihat sepanjang clip.")
            if layer.setdefault("fit", "cover") not in {"cover", "contain"} or layer.setdefault("framing", "center") not in {"fit", "center"}:
                raise DesignError("Framing video tidak valid.")
        if kind in {"text", "subtitle"}:
            subtitles += kind == "subtitle"
            layer.setdefault("font_family", "Arial")
            if not isinstance(layer["font_family"], str) or not 1 <= len(layer["font_family"]) <= 128 or re.search(r"[,\r\n]", layer["font_family"]):
                raise DesignError("Nama font tidak valid.")
            _number(layer.setdefault("font_size", 64), "Ukuran font", 8, 512)
            _number(layer.setdefault("outline_width", 2), "Outline", 0, 30)
            layer["color"] = _color(layer.get("color", "#ffffff"), "Warna teks")
            layer["outline_color"] = _color(layer.get("outline_color", "#000000"), "Warna outline")
            if layer.setdefault("align", "center") not in {"left", "center", "right"}:
                raise DesignError("Perataan teks tidak valid.")
            if layer.get("font_asset_id") and not any(a["id"] == layer["font_asset_id"] and a["kind"] == "font" for a in assets):
                raise DesignError("Font layer belum diimpor.")
            if layer.get("font_asset_id") and asset_root is not None:
                font_asset = next(a for a in assets if a["id"] == layer["font_asset_id"])
                if layer["font_family"].casefold() not in _font_families(Path(asset_root) / font_asset["path"]):
                    raise DesignError("Font layer tidak cocok dengan font paket: " + layer["font_family"])
            if not isinstance(layer.setdefault("bold", True), bool):
                raise DesignError("Bold harus benar atau salah.")
            if kind == "text":
                if layer.setdefault("binding", "static") not in {"static", "title"} or not isinstance(layer.setdefault("text", "Teks"), str) or len(layer["text"]) > 2000:
                    raise DesignError("Teks atau binding tidak valid.")
            else:
                for key, default, maximum in (("words_per_group", 4, 20), ("max_lines", 2, 6)):
                    value = _number(layer.setdefault(key, default), key, 1, maximum)
                    if not value.is_integer():
                        raise DesignError(key + " harus bilangan bulat.")
                layer["highlight_color"] = _color(layer.get("highlight_color", "#bcff32"), "Highlight kata")
                layer["background"] = _color(layer.get("background", "#00000000"), "Latar subtitle")
        if kind == "image":
            if not any(a["id"] == layer.get("asset_id") and a["kind"] == "image" for a in assets):
                raise DesignError("Gambar layer belum diimpor.")
            if layer.setdefault("fit", "contain") not in {"contain", "cover"}:
                raise DesignError("Fit gambar tidak valid.")
        if kind == "rect":
            layer["color"] = _color(layer.get("color", "#000000"), "Warna bingkai")
            layer["border_color"] = _color(layer.get("border_color", "#ffffff"), "Border bingkai")
            _number(layer.setdefault("border_width", 0), "Lebar border", 0, 128)
    if videos != 1 or subtitles > 1:
        raise DesignError("Gunakan tepat satu video highlight dan maksimal satu layer subtitle.")
    audio = result.setdefault("audio", {})
    if not isinstance(audio, dict):
        raise DesignError("Audio template tidak valid.")
    for key, default, maximum in (("voice_volume", 1, 2), ("music_volume", .12, 2), ("fade_in", .5, 10), ("fade_out", 1, 10)):
        _number(audio.setdefault(key, default), key, 0 if key != "music_volume" else .001, maximum)
    if not isinstance(audio.setdefault("ducking", True), bool):
        raise DesignError("Ducking harus benar atau salah.")
    return result


def production_design(model, asset_root=None):
    value = validate_design(model, asset_root)
    for layer in value["layers"]:
        if layer["type"] in {"text", "subtitle"} and not layer.get("font_asset_id"):
            raise DesignError("Font " + layer["font_family"] + " belum disertakan dalam paket. Impor font atau terbitkan melalui Editor.")
    value["assets"] = [{key: asset[key] for key in ("id", "kind", "path", "name", "sha256", "font_family", "font_style", "system_font", "width", "height") if key in asset} for asset in value["assets"]]
    # Derived URLs and frontend selection state never leave the authoring app.
    allowed = {"id", "type", "name", "x", "y", "width", "height", "rotation", "visible", "locked", "timing", "fit", "framing", "binding", "text", "font_family", "font_asset_id", "font_size", "color", "align", "bold", "outline_color", "outline_width", "words_per_group", "max_lines", "highlight_color", "background", "asset_id", "border_color", "border_width"}
    value["layers"] = [{key: field for key, field in layer.items() if key in allowed} for layer in value["layers"]]
    return {key: value[key] for key in ("schema_version", "id", "name", "canvas", "layers", "assets", "audio")}


def export_design_package(model, asset_root, destination, version=1):
    from .package import inspect_package
    model = production_design(model, asset_root)
    if type(version) is not int or not 1 <= version <= 100000:
        raise DesignError("Versi template harus bilangan positif.")
    payload = json.dumps(model, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
    files = {"design.json": hashlib.sha256(payload).hexdigest()}
    for asset in model["assets"]:
        files[asset["path"]] = sha256(Path(asset_root) / asset["path"])
    video = next(layer for layer in model["layers"] if layer["type"] == "video")
    manifest = {"format": FORMAT, "schema_version": 1, "id": model["id"], "name": model["name"], "version": version,
        "duration_policy": "source_duration", "canvas": model["canvas"], "source_framing": video["framing"],
        "subtitle_style": "clean", "required_services": [], "files": files, "authoring_editor": "SSR Editor"}
    output = Path(destination).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as temp:
        archive = Path(temp) / "package.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            z.writestr("design.json", payload)
            for asset in model["assets"]:
                z.write(Path(asset_root) / asset["path"], asset["path"])
        inspect_package(archive)
        os.replace(archive, output)
    return manifest


def validate_manifest(manifest):
    if manifest.get("format") != FORMAT or manifest.get("schema_version") != 1 or manifest.get("duration_policy") != "source_duration":
        raise DesignError("Format paket desain tidak valid.")
    if not re.fullmatch(r"[a-z][a-z0-9_-]{1,63}", str(manifest.get("id", ""))) or type(manifest.get("version")) is not int or not 1 <= manifest["version"] <= 100000:
        raise DesignError("Identitas versi desain tidak valid.")
    files = manifest.get("files")
    if not isinstance(files, dict) or "design.json" not in files or len(files) > 129:
        raise DesignError("Paket desain memerlukan design.json dan checksum.")
    for name, checksum in files.items():
        name = _safe_name(name)
        if name != "design.json" and (not name.startswith("assets/") or Path(name).suffix.lower() not in IMAGE_EXTENSIONS | FONT_EXTENSIONS):
            raise DesignError("Paket desain hanya menerima model, gambar, dan font.")
        if not re.fullmatch(r"[a-f0-9]{64}", str(checksum)):
            raise DesignError("Checksum desain tidak valid.")
    return copy.deepcopy(manifest)


def validate_package_model(model, manifest, asset_root=None):
    model = validate_design(model, asset_root)
    if "preview" in model or any(key in model for key in ("created_at", "updated_at", "revision", "published_versions", "archived")):
        raise DesignError("Paket produksi tidak boleh menyertakan state editor atau video contoh.")
    if model["id"] != manifest["id"] or model["name"] != manifest.get("name") or model["canvas"] != manifest.get("canvas"):
        raise DesignError("Model desain berbeda dari manifest.")
    if {"design.json", *(asset["path"] for asset in model["assets"])} != set(manifest["files"]):
        raise DesignError("Aset model berbeda dari manifest.")
    video = next(layer for layer in model["layers"] if layer["type"] == "video")
    if any(layer["type"] in {"text", "subtitle"} and not layer.get("font_asset_id") for layer in model["layers"]):
        raise DesignError("Font teks/subtitle harus disertakan agar paket portable.")
    if video["framing"] != manifest.get("source_framing") or manifest.get("required_services") != []:
        raise DesignError("Konfigurasi renderer desain berbeda dari manifest.")
    return model


def load_design(directory):
    from .package import load_template
    directory = Path(directory).resolve()
    manifest = load_template(directory)
    if manifest["format"] != FORMAT:
        raise DesignError("Template MLT tidak memiliki model Editor yang dapat diedit.")
    return validate_package_model(json.loads((directory / "design.json").read_text(encoding="utf-8")), manifest, directory)


def inspect_design_package(path):
    from .package import inspect_package
    manifest = inspect_package(path)
    if manifest["format"] != FORMAT:
        raise DesignError("Paket bukan desain native SSR.")
    return manifest


def extract_design_package(path, destination):
    from .package import install_package
    directory, manifest = install_package(path, destination)
    return {"directory": str(directory), "manifest": manifest, "model": load_design(directory)}


def timing_bounds(timing, source_duration):
    mode = timing.get("mode", "full")
    start, length = float(timing.get("start", 0)), float(timing.get("duration", 4))
    if mode == "full":
        return 0., source_duration
    if mode == "end":
        end = source_duration - start
        start = end - length
    elif mode == "percent":
        start, end = source_duration * start / 100, source_duration * (start + length) / 100
    else:
        end = start + length
    return max(0., min(source_duration, start)), max(0., min(source_duration, end))


def _probe(path, ffprobe):
    result = subprocess.run([str(ffprobe), "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        capture_output=True, timeout=20, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    if result.returncode:
        raise DesignError("Tidak dapat membaca media: " + result.stderr.decode(errors="replace")[-400:])
    data = json.loads(result.stdout)
    video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    duration = float((data.get("format") or {}).get("duration") or (video or {}).get("duration") or 0)
    return {"duration": duration, "video": video, "audio": any(s.get("codec_type") == "audio" for s in data.get("streams", []))}


def subtitle_words_from_file(path):
    text = Path(path).read_text(encoding="utf-8-sig")
    if Path(path).suffix.lower() == ".json":
        data = json.loads(text)
        if isinstance(data, dict):
            return data.get("words") or [word for segment in data.get("segments", []) for word in segment.get("words", [])]
        return data
    result = []
    pattern = r"(\d+:\d{2}:\d{2}[,.]\d+)\s*-->\s*(\d+:\d{2}:\d{2}[,.]\d+)\s*\n(.*?)(?=\n\s*\n|\Z)"
    def seconds(value):
        h, m, s = value.replace(",", ".").split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)
    for match in re.finditer(pattern, text, re.S):
        start, end, phrase = seconds(match[1]), seconds(match[2]), re.sub(r"<[^>]+>", "", match[3]).strip()
        words = phrase.split()
        for index, word in enumerate(words):
            result.append({"word": word, "start": start + (end-start) * index / len(words), "end": start + (end-start) * (index+1) / len(words)})
    return result


def normalize_words(words, duration):
    result = []
    for word in words or []:
        if not isinstance(word, dict):
            word = {key: getattr(word, key, None) for key in ("word", "start", "end")}
        try:
            start, end = max(0., float(word["start"])), min(duration, float(word["end"]))
        except (TypeError, KeyError, ValueError):
            raise DesignError("Waktu kata subtitle tidak valid.")
        text = str(word.get("word") or word.get("text") or "").strip()
        if math.isfinite(start) and math.isfinite(end) and end > start and text:
            result.append({"word": text, "start": start, "end": end})
    return sorted(result, key=lambda w: (w["start"], w["end"]))


def _ass_color(value):
    value = value.lstrip("#")
    alpha = 255 - int(value[6:8], 16) if len(value) == 8 else 0
    return f"&H{alpha:02X}{value[4:6]}{value[2:4]}{value[:2]}"


def _ass_text(value):
    return str(value).replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}").replace("\n", r"\N").replace("\r", "")


def _ass_time(seconds):
    centiseconds = max(0, round(seconds * 100))
    return f"{centiseconds//360000}:{centiseconds//6000%60:02}:{centiseconds//100%60:02}.{centiseconds%100:02}"


def _wrap_tokens(tokens, layer):
    # Reserve a conservative glyph budget to keep preview and libass wrapping
    # within the design box. ASS may wrap further for unusually wide fonts.
    budget = max(2, int(layer["width"] / (layer["font_size"] * .58)))
    lines, current, count = [], [], 0
    for index, token in enumerate(tokens):
        size = len(token)
        if current and count + size + 1 > budget:
            lines.append(current)
            current, count = [], 0
        current.append(index)
        count += size + (1 if len(current) > 1 else 0)
    if current:
        lines.append(current)
    return lines


def write_layer_ass(path, layer, canvas, duration, title="", words=None):
    start, end = timing_bounds(layer["timing"], duration)
    align = {"left": 7, "center": 8, "right": 9}[layer["align"]]
    x = layer["x"] + (0 if align == 7 else layer["width"] / 2 if align == 8 else layer["width"])
    pos = r"{\an%d\pos(%.2f,%.2f)\clip(%.2f,%.2f,%.2f,%.2f)\q2}" % (align, x, layer["y"], layer["x"], layer["y"], layer["x"]+layer["width"], layer["y"]+layer["height"])
    background = layer.get("background", "#00000000")
    opaque = len(background) == 7 or background[-2:] != "00"
    style = f"Style: Default,{layer['font_family']},{layer['font_size']},{_ass_color(layer['color'])},{_ass_color(layer.get('highlight_color', layer['color']))},{_ass_color(layer['outline_color'])},{_ass_color(background)}," + f"{-1 if layer.get('bold', True) else 0},0,0,0,100,100,0,0,{3 if opaque else 1},{layer['outline_width']},0,{align},0,0,0,1"
    events = []
    if layer["type"] == "text":
        text = title if layer["binding"] == "title" else layer["text"]
        tokens = str(text).split()
        lines = _wrap_tokens(tokens, layer)
        rendered = r"\N".join(_ass_text(" ".join(tokens[i] for i in line)) for line in lines)
        if end > start and rendered:
            events.append((start, end, pos + rendered))
    else:
        words = normalize_words(words, duration)
        index = 0
        while index < len(words):
            group = words[index:index + layer["words_per_group"]]
            # Do not leave a phrase on screen across a long source silence.
            for gap in range(1, len(group)):
                if group[gap]["start"] - group[gap-1]["end"] > .8:
                    group = group[:gap]
                    break
            while len(group) > 1 and len(_wrap_tokens([w["word"] for w in group], layer)) > layer["max_lines"]:
                group = group[:-1]
            tokens = [w["word"] for w in group]
            lines = _wrap_tokens(tokens, layer)
            for active, word in enumerate(group):
                event_start = max(start, word["start"])
                event_end = min(end, group[active+1]["start"] if active+1 < len(group) else word["end"])
                if event_end <= event_start:
                    continue
                rendered_lines = []
                for line in lines:
                    rendered_lines.append(" ".join((r"{\c&H" + _ass_color(layer["highlight_color"])[4:] + "&}" if i == active else r"{\c&H" + _ass_color(layer["color"])[4:] + "&}") + _ass_text(tokens[i]) for i in line))
                events.append((event_start, event_end, pos + r"\N".join(rendered_lines)))
            index += len(group)
    content = f"[Script Info]\nScriptType: v4.00+\nPlayResX: {canvas['width']}\nPlayResY: {canvas['height']}\nWrapStyle: 2\nScaledBorderAndShadow: yes\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n{style}\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    content += "".join(f"Dialogue: 0,{_ass_time(a)},{_ass_time(b)},Default,,0,0,0,,{text}\n" for a, b, text in events)
    Path(path).write_text(content, encoding="utf-8")
    return len(events)


def _filter_path(path):
    return str(Path(path).resolve()).replace("\\", "/").replace(":", r"\:").replace("'", r"\'").replace("[", r"\[").replace("]", r"\]")


def _run(command, duration, progress, cancel_event, timeout, log_path, progress_path):
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    start, reported = time.monotonic(), -1
    process = None
    try:
        with Path(log_path).open("wb") as log:
            process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=log, stdin=subprocess.DEVNULL, creationflags=flags)
            while process.poll() is None:
                cancelled = cancel_event.is_set() if hasattr(cancel_event, "is_set") else cancel_event() if callable(cancel_event) else False
                if cancelled:
                    raise DesignError("Render template dibatalkan.")
                if time.monotonic() - start > timeout:
                    raise DesignError("Render template melewati batas waktu.")
                if progress and Path(progress_path).exists():
                    values = re.findall(r"out_time_us=(\d+)", Path(progress_path).read_text(errors="replace"))
                    if values:
                        value = min(99, int(int(values[-1]) / 1000000 / duration * 100))
                        if value != reported:
                            progress(value)
                            reported = value
                time.sleep(.1)
        if process.returncode:
            raise DesignError("FFmpeg gagal merender desain: " + Path(log_path).read_text(errors="replace")[-1400:])
    finally:
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)


def render_design(model, asset_root, source_path, output_path, *, title="", subtitle_words=None, subtitle_path=None,
                  music_path=None, ffmpeg="ffmpeg", ffprobe=None, progress=None, cancel_event=None, timeout=600):
    model = validate_design(model, asset_root)
    source, output = Path(source_path).resolve(), Path(output_path).resolve()
    if not source.is_file() or source == output:
        raise DesignError("Pilih video sumber yang tersedia dan output yang berbeda.")
    if ffprobe is None:
        sibling = Path(ffmpeg).with_name("ffprobe.exe" if os.name == "nt" else "ffprobe")
        ffprobe = str(sibling) if sibling.is_file() else "ffprobe"
    info = _probe(source, ffprobe)
    if not info["video"] or not math.isfinite(info["duration"]) or not 0 < info["duration"] <= 3600:
        raise DesignError("Video sumber harus berdurasi positif, maksimal satu jam.")
    canvas, audio = model["canvas"], model["audio"]
    fps, duration = canvas["fps"], info["duration"]
    frames = math.ceil(duration * fps - 1e-6)
    timeline_duration = frames / fps
    if subtitle_path and subtitle_words is None:
        subtitle_words = subtitle_words_from_file(subtitle_path)
    if any(l["type"] == "subtitle" and l["visible"] for l in model["layers"]) and not subtitle_words:
        raise DesignError("Layer subtitle membutuhkan transkrip SRT atau waktu kata. Tambahkan transkrip contoh untuk Uji render.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="design-render-", dir=output.parent) as temp:
        temp = Path(temp)
        font_assets = [asset for asset in model["assets"] if asset["kind"] == "font"]
        if font_assets:
            font_directory = temp / "fonts"
            font_directory.mkdir()
            for asset in font_assets:
                source_font = Path(asset_root) / asset["path"]
                shutil.copy2(source_font, font_directory / (sha256(source_font) + source_font.suffix.lower()))
        filters = [f"color=c={canvas['background']}:s={canvas['width']}x{canvas['height']}:r={fps}:d={timeline_duration},format=rgba[base0]"]
        command = [str(ffmpeg), "-y", "-hide_banner", "-loglevel", "error", "-i", str(source)]
        base, inputs = "base0", 1
        for index, layer in enumerate(model["layers"]):
            if not layer["visible"]:
                continue
            start, end = timing_bounds(layer["timing"], duration)
            if end <= start:
                continue
            target = f"base{index+1}"
            width, height = max(2, round(layer["width"])), max(2, round(layer["height"]))
            x, y = round(layer["x"]), round(layer["y"])
            enabled = f"gte(t,{start})*lt(t,{end})"
            kind = layer["type"]
            if kind in {"video", "image"}:
                if kind == "video":
                    stream = "0:v"
                else:
                    asset = next(a for a in model["assets"] if a["id"] == layer["asset_id"])
                    command.extend(["-loop", "1", "-i", str(Path(asset_root) / asset["path"])])
                    stream = f"{inputs}:v"
                    inputs += 1
                mode = "increase" if layer["fit"] == "cover" else "decrease"
                sizing = f"format=rgba,scale={width}:{height}:force_original_aspect_ratio={mode}"
                if mode == "increase":
                    sizing += f",crop={width}:{height}"
                else:
                    sizing += f",pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=0x00000000"
                filters.append(f"[{stream}]{sizing},setsar=1,fps={fps},format=rgba,tpad=stop_mode=clone:stop_duration=1[layer{index}]")
                filters.append(f"[{base}][layer{index}]overlay={x}:{y}:enable='{enabled}':eof_action=repeat[{target}]")
            elif kind == "rect":
                filters.append(f"[{base}]drawbox=x={x}:y={y}:w={width}:h={height}:color={layer['color']}:t=fill:enable='{enabled}'[{target}]")
                if layer["border_width"]:
                    border_target = target + "b"
                    filters.append(f"[{target}]drawbox=x={x}:y={y}:w={width}:h={height}:color={layer['border_color']}:t={layer['border_width']}:enable='{enabled}'[{border_target}]")
                    target = border_target
            else:
                ass = temp / f"layer-{index}.ass"
                write_layer_ass(ass, layer, canvas, duration, title, subtitle_words)
                fonts = ""
                if font_assets:
                    fonts = f":fontsdir='{_filter_path(font_directory)}'"
                filters.append(f"[{base}]ass=filename='{_filter_path(ass)}'{fonts}[{target}]")
            base = target
        filters.append(f"[{base}]format=yuv420p[outv]")
        music_index = None
        if music_path:
            if not Path(music_path).is_file():
                raise DesignError("Musik contoh tidak tersedia.")
            music_index = inputs
            command.extend(["-stream_loop", "-1", "-i", str(music_path)])
        audio_label = None
        if info["audio"]:
            filters.append(f"[0:a]volume={audio['voice_volume']},apad,atrim=duration={timeline_duration}[voice]")
            audio_label = "voice"
        if music_index is not None:
            fade_in, fade_out = min(audio['fade_in'], timeline_duration/2), min(audio['fade_out'], timeline_duration/2)
            fades = f"aresample=48000,atrim=duration={timeline_duration},asetpts=PTS-STARTPTS,loudnorm=I=-20:TP=-2:LRA=11,volume={audio['music_volume']},afade=t=in:d={fade_in},afade=t=out:st={max(0,timeline_duration-fade_out)}:d={fade_out}"
            filters.append(f"[{music_index}:a]{fades}[music]")
            if audio_label and audio["ducking"]:
                filters.extend(["[voice]aresample=48000,asplit=2[voicesc][voiceout]", "[music][voicesc]sidechaincompress=threshold=0.025:ratio=8:attack=30:release=400[ducked]", "[voiceout][ducked]amix=inputs=2:duration=first:normalize=0[outa]"])
                audio_label = "outa"
            elif audio_label:
                filters.append("[voice][music]amix=inputs=2:duration=first:normalize=0[outa]")
                audio_label = "outa"
            else:
                audio_label = "music"
            filters.append(f"[{audio_label}]alimiter=limit=0.95:level=0[limited]")
            audio_label = "limited"
        graph = temp / "render.txt"
        graph.write_text(";\n".join(filters), encoding="utf-8")
        partial, progress_path, log = temp / "render.mp4", temp / "progress.txt", temp / "render.log"
        command.extend(["-filter_complex_threads", "1", "-filter_complex_script", str(graph), "-map", "[outv]"])
        if audio_label:
            command.extend(["-map", f"[{audio_label}]", "-c:a", "aac", "-b:a", "192k"])
        command.extend(["-c:v", "libx264", "-preset", "fast", "-crf", "18", "-threads", "2", "-r", str(fps), "-t", str(timeline_duration), "-movflags", "+faststart", "-progress", str(progress_path), str(partial)])
        _run(command, timeline_duration, progress, cancel_event, timeout, log, progress_path)
        actual = _probe(partial, ffprobe)
        if (not actual["video"] or (actual["video"]["width"], actual["video"]["height"]) != (canvas["width"], canvas["height"]) or actual["duration"] + 1/fps + .01 < duration or abs(actual["duration"]-timeline_duration) > .12 or (info["audio"] and not actual["audio"])):
            raise DesignError("Hasil desain tidak mempertahankan ukuran, durasi, atau audio sumber.")
        os.replace(partial, output)
        if progress:
            progress(100)
    return {"engine": "design", "template_id": model["id"], "frames": frames, "duration_seconds": actual["duration"],
            "duration_policy": "source_duration", "source_audio_preserved": info["audio"], "subtitles_rendered": bool(subtitle_words),
            "music_mixed": bool(music_path), "editor_required": False}
