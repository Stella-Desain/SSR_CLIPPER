"""Installed template catalog. Has no dependency on Template Studio/Kdenlive."""
from __future__ import annotations

import json
from pathlib import Path
import re

from template_sdk.ssr_template_engine import TemplateError, install_package, load_template
from template_sdk.ssr_template_engine.package import manifest_digest
from .mlt_runtime import application_root, runtime_status


def library_root():
    return application_root() / "template_library"


def template_directory(preset_id):
    match = re.fullmatch(r"(?:mlt|design):([a-z][a-z0-9_-]{1,63}):v([1-9][0-9]{0,5})", str(preset_id))
    if not match:
        raise TemplateError("ID template MLT tidak valid.")
    return library_root() / (match[1] + "-v" + match[2])


def preset_from_manifest(manifest):
    canvas = manifest["canvas"]
    if manifest["format"] == "ssr-design-template":
        from template_sdk.ssr_template_engine.design import load_design
        directory = library_root() / (manifest["id"] + "-v" + str(manifest["version"]))
        model = load_design(directory)
        captions = any(layer["type"] == "subtitle" and layer["visible"] for layer in model["layers"])
        return {"id": f"design:{manifest['id']}:v{manifest['version']}", "version": manifest["version"],
            "name": manifest["name"], "features": {"highlight_finder": True, "add_captions": captions,
                "add_hook": False, "yt_title_maker": True, "portrait": False},
            "subtitle_template_id": "clean", "subtitle_name": "Desain Editor" if captions else "Tanpa subtitle",
            "format_label": f"{canvas['width']} × {canvas['height']}", "description": "Template Editor SSR, berjalan tanpa halaman Editor.",
            "external_template": {"engine": "design", "id": manifest["id"], "version": manifest["version"],
                "package_sha256": manifest_digest(manifest), "design_sha256": manifest["files"]["design.json"],
                "canvas": canvas, "source_framing": manifest["source_framing"], "duration_policy": manifest["duration_policy"],
                "audio": model["audio"], "custom_subtitles": captions}}
    style = manifest["subtitle_style"]
    return {"id": f"mlt:{manifest['id']}:v{manifest['version']}", "version": manifest["version"],
            "name": manifest["name"], "features": {"highlight_finder": True, "add_captions": True,
            "add_hook": False, "yt_title_maker": True,
            "portrait": canvas["width"] * 16 == canvas["height"] * 9 and manifest["source_framing"] != "fit"},
            "subtitle_template_id": style, "subtitle_name": style.title(),
            "format_label": f"{canvas['width']} × {canvas['height']}",
            "description": "Template Kdenlive, dirender oleh MLT tanpa editor.",
            "external_template": {"engine": "mlt", "id": manifest["id"], "version": manifest["version"],
                                  "package_sha256": manifest_digest(manifest),
                                  "timeline_sha256": manifest["files"]["timeline.mlt"], "canvas": canvas,
                                  "source_framing": manifest["source_framing"], "duration_policy": manifest["duration_policy"]}}


def resolve_preset(preset_id):
    return preset_from_manifest(load_template(template_directory(preset_id)))


def list_presets():
    root = library_root()
    if not root.is_dir():
        return []
    result = []
    archived_path = root / ".archived-designs.json"
    archived = set(json.loads(archived_path.read_text(encoding="utf-8")).get("ids", [])) if archived_path.is_file() else set()
    for path in sorted(root.iterdir()):
        if path.is_dir() and not path.name.startswith("."):
            manifest = load_template(path)
            if manifest["format"] == "ssr-design-template" and manifest["id"] in archived:
                continue
            result.append(preset_from_manifest(manifest))
    return result


def import_template(package):
    from template_sdk.ssr_template_engine import inspect_package
    path = Path(package).expanduser().resolve()
    if path.suffix.lower() != ".ssrtemplate":
        raise TemplateError("Pilih paket .ssrtemplate hasil ekspor Template Studio.")
    manifest = inspect_package(path)
    if manifest["format"] == "ssr-mlt-template":
        runtime_status(manifest["required_services"])
    directory, manifest = install_package(path, library_root())
    return {"status": "ok", "preset": preset_from_manifest(manifest), "directory": str(directory)}


class ExternalTemplateMixin:
    def import_editing_template(self, path):
        try:
            return import_template(path)
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def browse_editing_template(self):
        try:
            import webview
            paths = webview.windows[0].create_file_dialog(webview.OPEN_DIALOG, allow_multiple=False,
                                                        file_types=("SSR Template (*.ssrtemplate)",))
            return self.import_editing_template(str(paths[0])) if paths else {"status": "cancelled"}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def get_template_runtime_status(self):
        try:
            return runtime_status()
        except Exception as exc:
            return {"status": "error", "message": str(exc), "editor_required": False}
