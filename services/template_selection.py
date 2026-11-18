"""Deterministic, weighted template selection for campaign clip renders.

A draw is keyed by the job and clip, so retries produce the same edit. Persist
the returned record with the highlight; rerenders can reuse that trusted record
even after the campaign's template pool has changed.
"""
from __future__ import annotations

import copy
from fractions import Fraction
import hashlib
import json
import math


def _weight(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Bobot template harus berupa angka antara 1 dan 100.")
    if not 1 <= value <= 100 or not math.isfinite(value):
        raise ValueError("Bobot template harus berupa angka antara 1 dan 100.")
    return int(value) if float(value).is_integer() else value


def normalize_template_selection(editing):
    """Validate explicit pools; campaigns without a pool keep their fixed preset."""
    from .campaigns import resolve_editing_preset

    if not isinstance(editing, dict):
        raise ValueError("Konfigurasi template campaign tidak valid.")
    result = copy.deepcopy(editing)
    if "template_pool" not in result:
        if result.get("selection_mode", "fixed") != "fixed":
            raise ValueError("Pemilihan template acak memerlukan daftar template campaign.")
        result["selection_mode"] = "fixed"
        return result
    if result.get("selection_mode", "weighted_random") != "weighted_random":
        raise ValueError("Daftar template campaign harus menggunakan pemilihan acak.")
    pool = result["template_pool"]
    if not isinstance(pool, list) or not pool:
        raise ValueError("Pilih setidaknya satu template untuk campaign.")
    normalized, seen = [], set()
    for item in pool:
        if not isinstance(item, dict):
            raise ValueError("Setiap template campaign harus berupa object.")
        if not isinstance(item.get("preset_id"), str):
            raise ValueError("Template editing tidak dikenal.")
        preset = resolve_editing_preset(item["preset_id"])
        preset_id = preset["id"]
        if preset_id in seen:
            raise ValueError("Template campaign tidak boleh tercantum dua kali.")
        seen.add(preset_id)
        if not isinstance(item.get("enabled"), bool):
            raise ValueError("Status aktif template harus berupa benar atau salah.")
        normalized.append({"preset_id": preset_id, "enabled": item["enabled"],
                           "weight": _weight(item.get("weight"))})
    if not any(item["enabled"] for item in normalized):
        raise ValueError("Aktifkan setidaknya satu template untuk campaign.")
    # A cosmetic reordering in the editor must not reshuffle queued results.
    result["template_pool"] = sorted(normalized, key=lambda item: item["preset_id"])
    result["selection_mode"] = "weighted_random"
    return result


def _record(preset, mode, weight, total):
    record = {"preset_id": preset["id"], "preset_version": preset["version"],
            "name": preset["name"], "subtitle_template_id": preset["subtitle_template_id"],
            "features": copy.deepcopy(preset["features"]), "selection_mode": mode,
            "weight": weight, "total_weight": total}
    if preset.get("external_template"):
        record["external_template"] = copy.deepcopy(preset["external_template"])
    return record


def choose_template(campaign, seed, existing=None):
    """Draw one preset, or reuse a trusted backend selection from an old clip.

    ``existing`` must come from stored clip metadata, never a frontend override.
    Version mismatches fail explicitly rather than changing a previous render.
    """
    from .campaigns import resolve_editing_preset

    def checked(preset_id):
        preset = resolve_editing_preset(preset_id)
        expected = campaign.get("editing", {}).get("external_template_versions", {}).get(preset_id)
        if expected is not None and expected != preset.get("external_template"):
            raise ValueError("Isi versi template berubah sejak job dibuat. Impor versi baru dan buat job baru.")
        return preset

    if existing is not None:
        if not isinstance(existing, dict):
            raise ValueError("Catatan template clip tidak valid.")
        if not isinstance(existing.get("preset_id"), str):
            raise ValueError("Catatan template clip tidak valid.")
        preset = checked(existing["preset_id"])
        if preset.get("external_template") and existing.get("external_template") != preset["external_template"]:
            raise ValueError("Isi versi template clip berubah. Pulihkan versi yang dipakai clip.")
        if existing.get("preset_version") != preset["version"] or isinstance(existing.get("preset_version"), bool):
            raise ValueError("Versi template clip tidak tersedia. Buat clip baru dari sumber.")
        mode = existing.get("selection_mode", "fixed")
        if mode not in {"fixed", "weighted_random"}:
            raise ValueError("Cara pemilihan template clip tidak valid.")
        weight = _weight(existing.get("weight", 1))
        total = existing.get("total_weight", weight)
        if isinstance(total, bool) or not isinstance(total, (int, float)) or not math.isfinite(total) or total < weight:
            raise ValueError("Total bobot template clip tidak valid.")
        return _record(preset, mode, weight, total)

    editing = normalize_template_selection(campaign.get("editing", {}))
    if editing["selection_mode"] == "fixed":
        return _record(checked(editing.get("preset_id", "standard")), "fixed", 1, 1)
    active = [item for item in editing["template_pool"] if item["enabled"]]
    weights = [Fraction(str(item["weight"])) for item in active]
    total = sum(weights)
    encoded = json.dumps(seed, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    point = Fraction(int.from_bytes(hashlib.sha256(encoded).digest(), "big"), 1 << 256) * total
    cumulative = Fraction(0)
    for item, weight in zip(active, weights):
        cumulative += weight
        if point < cumulative:
            total_number = int(total) if total.denominator == 1 else float(total)
            return _record(checked(item["preset_id"]), "weighted_random", item["weight"], total_number)
    raise AssertionError("Weighted template draw outside validated pool")
