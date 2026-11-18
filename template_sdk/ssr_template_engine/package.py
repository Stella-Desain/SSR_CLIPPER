"""Versioned, self contained MLT template format (source-duration, v1).

The editable project belongs to the author. A package contains only render XML
and media. Import never executes scripts. The entire prepared clip replaces the
source slot; matching timeline endpoints grow/shrink to the source duration.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
import xml.etree.ElementTree as ET
import zipfile

FORMAT = "ssr-mlt-template"
SCHEMA_VERSION = 1
MAX_PACKAGE_BYTES = 512 * 1024 * 1024
MAX_FILES = 256
MAX_XML_BYTES = 4 * 1024 * 1024
SOURCE = "{{SSR_SOURCE}}"
TITLE = "{{SSR_TITLE}}"
LAST = "{{SSR_LAST_FRAME}}"
COUNT = "{{SSR_FRAME_COUNT}}"
PATH_PROPERTIES = {"resource", "luma", "filename", "warp_resource"}
# These are deliberately a tested render subset, not every editor plug-in.
SERVICES = {
    "avformat", "avformat-novalidate", "color", "colour", "qimage", "pixbuf",
    "affine", "crop", "brightness", "gamma", "greyscale", "saturation",
    "sepia", "boxblur", "invert", "mirror", "charcoal", "oldfilm",
    "vignette", "dynamictext", "volume", "volume.keyframe", "panner",
    "qtblend", "mix", "composite", "luma", "frei0r.cairoblend",
    "frei0r.saturat0r", "frei0r.colgate", "frei0r.brightness", "frei0r.contrast0r",
    "frei0r.vignette", "frei0r.squareblur", "frei0r.glow", "frei0r.alpha0ps",
}
ASSET_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".pgm", ".wav", ".mp3", ".m4a", ".flac", ".ogg"}
TAGS = {"mlt", "profile", "producer", "chain", "playlist", "tractor", "multitrack", "track", "entry", "blank", "filter", "transition", "property", "consumer"}


class TemplateError(ValueError):
    pass


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest_digest(manifest):
    return hashlib.sha256(json.dumps(manifest, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def _safe_name(name):
    if not isinstance(name, str) or "\\" in name or ":" in name:
        raise TemplateError("Package paths must be relative POSIX paths.")
    path = PurePosixPath(name)
    if path.is_absolute() or any(p in {"..", ".", ""} for p in name.split("/")):
        raise TemplateError("Package paths must stay inside the package.")
    if any(p.endswith((".", " ")) or re.search(r'[<>"|?*\x00-\x1f]', p) for p in path.parts):
        raise TemplateError("Package paths must be portable across Windows and POSIX.")
    if any(p.casefold().split(".")[0] in {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))} for p in path.parts):
        raise TemplateError("Reserved filename in template package.")
    return path.as_posix()


def _xml(data):
    if len(data) > MAX_XML_BYTES or re.search(br"<!\s*(DOCTYPE|ENTITY)", data, re.I):
        raise TemplateError("Template XML cannot contain DTDs or entities.")
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise TemplateError("Invalid MLT XML.") from exc
    if root.tag != "mlt" or any(n.tag not in TAGS for n in root.iter()):
        raise TemplateError("Export render MLT XML, without scripts or editor extensions.")
    return root


def _profile(root):
    p = root.find("profile")
    if p is None:
        raise TemplateError("The render XML needs a project profile.")
    try:
        values = {k: int(p.get(k, "0")) for k in ("width", "height", "frame_rate_num", "frame_rate_den")}
    except ValueError as exc:
        raise TemplateError("Invalid project profile.") from exc
    fps = values["frame_rate_num"] / max(1, values["frame_rate_den"])
    if not (32 <= values["width"] <= 4096 and 32 <= values["height"] <= 4096 and values["frame_rate_den"] > 0 and 1 <= fps <= 120):
        raise TemplateError("Canvas must be 32–4096 pixels, with 1–120 fps.")
    return {**values, "fps": fps}


def _frame(value, fps):
    if value is None:
        return None
    if re.fullmatch(r"\d+", str(value)):
        return int(value)
    if re.fullmatch(r"\d+:\d{2}:\d{2}(?:\.\d+)?", str(value)):
        h, m, s = str(value).split(":")
        return round((int(h) * 3600 + int(m) * 60 + float(s)) * fps)
    raise TemplateError(f"Unsupported timeline time: {value}")


def _services(root):
    required = {p.text for p in root.iter("property") if p.get("name") == "mlt_service"}
    unknown = required - SERVICES
    if unknown:
        raise TemplateError("Unsupported MLT services: " + ", ".join(sorted(str(x) for x in unknown)))
    # Unspecified file producers infer avformat; all exported producers must be explicit.
    for node in list(root.iter("producer")) + list(root.iter("chain")):
        if node.find("property[@name='mlt_service']") is None:
            raise TemplateError("Every producer must declare its mlt_service.")
    return sorted(required)


def _manifest(value):
    if isinstance(value, dict) and value.get("format") == "ssr-design-template":
        from .design import validate_manifest
        return validate_manifest(value)
    if not isinstance(value, dict) or value.get("format") != FORMAT or value.get("schema_version") != SCHEMA_VERSION:
        raise TemplateError("Unsupported SSR template package version.")
    if not re.fullmatch(r"[a-z][a-z0-9_-]{1,63}", str(value.get("id", ""))):
        raise TemplateError("Template ID must use lowercase letters, digits, _ or -.")
    if type(value.get("version")) is not int or not 1 <= value["version"] <= 100000:
        raise TemplateError("Template version must be a positive integer.")
    if not isinstance(value.get("name"), str) or not 1 <= len(value["name"].strip()) <= 120:
        raise TemplateError("Template name is required (maximum 120 characters).")
    if value.get("duration_policy") != "source_duration" or value.get("subtitle_style") not in {"clean", "social", "bold"}:
        raise TemplateError("Use source_duration with Clean, Social, or Bold subtitles.")
    if value.get("source_framing") not in {"speaker", "fit", "center"}:
        raise TemplateError("Invalid source framing.")
    canvas = value.get("canvas", {})
    if value["source_framing"] != "fit" and canvas.get("width", 0) * 16 != canvas.get("height", 0) * 9:
        raise TemplateError("Speaker/center preprocessing currently requires a 9:16 template; use fit for other canvases.")
    if type(value.get("reference_frames")) is not int or not 1 <= value["reference_frames"] <= 432000:
        raise TemplateError("Invalid reference duration.")
    files = value.get("files")
    if not isinstance(files, dict) or not files or len(files) > MAX_FILES or "timeline.mlt" not in files:
        raise TemplateError("Template must include its timeline and file checksums.")
    for name, digest in files.items():
        _safe_name(name)
        if name != "timeline.mlt" and (not name.startswith("assets/") or Path(name).suffix.lower() not in ASSET_EXTENSIONS):
            raise TemplateError("Only the render timeline and packaged media assets are accepted.")
        if not re.fullmatch(r"[a-f0-9]{64}", str(digest)):
            raise TemplateError("Missing or invalid file checksum.")
    return copy.deepcopy(value)


def _validate_tree(root, manifest):
    if any(n.tag == "consumer" for n in root.iter()):
        raise TemplateError("Template packages cannot choose an output consumer.")
    profile = _profile(root)
    if profile != manifest.get("canvas"):
        raise TemplateError("Manifest canvas differs from its timeline.")
    if _services(root) != manifest.get("required_services"):
        raise TemplateError("Template service requirements differ from its timeline.")
    if root.get("root") is not None or root.get("producer") is not None:
        raise TemplateError("Render template must use the final timeline, without an external root.")
    source_ids = set()
    for node in root.iter():
        if node.tag == "property":
            name, value = node.get("name", ""), node.text or ""
            if name in {"xml", "xmldata", "qml", "script", "warp_resource"}:
                raise TemplateError("Embedded projects, title XML, timewarp and scripts are unsupported. Bake titles into media or use Dynamic Text.")
            if name in PATH_PROPERTIES and value:
                if value == SOURCE:
                    continue
                if value in manifest["files"] and value.startswith("assets/"):
                    continue
                # Colour generators and an empty/default luma aren't paths.
                parent = next((p for p in root.iter() if node in list(p)), None)
                service = parent.findtext("property[@name='mlt_service']") if parent is not None else None
                if name == "resource" and service in {"color", "colour"} and re.fullmatch(r"(?:#[0-9a-fA-F]{6,8}|[A-Za-z]+|0x[0-9a-fA-F]{6,8}|0)", value):
                    continue
                raise TemplateError("Unpackaged or external resource in template: " + value[:100])
            if name.startswith("meta.") or name.startswith("kdenlive:") or name.startswith("shotcut:"):
                raise TemplateError("Remove editor and source metadata from render templates.")
    for producer in list(root.iter("producer")) + list(root.iter("chain")):
        if producer.findtext("property[@name='resource']") == SOURCE:
            if producer.findtext("property[@name='mlt_service']") not in {"avformat", "avformat-novalidate"}:
                raise TemplateError("Source slots must be avformat producers.")
            source_ids.add(producer.get("id"))
            if producer.get("in", "0") != "0" or producer.get("out") != LAST:
                raise TemplateError("Source producers must preserve the full prepared clip.")
            for field, expected in (("in", "0"), ("out", LAST), ("length", COUNT)):
                prop = producer.find(f"property[@name='{field}']")
                if prop is not None and prop.text != expected:
                    raise TemplateError("Source producer timing must preserve the full prepared clip.")
    if not source_ids or None in source_ids:
        raise TemplateError("Template needs a named source video producer.")
    # This v1 contract intentionally refuses a source cut into fixed segments.
    # It would silently truncate a longer speech or replay the same source.
    used = set()
    for playlist in root.iter("playlist"):
        entries = list(playlist)
        refs = [n for n in entries if n.tag == "entry" and n.get("producer") in source_ids]
        if refs:
            if len(refs) != 1 or any(n.tag in {"entry", "blank"} for n in entries[:entries.index(refs[0])]):
                raise TemplateError("Source must begin at frame 0 as one continuous entry per track.")
            entry = refs[0]
            if entry.get("in", "0") != "0" or entry.get("out") != LAST:
                raise TemplateError("Source entries must preserve the full prepared clip.")
            if any(n.tag in {"entry", "blank"} for n in entries[entries.index(entry)+1:]):
                raise TemplateError("Put intro/outro assets in the campaign, not after the source slot.")
            used.add(entry.get("producer"))
    if used != source_ids:
        raise TemplateError("Every source producer must be used by a continuous timeline track.")
    timeline = list(root)[-1]
    if timeline.tag not in {"tractor", "playlist"} or timeline.get("out") != LAST or timeline.get("in", "0") != "0":
        raise TemplateError("Final timeline must span the entire source clip.")
    producers = {n.get("id"): n for n in root.iter() if n.tag in {"producer", "chain", "playlist", "tractor"}}
    if None in producers or len(producers) != sum(n.tag in {"producer", "chain", "playlist", "tractor"} for n in root.iter()):
        raise TemplateError("Timeline producers must have unique IDs.")
    def reachable(node, stack):
        node_id = node.get("id")
        if node_id in stack:
            raise TemplateError("Cyclic timeline references are unsupported.")
        result = {node_id} if node_id in source_ids else set()
        for reference in node.iter():
            if reference.tag in {"entry", "track"}:
                target = producers.get(reference.get("producer"))
                if target is None:
                    raise TemplateError("Missing producer referenced by timeline.")
                result.update(reachable(target, stack | {node_id}))
        return result
    if not source_ids.issubset(reachable(timeline, set())):
        raise TemplateError("Source tracks must be connected to the final timeline.")
    return manifest


def export_template(timeline, output, *, source, template_id, name, version=1, subtitle_style="clean", source_framing="fit"):
    """Package an editor-exported render .mlt; the editor is never executed."""
    timeline, source, output = Path(timeline).resolve(), Path(source).resolve(), Path(output).resolve()
    if timeline.suffix.lower() != ".mlt" or not source.is_file():
        raise TemplateError("Export a render .mlt and select its placeholder video file.")
    root = _xml(timeline.read_bytes())
    # Exported consumer paths belong to the author, never to the consumer app.
    for consumer in list(root.findall("consumer")):
        root.remove(consumer)
    profile = _profile(root)
    fps = profile["fps"]
    old_root = Path(root.get("root") or timeline.parent)
    if not old_root.is_absolute():
        old_root = timeline.parent / old_root
    root.attrib.pop("root", None)
    root.attrib.pop("producer", None)
    root.attrib.pop("LC_NUMERIC", None)
    final = list(root)[-1]
    end = _frame(final.get("out"), fps)
    if end is None:
        raise TemplateError("Render timeline must declare its end frame.")
    reference = end + 1
    assets = {}
    for parent in root.iter():
        for prop in list(parent.findall("property")):
            key, value = prop.get("name", ""), prop.text or ""
            if key.startswith(("meta.", "kdenlive:", "shotcut:")) or key in {"eof", "mute_on_pause", "seekable"}:
                parent.remove(prop)
                continue
            if key in {"xml", "xmldata", "qml", "script", "warp_resource"}:
                raise TemplateError("Use baked title/overlay media or Dynamic Text, without embedded title XML or scripts.")
            if key in PATH_PROPERTIES and value:
                service = parent.findtext("property[@name='mlt_service']")
                if key == "resource" and service in {"color", "colour"}:
                    continue
                resource = Path(value)
                if not resource.is_absolute():
                    resource = old_root / resource
                resource = resource.resolve()
                if resource == source:
                    prop.text = SOURCE
                    parent.set("in", "0")
                    parent.set("out", str(end))
                    length = parent.find("property[@name='length']")
                    if length is not None:
                        length.text = str(reference)
                    for field, timing in (("in", "0"), ("out", str(end))):
                        point = parent.find(f"property[@name='{field}']")
                        if point is not None:
                            point.text = timing
                else:
                    if not resource.is_file() or resource.suffix.lower() not in ASSET_EXTENSIONS:
                        raise TemplateError("Missing or unsupported asset: " + resource.name)
                    target = "assets/" + sha256(resource)[:24] + resource.suffix.lower()
                    assets[target] = resource
                    prop.text = target
    for node in root.iter():
        for key in ("in", "out", "length"):
            if key in node.attrib:
                frame = _frame(node.attrib[key], fps)
                node.set(key, LAST if key == "out" and frame == end else COUNT if key == "length" and frame == reference else str(frame))
        for prop in node.findall("property"):
            if prop.get("name") in {"in", "out", "length"}:
                frame = _frame(prop.text, fps)
                prop.text = LAST if prop.get("name") == "out" and frame == end else COUNT if prop.get("name") == "length" and frame == reference else str(frame)
    data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    files = {"timeline.mlt": hashlib.sha256(data).hexdigest(), **{key: sha256(path) for key, path in assets.items()}}
    manifest = _manifest({"format": FORMAT, "schema_version": SCHEMA_VERSION, "id": template_id,
        "version": version, "name": name, "authoring_editor": "Kdenlive", "duration_policy": "source_duration",
        "reference_frames": reference, "canvas": profile, "subtitle_style": subtitle_style,
        "source_framing": source_framing, "required_services": _services(root), "files": files})
    _validate_tree(root, manifest)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as temp:
        archive = Path(temp) / "package.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            z.writestr("timeline.mlt", data)
            for key, path in assets.items():
                z.write(path, key)
        inspect_package(archive)
        os.replace(archive, output)
    return manifest


def inspect_package(path):
    try:
        with zipfile.ZipFile(path) as z:
            info = z.infolist()
            names = [i.filename for i in info]
            if len(names) > MAX_FILES + 1 or len(names) != len(set(n.casefold() for n in names)) or sum(i.file_size for i in info) > MAX_PACKAGE_BYTES:
                raise TemplateError("Template package is too large or contains duplicate paths.")
            for item in info:
                _safe_name(item.filename)
                if item.is_dir() or (item.external_attr >> 16) & 0o170000 == 0o120000:
                    raise TemplateError("Template package cannot contain directories or symbolic links.")
            if "manifest.json" not in names or z.getinfo("manifest.json").file_size > 65536:
                raise TemplateError("Missing or oversized template manifest.")
            manifest = _manifest(json.loads(z.read("manifest.json")))
            if set(names) != {"manifest.json", *manifest["files"]}:
                raise TemplateError("Package files differ from manifest.")
            for name, expected in manifest["files"].items():
                if hashlib.sha256(z.read(name)).hexdigest() != expected:
                    raise TemplateError("Template checksum mismatch: " + name)
            if manifest["format"] == "ssr-design-template":
                from .design import validate_package_model
                if z.getinfo("design.json").file_size > MAX_XML_BYTES:
                    raise TemplateError("Native design model is too large.")
                validate_package_model(json.loads(z.read("design.json")), manifest)
            else:
                _validate_tree(_xml(z.read("timeline.mlt")), manifest)
            return manifest
    except (zipfile.BadZipFile, KeyError, json.JSONDecodeError) as exc:
        raise TemplateError("Invalid SSR template archive.") from exc


def install_package(path, library):
    manifest = inspect_package(path)
    library = Path(library).resolve()
    library.mkdir(parents=True, exist_ok=True)
    target = library / (manifest["id"] + "-v" + str(manifest["version"]))
    if target.exists():
        existing = load_template(target)
        if existing != manifest:
            raise TemplateError("This template version already exists with different contents. Export a new version.")
        return target, existing
    with tempfile.TemporaryDirectory(prefix=".import-", dir=library) as temp:
        staging = Path(temp) / "package"
        staging.mkdir()
        with zipfile.ZipFile(path) as z:
            for name in ["manifest.json", *manifest["files"]]:
                dest = staging / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(z.read(name))
        load_template(staging)
        try:
            staging.rename(target)
        except FileExistsError:
            if load_template(target) != manifest:
                raise TemplateError("Template version was imported with different contents.")
    return target, manifest


def load_template(directory):
    directory = Path(directory).resolve()
    try:
        manifest = _manifest(json.loads((directory / "manifest.json").read_text(encoding="utf-8")))
        for name, expected in manifest["files"].items():
            path = directory / name
            if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(directory) or sha256(path) != expected:
                raise TemplateError("Imported template asset changed or is missing: " + name)
        if manifest["format"] == "ssr-design-template":
            from .design import validate_package_model
            if (directory / "design.json").stat().st_size > MAX_XML_BYTES:
                raise TemplateError("Native design model is too large.")
            validate_package_model(json.loads((directory / "design.json").read_text(encoding="utf-8")), manifest, directory)
        else:
            _validate_tree(_xml((directory / "timeline.mlt").read_bytes()), manifest)
        return manifest
    except (OSError, json.JSONDecodeError) as exc:
        raise TemplateError("Imported template is unavailable or damaged.") from exc


def instantiate(directory, source, duration_seconds, title=""):
    """Return an XML instance without mutating the installed template."""
    directory, source = Path(directory).resolve(), Path(source).resolve()
    manifest = load_template(directory)
    if manifest["format"] != FORMAT:
        raise TemplateError("Native designs use render_design instead of MLT instantiate.")
    if not source.is_file() or not math.isfinite(float(duration_seconds)) or not 0 < float(duration_seconds) <= 3600:
        raise TemplateError("Prepared source must be a local video with positive duration up to one hour.")
    count = math.ceil(float(duration_seconds) * manifest["canvas"]["fps"] - 1e-6)
    root = _xml((directory / "timeline.mlt").read_bytes())
    root.set("root", directory.as_posix())
    for node in root.iter():
        for key, value in list(node.attrib.items()):
            if value in {LAST, COUNT}:
                node.set(key, str(count-1 if value == LAST else count))
        if node.tag == "property":
            value = node.text or ""
            if value in {LAST, COUNT}:
                node.text = str(count-1 if value == LAST else count)
            elif value == SOURCE:
                node.text = source.as_posix()
            elif value in manifest["files"]:
                node.text = (directory / value).as_posix()
            elif TITLE in value:
                if node.get("name") not in {"text", "argument"}:
                    raise TemplateError("SSR_TITLE can only be used in a Dynamic Text field.")
                node.text = value.replace(TITLE, str(title)[:300])
    return ET.tostring(root, encoding="utf-8", xml_declaration=True), manifest, count
