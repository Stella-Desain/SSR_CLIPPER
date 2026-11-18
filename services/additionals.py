"""Campaign additions scoped to a template's final canvas, independent of editors."""
from __future__ import annotations

import base64
import copy
import io
import math
from pathlib import Path
import re
import shutil
import tempfile
import uuid

from .editing import EditingValidationError, file_sha256, probe_media, validate_render_canvas, _run

ADDITIONAL_VERSION = 3
ADDITIONAL_PLATFORMS = ("tiktok", "instagram")
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
MAX_WATERMARK_IMAGES = 24


def _normalize_image(image):
    if not isinstance(image, dict):
        raise EditingValidationError("Gambar Additional tidak valid.")
    sha = str(image.get("sha256") or "")
    if sha and not re.fullmatch(r"[a-f0-9]{64}", sha):
        raise EditingValidationError("Fingerprint gambar Additional tidak valid.")
    clean = {"path": str(image.get("path") or ""), "sha256": sha,
             "name": str(image.get("name") or "")[:300]}
    if "width" in image or "height" in image:
        try:
            width, height = int(image["width"]), int(image["height"])
            if width <= 0 or height <= 0 or width * height > 25_000_000:
                raise ValueError("invalid image dimensions")
        except (KeyError, TypeError, ValueError, OverflowError):
            raise EditingValidationError("Dimensi gambar Additional tidak valid.") from None
        clean.update(width=width, height=height)
    return clean


def _normalize_layout(layout):
    if not isinstance(layout, dict):
        raise EditingValidationError("Tata letak watermark tidak valid.")
    clean = {"opacity": 1}
    for key, default, low, high in (("x", .65, 0, 1), ("y", .18, 0, 1), ("width", .18, .01, 1)):
        value = layout.get(key, default)
        try:
            number = float(value)
        except (ValueError, TypeError):
            raise EditingValidationError("Tata letak watermark harus berupa angka.") from None
        if isinstance(value, bool) or not math.isfinite(number) or not low <= number <= high:
            raise EditingValidationError(f"Nilai {key} watermark di luar batas.")
        clean[key] = number
    return clean


def watermark_layers(item):
    """The images array is authoritative, including an intentionally empty array."""
    if "images" in item:
        layers = item["images"]
    else:
        # Preserve the identity and layout of campaigns created before multi-image.
        layers = [{"id": item["id"], "image": item.get("image") or {},
                   "layout": item.get("layout") or {}}]
    if not isinstance(layers, list) or len(layers) > MAX_WATERMARK_IMAGES:
        raise EditingValidationError(f"Watermark maksimal {MAX_WATERMARK_IMAGES} gambar per Additional.")
    result, ids = [], set()
    for layer in layers:
        if not isinstance(layer, dict):
            raise EditingValidationError("Data gambar watermark tidak valid.")
        identifier = str(layer.get("id") or uuid.uuid4().hex)
        if not re.fullmatch(r"[\w-]{1,80}", identifier) or identifier in ids:
            raise EditingValidationError("ID gambar watermark tidak valid atau duplikat.")
        ids.add(identifier)
        result.append({"id": identifier, "image": _normalize_image(layer.get("image", {})),
                       "layout": _normalize_layout(layer.get("layout", {}))})
    return result


def additional_images(item):
    return [layer["image"] for layer in item["images"]] if item["type"] == "watermark" else [item["image"]]


def platform_key(value):
    value = str(value).strip().casefold()
    return "instagram" if value == "ig" else value


def ratio_key(width, height):
    width, height = int(width), int(height)
    if width <= 0 or height <= 0:
        raise EditingValidationError("Rasio hasil template tidak valid.")
    divisor = math.gcd(width, height)
    return f"{width // divisor}:{height // divisor}"


def normalize_additionals(items):
    if not isinstance(items, list) or len(items) > 24:
        raise EditingValidationError("Additional harus berupa daftar, maksimal 24 item.")
    result, ids = [], set()
    for item in items:
        if not isinstance(item, dict) or item.get("type") not in {"watermark", "face_filter"}:
            raise EditingValidationError("Jenis Additional tidak dikenal.")
        identifier = str(item.get("id") or uuid.uuid4().hex)
        if not re.fullmatch(r"[\w-]{1,80}", identifier) or identifier in ids:
            raise EditingValidationError("ID Additional tidak valid atau duplikat.")
        ids.add(identifier)
        if not isinstance(item.get("enabled", True), bool):
            raise EditingValidationError("Status aktif Additional harus berupa benar atau salah.")
        ratios = item.get("ratios", [])
        if not isinstance(ratios, list) or len(ratios) > 24:
            raise EditingValidationError("Pilih rasio hasil template untuk Additional.")
        canonical = []
        for value in ratios:
            if not isinstance(value, str) or not re.fullmatch(r"[1-9]\d{0,4}:[1-9]\d{0,4}", value):
                raise EditingValidationError("Rasio Additional harus seperti 16:9, 9:16, atau 1:1.")
            canonical.append(ratio_key(*map(int, value.split(":"))))
        platforms = item.get("platforms", list(ADDITIONAL_PLATFORMS))
        if not isinstance(platforms, list) or any(p not in ADDITIONAL_PLATFORMS for p in platforms):
            raise EditingValidationError("Sosmed Additional hanya TikTok dan Instagram.")
        template_scope = item.get("template_scope", "all")
        template_ids = item.get("template_ids", [])
        if template_scope not in {"all", "include", "exclude"} or not isinstance(template_ids, list):
            raise EditingValidationError("Aturan template Additional tidak valid.")
        from .campaigns import resolve_editing_preset
        for identifier_value in template_ids:
            if not isinstance(identifier_value, str):
                raise EditingValidationError("Pilihan template Additional tidak valid.")
            resolve_editing_preset(identifier_value)
        clean = {"id": identifier, "type": item["type"], "enabled": item.get("enabled", True) is True,
                 "ratios": list(dict.fromkeys(canonical)),
                 "platforms": list(dict.fromkeys(platforms)), "template_scope": template_scope,
                 "template_ids": list(dict.fromkeys(template_ids))}
        if item["type"] == "watermark":
            clean["images"] = watermark_layers({**item, "id": identifier})
        else:
            clean["image"] = _normalize_image(item.get("image") or {})
        result.append(clean)
    return result


def active_ratios(campaign):
    editing = campaign.get("editing") or {}
    ids = [item["preset_id"] for item in editing.get("template_pool", []) if item["enabled"]] if editing.get("selection_mode") == "weighted_random" else [editing.get("preset_id", "standard")]
    result = set()
    for identifier in ids:
        canvas = selected_canvas(campaign, {"editing_template": {"preset_id": identifier}})
        result.add(ratio_key(canvas["width"], canvas["height"]))
    return result


def template_applies(item, preset_id):
    return (item["template_scope"] == "all" or
            item["template_scope"] == "include" and preset_id in item["template_ids"] or
            item["template_scope"] == "exclude" and preset_id not in item["template_ids"])


def active_additionals(campaign):
    editing = campaign.get("editing") or {}
    ids = [p["preset_id"] for p in editing.get("template_pool", []) if p["enabled"]] if editing.get("selection_mode") == "weighted_random" else [editing.get("preset_id", "standard")]
    candidates = [(identifier, selected_canvas(campaign, {"editing_template": {"preset_id": identifier}})) for identifier in ids]
    return [item for item in normalize_additionals(editing.get("additional", [])) if item["enabled"]
            and any(template_applies(item, identifier) and ratio_key(canvas["width"], canvas["height"]) in item["ratios"]
                    for identifier, canvas in candidates)]


def destination_platforms(campaign):
    values = campaign.get("render_platforms") or campaign.get("platforms") or campaign.get("brief", {}).get("platforms") or list(ADDITIONAL_PLATFORMS)
    if not isinstance(values, list):
        values = [values]
    return list(dict.fromkeys(platform_key(p) for p in values if p)) or list(ADDITIONAL_PLATFORMS)


def selected_canvas(campaign, highlight=None):
    from .campaigns import resolve_editing_preset
    from .editing import resolve_template
    editing = campaign.get("editing") or {}
    chosen = (highlight or {}).get("editing_template") or {}
    preset = resolve_editing_preset(chosen.get("preset_id") or editing.get("preset_id", "standard"))
    return copy.deepcopy(preset.get("external_template", {}).get("canvas") or
        preset.get("canvas") or resolve_template(preset["subtitle_template_id"]).get("canvas") or
        {"width": 1080, "height": 1920, "fps": 30})


def applicable_additionals(campaign, highlight=None, canvas=None, platform=None):
    items = normalize_additionals((campaign.get("editing") or {}).get("additional", []))
    canvas = canvas or selected_canvas(campaign, highlight)
    ratio = ratio_key(canvas["width"], canvas["height"])
    preset_id = (highlight or {}).get("editing_template", {}).get("preset_id") or campaign.get("editing", {}).get("preset_id", "standard")
    return {"version": ADDITIONAL_VERSION, "ratio": ratio,
            "items": [item for item in items if item["enabled"] and ratio in item["ratios"] and template_applies(item, preset_id)
                      and (platform is None or platform in item["platforms"])]}


def read_image(asset):
    """Decode bounded real images; preserve alpha and honor phone EXIF rotation."""
    from PIL import Image, ImageOps
    path = Path(asset.get("path") or "")
    if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
        raise EditingValidationError("Gambar Additional belum tersedia. Unggah PNG, JPG, atau WebP.")
    if path.stat().st_size > 20 * 1024 * 1024:
        raise EditingValidationError("Gambar Additional maksimal 20 MB.")
    digest = file_sha256(path)
    if asset.get("sha256") and digest != asset["sha256"]:
        raise EditingValidationError("Gambar Additional berubah sejak campaign disimpan. Unggah kembali.")
    try:
        with Image.open(path) as source:
            if source.width * source.height > 25_000_000 or getattr(source, "n_frames", 1) != 1:
                raise ValueError("Gunakan gambar statis maksimal 25 megapiksel.")
            source.load()
            image = ImageOps.exif_transpose(source).convert("RGBA")
    except Exception as exc:
        raise EditingValidationError(f"Gambar Additional tidak dapat dibaca: {exc}") from exc
    if not image.getchannel("A").getbbox():
        raise EditingValidationError("Gambar seluruhnya transparan. Pilih gambar yang terlihat.")
    return image, digest


def image_preview(asset):
    image, digest = read_image(asset)
    width, height = image.size
    image.thumbnail((512, 512))
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    return {"status": "ok", "sha256": digest, "width": width, "height": height,
            "preview_url": "data:image/png;base64," + base64.b64encode(stream.getvalue()).decode("ascii")}


def import_image(asset, root):
    image, digest = read_image(asset)
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    original = Path(asset["path"]).resolve()
    target = root / (digest + original.suffix.lower())
    if not target.exists():
        temporary = root / ("." + uuid.uuid4().hex + ".tmp")
        try:
            shutil.copyfile(original, temporary)
            if file_sha256(temporary) != digest:
                raise EditingValidationError("Gambar berubah saat disalin. Coba unggah kembali.")
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
    elif file_sha256(target) != digest:
        raise EditingValidationError("Salinan gambar Additional berubah. Unggah kembali.")
    return {"path": str(target.resolve()), "sha256": digest,
            "name": str(asset.get("name") or original.name), "width": image.width, "height": image.height}


def validate_additionals(campaign):
    """Incomplete drafts can save, but cannot start production."""
    blockers, warnings = [], []
    items = normalize_additionals((campaign.get("editing") or {}).get("additional", []))
    active_ids = {item["id"] for item in active_additionals(campaign)} if items else set()
    for item in items:
        if not item["enabled"]:
            continue
        label = "Watermark" if item["type"] == "watermark" else "Hanya clip wajah"
        try:
            if not item["ratios"]:
                raise EditingValidationError("Pilih minimal satu rasio hasil template.")
            if not item["platforms"]:
                raise EditingValidationError("Pilih minimal satu sosmed: TikTok atau Instagram.")
            if item["template_scope"] == "include" and not item["template_ids"]:
                raise EditingValidationError("Pilih template untuk aturan 'Hanya digunakan pada template'.")
            if item["id"] not in active_ids:
                warnings.append(f"{label}: belum ada template aktif yang memenuhi pilihan template dan rasio {', '.join(item['ratios'])}; Additional belum diterapkan.")
                continue
            images = additional_images(item)
            if not images:
                raise EditingValidationError("Tambahkan minimal satu gambar watermark.")
            for asset in images:
                read_image(asset)
                if not asset["sha256"]:
                    raise EditingValidationError("Unggah ulang gambar agar snapshot campaign terverifikasi.")
            if item["type"] == "face_filter":
                from .target_faces import TargetFaceMatcher
                TargetFaceMatcher().reference(item["image"])
        except Exception as exc:
            blockers.append(f"{label}: {exc}")
    return blockers, warnings


def render_watermarks(source, target, items, ffmpeg="ffmpeg"):
    """Pure per-clip overlays. Never mutate shared renderer/global settings."""
    media = probe_media(source, ffmpeg)
    width, height = media["width"], media["height"]
    if not media["has_video"] or not width or not height:
        raise EditingValidationError("Canvas video watermark tidak valid.")
    inputs, filters, evidence = [], [], []
    with tempfile.TemporaryDirectory(prefix="ssr-watermarks-", dir=Path(target).parent) as directory:
        layers = [(item, layer) for item in items for layer in watermark_layers(item)]
        for index, (item, layer) in enumerate(layers, 1):
            image, digest = read_image(layer["image"])
            layout = layer["layout"]
            scale = min(width * layout["width"] / image.width, height / image.height)
            iw, ih = max(1, round(image.width * scale)), max(1, round(image.height * scale))
            image = image.resize((iw, ih))
            logo = Path(directory) / f"{index}.png"
            image.save(logo)
            x, y = round((width-iw) * layout["x"]), round((height-ih) * layout["y"])
            inputs += ["-i", str(logo)]
            previous = "0:v" if index == 1 else f"wm{index-1}"
            filters.append(f"[{previous}][{index}:v]overlay={x}:{y}:eof_action=repeat[wm{index}]")
            evidence.append({"id": item["id"], "image_id": layer["id"], "sha256": digest, "x": x, "y": y, "width": iw,
                             "height": ih, "opacity": 1})
        if not layers:
            shutil.copyfile(source, target)
            return []
        _run([str(ffmpeg), "-y", "-i", str(source), *inputs, "-filter_complex", ";".join(filters),
              "-map", f"[wm{len(layers)}]", "-map", "0:a?", "-c:v", "libx264", "-preset", "fast",
              "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", str(target)])
    validate_render_canvas(probe_media(target, ffmpeg), media, "Watermark")
    return evidence


class AdditionalMixin:
    def import_additional_images(self, paths):
        """Keep valid selections and report each rejected file without replacing layers."""
        if not isinstance(paths, (list, tuple)) or not 1 <= len(paths) <= MAX_WATERMARK_IMAGES:
            return {"status": "error", "message": f"Pilih 1–{MAX_WATERMARK_IMAGES} gambar watermark."}
        images, errors = [], []
        for path in paths:
            result = self.import_additional_image(path, "watermark")
            if result["status"] == "ok":
                images.append(result)
            else:
                errors.append({"name": Path(str(path)).name, "message": result["message"]})
        return {"status": "ok" if images else "error", "images": images, "errors": errors,
                "message": "; ".join(f"{e['name']}: {e['message']}" for e in errors)}

    def browse_additional_images(self):
        try:
            import webview
            if not webview.windows:
                raise EditingValidationError("Jendela aplikasi tidak tersedia.")
            paths = webview.windows[0].create_file_dialog(webview.OPEN_DIALOG, allow_multiple=True,
                file_types=("Images (*.png;*.jpg;*.jpeg;*.webp)",))
            return self.import_additional_images(paths) if paths else {"status": "cancelled"}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def import_additional_image(self, path, additional_type="watermark"):
        try:
            if additional_type not in {"watermark", "face_filter"}:
                raise EditingValidationError("Jenis Additional tidak dikenal.")
            asset = {"path": str(path)}
            if additional_type == "face_filter":
                from .target_faces import TargetFaceMatcher
                TargetFaceMatcher().reference(asset)
            asset = import_image(asset, Path(self.config_file).resolve().parent / "campaign_assets" / "additional")
            return {"status": "ok", "image": asset, **image_preview(asset)}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def browse_additional_image(self, additional_type="watermark"):
        try:
            import webview
            if not webview.windows:
                raise EditingValidationError("Jendela aplikasi tidak tersedia.")
            paths = webview.windows[0].create_file_dialog(webview.OPEN_DIALOG, allow_multiple=False,
                file_types=("Images (*.png;*.jpg;*.jpeg;*.webp)",))
            return self.import_additional_image(paths[0], additional_type) if paths else {"status": "cancelled"}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def get_additional_image_preview(self, image):
        try:
            return image_preview(image)
        except Exception as exc:
            return {"status": "error", "message": str(exc)}
