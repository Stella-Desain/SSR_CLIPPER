"""Native template drafts and bridge APIs, independent of GUI and model providers.

Drafts are mutable and revision checked. Published packages are immutable and
installed in the existing consumer library. Preview media never enters packages.
"""
from __future__ import annotations

import copy
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading
import uuid

from .editing import atomic_json
from .mlt_runtime import application_root

_INITIALIZE = threading.Lock()
_PROJECT_ID = re.compile(r"design-[a-f0-9]{32}")
_ASSET_EXTENSIONS = {
    "image": {".png", ".jpg", ".jpeg", ".webp", ".bmp"},
    "video": {".mp4", ".mov", ".mkv", ".webm", ".avi"},
    "audio": {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac"},
    "subtitle": {".srt", ".vtt", ".json"},
    "font": {".ttf", ".otf"},
}
_PREVIEW_KEYS = {"video": "video_path", "audio": "music_path", "subtitle": "subtitle_path"}
_DRAFT_KEYS = ("revision", "created_at", "updated_at", "archived", "published_versions")
_PREVIEW_DERIVED = {"video_url", "music_url", "subtitle_url", "subtitle_text", "subtitle_cues"}


def editor_root():
    return application_root() / "template_projects"


def _now():
    return datetime.now(timezone.utc).isoformat()


def _clean(model):
    model = copy.deepcopy(model)
    model.pop("last_render", None)
    for asset in model.get("assets", []):
        asset.pop("url", None)
    preview = model.get("preview", {})
    for key in _PREVIEW_DERIVED:
        preview.pop(key, None)
    return model


def _within(root, relative):
    relative = str(relative)
    if not relative or "\\" in relative or ":" in relative:
        raise ValueError("Lokasi aset template tidak valid.")
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root.resolve()):
        raise ValueError("Aset harus berada di dalam project template.")
    return candidate


def _sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _subtitle_preview(path):
    """Read existing sample subtitles only. No transcription or network calls."""
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("Subtitle contoh maksimal 2 MB.")
    raw = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() == ".json":
        data = json.loads(raw)
        items = (data.get("words") or data.get("segments", [])) if isinstance(data, dict) else data
        cues = [{"start": float(item["start"]), "end": float(item["end"]),
                 "text": str(item.get("text", item.get("word", "")))} for item in items]
        if not cues or any(not math.isfinite(item["start"]) or not math.isfinite(item["end"])
                           or item["start"] < 0 or item["end"] <= item["start"] for item in cues):
            raise ValueError("Waktu subtitle contoh tidak valid.")
        return raw, cues
    cues = []
    pattern = re.compile(r"(?:(\d+):)?(\d{2}):(\d{2})[,.](\d{3})")
    def seconds(value):
        match = pattern.fullmatch(value.strip().split()[0])
        if not match:
            raise ValueError("Waktu subtitle contoh tidak valid.")
        h, m, s, ms = match.groups()
        return int(h or 0) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000
    for block in re.split(r"\n\s*\n", raw.replace("\r\n", "\n")):
        lines = block.strip().splitlines()
        for number, line in enumerate(lines):
            if "-->" in line:
                start, end = line.split("-->", 1)
                text = re.sub(r"<[^>]*>", "", " ".join(lines[number + 1:]))
                cues.append({"start": seconds(start), "end": seconds(end), "text": text})
                break
    if not cues:
        raise ValueError("Subtitle contoh belum berisi ucapan dengan waktu yang valid.")
    if any(item["start"] < 0 or item["end"] <= item["start"] for item in cues):
        raise ValueError("Waktu subtitle contoh tidak valid.")
    return raw, cues


def _preview_words(path):
    if Path(path).suffix.lower() == ".json":
        from template_sdk.ssr_template_engine.design import subtitle_words_from_file
        timed_words = subtitle_words_from_file(path)
        if timed_words:
            return timed_words
    _, cues = _subtitle_preview(Path(path))
    words = []
    for cue in cues:
        tokens = cue["text"].split()
        for index, token in enumerate(tokens):
            words.append({"word": token, "start": cue["start"] + (cue["end"] - cue["start"]) * index / len(tokens),
                          "end": cue["start"] + (cue["end"] - cue["start"]) * (index + 1) / len(tokens)})
    return words


class RevisionConflict(ValueError):
    pass


class TemplateEditorMixin:
    def _editor_state(self):
        if not hasattr(self, "_editor_lock"):
            with _INITIALIZE:
                if not hasattr(self, "_editor_lock"):
                    self._editor_lock = threading.RLock()
                    self._editor_renders = {}
                    self._editor_urls = {}
        return self._editor_lock

    def _editor_directory(self, project_id):
        if not isinstance(project_id, str) or not _PROJECT_ID.fullmatch(project_id):
            raise ValueError("ID project template tidak valid.")
        root = editor_root().resolve()
        return _within(root, project_id)

    def _editor_read(self, project_id):
        directory = self._editor_directory(project_id)
        path = directory / "project.json"
        if not path.is_file():
            raise ValueError("Project template tidak ditemukan.")
        model = json.loads(path.read_text(encoding="utf-8"))
        if model.get("id") != project_id:
            raise ValueError("Identitas project template tidak sesuai.")
        return model

    def _editor_validate(self, model, directory):
        from template_sdk.ssr_template_engine.design import validate_design
        clean = _clean(model)
        result = validate_design(clean, asset_root=directory)
        # Lifecycle belongs to authoring; the render SDK may deliberately strip it.
        for key in _DRAFT_KEYS:
            if key in clean:
                result[key] = clean[key]
        result["preview"] = copy.deepcopy(clean.get("preview", {}))
        return result

    def _editor_prepare_fonts(self, model, directory):
        """Freeze selected system fonts into assets for portable publication."""
        from utils.font_scanner import get_path_for_name
        from PIL import ImageFont
        model = _clean(model)
        for layer in model.get("layers", []):
            if layer.get("type") not in {"text", "subtitle"} or layer.get("font_asset_id"):
                continue
            family = layer.get("font_family") or "Arial"
            name = family + " Bold" if layer.get("bold") and not family.lower().endswith("bold") else family
            selected = get_path_for_name(name) or get_path_for_name(family)
            if not selected:
                raise ValueError("Font pada layer " + str(layer.get("name", "Teks")) +
                                 " belum tersedia. Pilih font lain atau impor font ini: " + family)
            source = Path(selected).resolve(strict=True)
            if source.suffix.lower() not in _ASSET_EXTENSIONS["font"]:
                raise ValueError("Impor font TTF/OTF untuk layer " + str(layer.get("name", "Teks")) + ".")
            digest = _sha(source)
            asset = next((item for item in model.get("assets", [])
                          if item.get("kind") == "font" and item.get("sha256") == digest), None)
            if not asset:
                asset_id = "asset-" + digest[:32]
                relative = "assets/" + asset_id + source.suffix.lower()
                target = _within(directory, relative)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                actual_family, actual_style = ImageFont.truetype(str(target), 20).getname()
                asset = {"id": asset_id, "kind": "font", "path": relative, "name": source.name,
                         "sha256": digest, "font_family": actual_family, "system_font": True,
                         "font_style": "bold" if "bold" in actual_style.lower() or "black" in actual_style.lower() else "normal"}
                model.setdefault("assets", []).append(asset)
            layer["font_asset_id"] = asset["id"]
            # ASS uses the embedded font's actual family; the display name may include a style.
            layer["font_family"] = asset["font_family"]
        return model

    def _editor_write(self, model):
        directory = self._editor_directory(model["id"])
        model = _clean(model)
        atomic_json(directory / "project.json", model)
        return model

    def _editor_url(self, path):
        from .media_preview import MediaPreview
        path = str(Path(path).resolve(strict=True))
        with self._editor_state():
            if path not in self._editor_urls:
                if not hasattr(self, "_media_preview"):
                    self._media_preview = MediaPreview()
                self._editor_urls[path] = self._media_preview.register(path)
            return self._editor_urls[path]

    def _editor_hydrate(self, model):
        model = _clean(model)
        directory = self._editor_directory(model["id"])
        for asset in model.get("assets", []):
            path = _within(directory, asset["path"])
            if path.is_file():
                asset["url"] = self._editor_url(path)
        preview = model.setdefault("preview", {})
        for key in ("video_path", "music_path", "subtitle_path"):
            path = Path(preview.get(key, ""))
            if preview.get(key) and path.is_file():
                preview[key.replace("_path", "_url")] = self._editor_url(path)
                if key == "subtitle_path":
                    try:
                        preview["subtitle_text"], preview["subtitle_cues"] = _subtitle_preview(path)
                    except (OSError, ValueError, TypeError, KeyError):
                        preview["subtitle_cues"] = []
        result_path = directory / "preview-result.json"
        if result_path.is_file():
            record = json.loads(result_path.read_text(encoding="utf-8"))
            model["last_render"] = record
            if record.get("path") and Path(record["path"]).is_file():
                record["url"] = self._editor_url(record["path"])
            if record.get("thumbnail_path") and Path(record["thumbnail_path"]).is_file():
                record["thumbnail_url"] = self._editor_url(record["thumbnail_path"])
        return model

    @staticmethod
    def _editor_error(exc):
        result = {"status": "error", "message": str(exc)}
        if isinstance(exc, RevisionConflict):
            result["conflict"] = True
        return result

    def editor_list_projects(self):
        try:
            with self._editor_state():
                projects = []
                root = editor_root()
                if root.is_dir():
                    for directory in root.iterdir():
                        if directory.is_dir() and _PROJECT_ID.fullmatch(directory.name) and (directory / "project.json").is_file():
                            model = self._editor_read(directory.name)
                            item = {key: copy.deepcopy(model.get(key)) for key in
                                    ("id", "name", "canvas", "updated_at", "archived", "published_versions")}
                            rendered = directory / "preview-result.json"
                            if rendered.is_file():
                                record = json.loads(rendered.read_text(encoding="utf-8"))
                                if record.get("thumbnail_path") and Path(record["thumbnail_path"]).is_file():
                                    item["thumbnail_url"] = self._editor_url(record["thumbnail_path"])
                            projects.append(item)
                projects.sort(key=lambda item: item.get("updated_at") or "", reverse=True)
                from .external_templates import list_presets
                return {"status": "ok", "projects": projects, "presets": list_presets()}
        except Exception as exc:
            return self._editor_error(exc)

    def editor_create_project(self, options=None):
        try:
            from template_sdk.ssr_template_engine.design import new_design
            options = options or {}
            with self._editor_state():
                model = new_design(str(options.get("name") or "Template baru"),
                                   str(options.get("ratio") or "9:16"), design_id="design-" + uuid.uuid4().hex)
                model.update(revision=1, created_at=_now(), updated_at=_now(), archived=False, published_versions=[])
                model = self._editor_validate(model, self._editor_directory(model["id"]))
                self._editor_write(model)
                return {"status": "ok", "project": self._editor_hydrate(model)}
        except Exception as exc:
            return self._editor_error(exc)

    def editor_get_project(self, project_id):
        try:
            with self._editor_state():
                return {"status": "ok", "project": self._editor_hydrate(self._editor_read(project_id))}
        except Exception as exc:
            return self._editor_error(exc)

    def editor_save_project(self, project):
        try:
            if not isinstance(project, dict):
                raise ValueError("Data project template tidak valid.")
            with self._editor_state():
                current = self._editor_read(project.get("id"))
                if type(project.get("revision")) is not int or project["revision"] != current["revision"]:
                    raise RevisionConflict("Draft sudah berubah. Buka ulang project sebelum menyimpan perubahan ini.")
                # Asset files and sample references are approved only through add/browse.
                approved = {asset["id"]: asset for asset in current.get("assets", [])}
                model = _clean(project)
                for asset in model.get("assets", []):
                    existing = approved.get(asset.get("id"))
                    if existing is None or any(asset.get(key) != existing.get(key) for key in ("path", "kind", "sha256")):
                        raise ValueError("Tambahkan atau ganti aset melalui tombol Impor pada Editor.")
                for key in ("video_path", "music_path", "subtitle_path"):
                    if model.get("preview", {}).get(key) not in ("", None, current.get("preview", {}).get(key)):
                        raise ValueError("Pilih media contoh melalui tombol Impor pada Editor.")
                for key in ("created_at", "archived", "published_versions"):
                    model[key] = current[key]
                model["revision"] = current["revision"] + 1
                model["updated_at"] = _now()
                model = self._editor_validate(model, self._editor_directory(current["id"]))
                self._editor_write(model)
                return {"status": "ok", "project": self._editor_hydrate(model)}
        except Exception as exc:
            return self._editor_error(exc)

    def editor_duplicate_project(self, project_id):
        try:
            with self._editor_state():
                original = self._editor_read(project_id)
                model = _clean(original)
                model.update(id="design-" + uuid.uuid4().hex, name=(original["name"][:105] + " (salinan)"),
                             revision=1, created_at=_now(), updated_at=_now(), archived=False, published_versions=[])
                source = self._editor_directory(project_id)
                target = self._editor_directory(model["id"])
                for asset in model.get("assets", []):
                    old = _within(source, asset["path"])
                    new = _within(target, asset["path"])
                    new.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(old, new)
                self._editor_write(model)
                return {"status": "ok", "project": self._editor_hydrate(model)}
        except Exception as exc:
            return self._editor_error(exc)

    def editor_archive_project(self, project_id, archived=True):
        try:
            if not isinstance(archived, bool):
                raise ValueError("Status arsip tidak valid.")
            with self._editor_state():
                model = self._editor_read(project_id)
                model.update(archived=archived, revision=model["revision"] + 1, updated_at=_now())
                from .external_templates import library_root
                archive_index = library_root() / ".archived-designs.json"
                record = json.loads(archive_index.read_text(encoding="utf-8")) if archive_index.is_file() else {"ids": []}
                ids = set(record["ids"])
                if archived:
                    ids.add(project_id)
                else:
                    ids.discard(project_id)
                atomic_json(archive_index, {"ids": sorted(ids)})
                self._editor_write(model)
                return {"status": "ok", "project": self._editor_hydrate(model)}
        except Exception as exc:
            return self._editor_error(exc)

    def editor_add_asset(self, project_id, path, kind):
        try:
            if kind not in _ASSET_EXTENSIONS:
                raise ValueError("Jenis aset Editor tidak dikenali.")
            source = Path(path).expanduser().resolve(strict=True)
            if not source.is_file() or source.suffix.lower() not in _ASSET_EXTENSIONS[kind]:
                raise ValueError("Format file tidak sesuai dengan jenis aset yang dipilih.")
            if kind in {"image", "font"} and source.stat().st_size > 64 * 1024 * 1024:
                raise ValueError("Gambar dan font template maksimal 64 MB per file.")
            with self._editor_state():
                model = self._editor_read(project_id)
                asset_id = "asset-" + uuid.uuid4().hex
                asset = {"id": asset_id, "kind": kind, "name": source.name}
                if kind in _PREVIEW_KEYS:
                    preview = model.setdefault("preview", {})
                    if kind == "video":
                        from .editing import probe_media
                        from utils.helpers import get_ffmpeg_path
                        info = probe_media(source, get_ffmpeg_path())
                        if not info.get("has_video") or not math.isfinite(float(info["duration"])) or not 0 < info["duration"] <= 3600:
                            raise ValueError("Video contoh harus memiliki gambar dan durasi positif, maksimal satu jam.")
                        preview["duration"] = info["duration"]
                    elif kind == "subtitle":
                        _subtitle_preview(source)
                    else:
                        from .editing import probe_media
                        from utils.helpers import get_ffmpeg_path
                        if not probe_media(source, get_ffmpeg_path()).get("has_audio"):
                            raise ValueError("File musik contoh tidak memiliki audio.")
                    preview[_PREVIEW_KEYS[kind]] = str(source)
                    asset["path"] = str(source)
                else:
                    directory = self._editor_directory(project_id)
                    asset["path"] = "assets/" + asset_id + source.suffix.lower()
                    target = _within(directory, asset["path"])
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if kind == "image":
                        from PIL import Image
                        with Image.open(source) as image:
                            image.verify()
                        with Image.open(source) as image:
                            asset.update(width=image.width, height=image.height)
                    else:
                        from PIL import ImageFont
                        font = ImageFont.truetype(str(source), 20)
                        family, style = font.getname()
                        asset.update(font_family=family, system_font=False,
                                     font_style="bold" if "bold" in style.lower() or "black" in style.lower() else "normal")
                    shutil.copy2(source, target)
                    asset["sha256"] = _sha(target)
                    model.setdefault("assets", []).append(asset)
                model.update(revision=model["revision"] + 1, updated_at=_now())
                self._editor_write(model)
                hydrated = self._editor_hydrate(model)
                if kind in _PREVIEW_KEYS:
                    asset["url"] = self._editor_url(source)
                else:
                    asset = next(item for item in hydrated["assets"] if item["id"] == asset_id)
                return {"status": "ok", "asset": asset, "project": hydrated}
        except Exception as exc:
            return self._editor_error(exc)

    def _editor_dialog(self, kind, save=False):
        import webview
        if not webview.windows:
            raise ValueError("Dialog file tersedia saat aplikasi desktop dibuka.")
        extensions = _ASSET_EXTENSIONS.get(kind, {".ssrtemplate"})
        label = "SSR Template" if kind == "template" else kind.title()
        file_type = label + " (" + ";".join("*" + ext for ext in sorted(extensions)) + ")"
        options = {"file_types": (file_type,)}
        if save:
            options["save_filename"] = "template.ssrtemplate"
        else:
            options["allow_multiple"] = False
        values = webview.windows[0].create_file_dialog(webview.SAVE_DIALOG if save else webview.OPEN_DIALOG, **options)
        return values if isinstance(values, str) else (str(values[0]) if values else None)

    def editor_browse_asset(self, project_id, kind):
        try:
            if kind not in _ASSET_EXTENSIONS:
                raise ValueError("Jenis aset Editor tidak dikenali.")
            self._editor_read(project_id)
            path = self._editor_dialog(kind)
            return self.editor_add_asset(project_id, path, kind) if path else {"status": "cancelled"}
        except Exception as exc:
            return self._editor_error(exc)

    def editor_publish_project(self, project_id):
        try:
            from template_sdk.ssr_template_engine.design import export_design_package
            from .external_templates import import_template
            with self._editor_state():
                model = self._editor_read(project_id)
                if model.get("archived"):
                    raise ValueError("Pulihkan project dari arsip sebelum menerbitkan versi baru.")
                directory = self._editor_directory(project_id)
                model = self._editor_prepare_fonts(model, directory)
                model = self._editor_validate(model, directory)
                versions = [int(item["version"]) for item in model.get("published_versions", [])]
                if (directory / "versions").is_dir():
                    versions.extend(int(path.stem[1:]) for path in (directory / "versions").glob("v*.ssrtemplate")
                                    if re.fullmatch(r"v[1-9][0-9]*", path.stem))
                version = max(versions or [0]) + 1
                package = directory / "versions" / f"v{version}.ssrtemplate"
                package.parent.mkdir(parents=True, exist_ok=True)
                if package.exists():
                    raise ValueError("Versi ini sudah tersimpan. Buka ulang project untuk memulihkan riwayat publikasi.")
                export_design_package(model, directory, package, version=version)
                result = import_template(package)
                if result.get("status") != "ok":
                    raise ValueError(result.get("message", "Template belum dapat dipasang."))
                model.setdefault("published_versions", []).append({"version": version, "preset_id": result["preset"]["id"],
                    "published_at": _now(), "sha256": _sha(package), "path": str(package)})
                model.update(revision=model["revision"] + 1, updated_at=_now())
                self._editor_write(model)
                return {"status": "ok", "preset": result["preset"], "project": self._editor_hydrate(model), "path": str(package)}
        except Exception as exc:
            return self._editor_error(exc)

    def editor_export_project(self, project_id, path=None):
        try:
            from template_sdk.ssr_template_engine.design import export_design_package
            if not path:
                path = self._editor_dialog("template", save=True)
                if not path:
                    return {"status": "cancelled"}
            target = Path(path).expanduser().resolve()
            if target.suffix.lower() != ".ssrtemplate":
                target = target.with_suffix(".ssrtemplate")
            with self._editor_state():
                model = self._editor_read(project_id)
                directory = self._editor_directory(project_id)
                if target.is_relative_to(directory):
                    raise ValueError("Ekspor ke folder di luar project agar versi terbit tetap terlindungi.")
                model = self._editor_prepare_fonts(model, directory)
                model = self._editor_validate(model, directory)
                version = max([int(item["version"]) for item in model.get("published_versions", [])] or [0]) + 1
                export_design_package(model, directory, target, version=version)
                return {"status": "ok", "path": str(target)}
        except Exception as exc:
            return self._editor_error(exc)

    def editor_import_project(self, path=None):
        try:
            from template_sdk.ssr_template_engine import inspect_package, install_package
            from template_sdk.ssr_template_engine.design import load_design
            from .external_templates import import_template
            if not path:
                path = self._editor_dialog("template")
                if not path:
                    return {"status": "cancelled"}
            source = Path(path).expanduser().resolve(strict=True)
            manifest = inspect_package(source)
            if manifest.get("format") != "ssr-design-template":
                result = import_template(source)
                result.update(editable=False, message="Template MLT sudah dipasang untuk campaign. Desain ini belum bisa diedit di Editor native.")
                return result
            with self._editor_state():
                editor_root().mkdir(parents=True, exist_ok=True)
                with tempfile.TemporaryDirectory(prefix=".import-", dir=editor_root()) as temporary:
                    installed, _ = install_package(source, Path(temporary))
                    model = load_design(installed)
                    model.update(id="design-" + uuid.uuid4().hex, revision=1, created_at=_now(), updated_at=_now(),
                                 archived=False, published_versions=[], imported_from={"id": manifest["id"], "version": manifest["version"]})
                    model["preview"] = {"video_path": "", "subtitle_path": "", "music_path": "", "title": "Judul clip", "duration": 30}
                    directory = self._editor_directory(model["id"])
                    for asset in model.get("assets", []):
                        original = _within(Path(installed), asset["path"])
                        destination = _within(directory, asset["path"])
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(original, destination)
                    self._editor_write(model)
                return {"status": "ok", "editable": True, "project": self._editor_hydrate(model)}
        except Exception as exc:
            return self._editor_error(exc)

    def editor_start_render(self, project_id, options=None):
        try:
            options = options or {}
            timeout = float(options.get("timeout", 600))
            if not 30 <= timeout <= 1800:
                raise ValueError("Batas waktu uji render harus 30–1800 detik.")
            with self._editor_state():
                if any(item["status"] in {"queued", "rendering", "cancelling"} for item in self._editor_renders.values()):
                    raise ValueError("Tunggu atau batalkan uji render yang sedang berjalan.")
                model = self._editor_read(project_id)
                directory = self._editor_directory(project_id)
                model = self._editor_prepare_fonts(model, directory)
                model = self._editor_validate(model, directory)
                preview = model.get("preview", {})
                source = Path(preview.get("video_path") or "")
                if not preview.get("video_path") or not source.is_file():
                    raise ValueError("Impor video contoh sebelum menjalankan Uji render.")
                render_id = "render-" + uuid.uuid4().hex
                output = directory / "renders" / render_id / "preview.mp4"
                event = threading.Event()
                record = {"id": render_id, "project_id": project_id, "revision": model["revision"], "status": "queued",
                          "progress": 0, "message": "Menyiapkan uji render.", "path": "", "url": "", "_cancel": event}
                self._editor_renders[render_id] = record
                thread = threading.Thread(target=self._editor_render_worker, args=(render_id, model, directory, output, timeout),
                                          name="template-preview-" + render_id[-8:], daemon=True)
                record["_thread"] = thread
                thread.start()
                return {"status": "ok", "render": self._editor_render_public(record)}
        except Exception as exc:
            return self._editor_error(exc)

    @staticmethod
    def _editor_render_public(record):
        return {key: copy.deepcopy(value) for key, value in record.items() if not key.startswith("_")}

    def _editor_render_worker(self, render_id, model, directory, output, timeout):
        event = self._editor_renders[render_id]["_cancel"]
        def update(progress=0, message=None):
            with self._editor_state():
                record = self._editor_renders[render_id]
                record["progress"] = min(99, max(0, float(progress)))
                if message:
                    record["message"] = str(message)
        try:
            from template_sdk.ssr_template_engine.design import render_design
            from utils.helpers import get_ffmpeg_path
            with self._editor_state():
                self._editor_renders[render_id].update(status="rendering", message="Merender desain dengan media contoh.")
            if event.is_set():
                raise ValueError("Uji render dibatalkan.")
            preview = model.get("preview", {})
            output.parent.mkdir(parents=True, exist_ok=True)
            metadata = render_design(model, directory, preview["video_path"], output,
                          title=preview.get("title", "Judul clip"), subtitle_path=preview.get("subtitle_path") or None,
                          subtitle_words=_preview_words(preview["subtitle_path"]) if preview.get("subtitle_path") else None,
                          music_path=preview.get("music_path") or None, ffmpeg=get_ffmpeg_path(),
                          progress=update, cancel_event=event, timeout=timeout)
            if event.is_set():
                raise ValueError("Uji render dibatalkan.")
            if not output.is_file():
                raise ValueError("Renderer belum menghasilkan video preview.")
            url = self._editor_url(output)
            thumbnail = output.with_name("thumbnail.jpg")
            if isinstance(metadata, dict) and metadata.get("engine") == "design":
                try:
                    subprocess.run([get_ffmpeg_path(), "-y", "-hide_banner", "-loglevel", "error", "-i", str(output),
                                    "-frames:v", "1", "-vf", "scale=320:320:force_original_aspect_ratio=decrease", str(thumbnail)],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                except (OSError, subprocess.TimeoutExpired):
                    pass
            if event.is_set():
                raise ValueError("Uji render dibatalkan.")
            with self._editor_state():
                self._editor_renders[render_id].update(status="completed", progress=100, message="Uji render selesai.",
                                                      path=str(output), url=url)
                if thumbnail.is_file():
                    self._editor_renders[render_id].update(thumbnail_path=str(thumbnail), thumbnail_url=self._editor_url(thumbnail))
                persisted = self._editor_render_public(self._editor_renders[render_id])
                persisted.pop("url", None)
                persisted.pop("thumbnail_url", None)
                atomic_json(directory / "preview-result.json", persisted)
        except Exception as exc:
            with self._editor_state():
                self._editor_renders[render_id].update(status="cancelled" if event.is_set() else "failed",
                                                      message="Uji render dibatalkan." if event.is_set() else str(exc))

    def editor_get_render(self, render_id):
        try:
            with self._editor_state():
                if render_id not in self._editor_renders:
                    raise ValueError("Uji render tidak ditemukan. Mulai uji baru jika aplikasi sudah dibuka ulang.")
                return {"status": "ok", "render": self._editor_render_public(self._editor_renders[render_id])}
        except Exception as exc:
            return self._editor_error(exc)

    def editor_cancel_render(self, render_id):
        try:
            with self._editor_state():
                if render_id not in self._editor_renders:
                    raise ValueError("Uji render tidak ditemukan.")
                record = self._editor_renders[render_id]
                if record["status"] in {"queued", "rendering", "cancelling"}:
                    record["_cancel"].set()
                    record.update(status="cancelling", message="Membatalkan uji render.")
                return {"status": "ok"}
        except Exception as exc:
            return self._editor_error(exc)

    def editor_media_preview(self, path):
        try:
            requested = Path(path).resolve(strict=True)
            with self._editor_state():
                allowed = str(requested) in self._editor_urls
                if not allowed:
                    root = editor_root()
                    if root.is_dir():
                        for directory in root.iterdir():
                            if directory.is_dir() and _PROJECT_ID.fullmatch(directory.name) and (directory / "project.json").is_file():
                                model = self._editor_read(directory.name)
                                values = [_within(directory, item["path"]) for item in model.get("assets", [])]
                                values.extend(Path(model.get("preview", {}).get(key)).resolve() for key in
                                              ("video_path", "music_path", "subtitle_path") if model.get("preview", {}).get(key))
                                if requested in values:
                                    allowed = True
                                    break
                if not allowed or not requested.is_file():
                    raise ValueError("File ini belum diimpor sebagai aset atau media contoh Editor.")
                return {"status": "ok", "url": self._editor_url(requested)}
        except Exception as exc:
            return self._editor_error(exc)

    def editor_list_fonts(self):
        try:
            from utils.font_scanner import get_font_names
            return {"status": "ok", "fonts": get_font_names() or ["Arial"]}
        except Exception as exc:
            return self._editor_error(exc)

    def editor_shutdown(self):
        """Signal subprocess cancellation when the owning desktop window closes."""
        with self._editor_state():
            for record in self._editor_renders.values():
                if record["status"] in {"queued", "rendering", "cancelling"}:
                    record["_cancel"].set()
        return {"status": "ok"}
