"""Platform files prepared before review and bound to the same approval."""
from pathlib import Path
import shutil

from .additionals import ADDITIONAL_PLATFORMS, destination_platforms, platform_key, render_watermarks
from .editing import EditingValidationError, config_hash, file_sha256, probe_media, validate_render_canvas


def render_platform_variants(final, items, gate, campaign, ffmpeg="ffmpeg", renderer=None):
    final = Path(final)
    watermarks = [item for item in items if item["type"] == "watermark"]
    eligibility = {p: result["accepted"] for p, result in gate.get("platforms", {}).items()}
    if not watermarks:
        return {}, eligibility, [], None
    base = final.parent / "base.mp4"
    shutil.copyfile(final, base)
    canvas = probe_media(base, ffmpeg)
    def record(path, applied):
        validate_render_canvas(probe_media(path, ffmpeg), canvas, "Versi sosmed")
        return {"path": str(path.resolve()), "file_hash": file_sha256(path), "watermarks": applied}
    variants = {"default": record(base, [])}
    groups = {}
    for platform in ADDITIONAL_PLATFORMS:
        if eligibility.get(platform) is False:
            continue
        overlays = [item for item in watermarks if platform in item["platforms"]]
        if not overlays:
            variants[platform] = variants["default"].copy()
            continue
        key = config_hash(overlays)
        if key not in groups:
            target = final.parent / (platform + ".mp4")
            evidence = (renderer or render_watermarks)(base, target, overlays, ffmpeg)
            groups[key] = record(target, evidence)
        variants[platform] = groups[key].copy()
    preferred = next((p for p in destination_platforms(campaign) if eligibility.get(p, True)), "default")
    chosen = variants.get(preferred, variants["default"])
    shutil.copyfile(chosen["path"], final)
    return variants, eligibility, chosen["watermarks"], preferred


def publication_media(clip, platform):
    platform = platform_key(platform)
    if clip.get("platform_eligibility", {}).get(platform) is False:
        raise EditingValidationError(f"Clip tidak lolos Additional untuk {platform}.")
    variants = clip.get("platform_variants") or {}
    if not variants:
        return {"path": clip["path"], "file_hash": clip["file_hash"]}
    if platform in ADDITIONAL_PLATFORMS and platform not in variants:
        raise EditingValidationError(f"Versi video {platform} belum tersedia. Render ulang clip sebelum distribusi.")
    selected = variants.get(platform) or variants.get("default")
    if not selected or not selected.get("path") or not selected.get("file_hash"):
        raise EditingValidationError("Versi video platform belum terverifikasi.")
    return selected


def verify_clip_files(clip, *, canvas=None, ffmpeg="ffmpeg"):
    files = [{"path": clip["path"], "file_hash": clip["file_hash"]}, *(clip.get("platform_variants") or {}).values()]
    checked = set()
    for item in files:
        key = (item.get("path"), item.get("file_hash"))
        if key in checked:
            continue
        checked.add(key)
        if not key[0] or not key[1] or not Path(key[0]).is_file() or file_sha256(key[0]) != key[1]:
            raise EditingValidationError("File clip atau versi platform berubah setelah render. Render ulang dan review kembali.")
        if canvas is not None:
            validate_render_canvas(probe_media(key[0], ffmpeg), canvas, "Render tersimpan")
