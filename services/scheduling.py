"""Global clock policy and validated daily upload times."""
from datetime import datetime, timezone
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DEFAULT_TIMEZONE = "Asia/Makassar"
DEFAULT_UPLOAD_TIMES = ["09:00", "14:30"]


def scheduling_timezone(config=None):
    value = (config or {}).get("timezone") or DEFAULT_TIMEZONE
    if not isinstance(value, str):
        raise ValueError("Zona waktu di Pengaturan tidak valid.")
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError("Zona waktu tidak tersedia. Periksa Pengaturan dan data zona waktu aplikasi.") from exc
    return value


def normalize_upload_times(value=None):
    if value is None:
        return list(DEFAULT_UPLOAD_TIMES)
    if not isinstance(value, list) or not value or len(value) > 100:
        raise ValueError("Isi setidaknya satu jam upload (maksimal 100 jam).")
    result = set()
    for item in value:
        if not isinstance(item, str) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", item):
            raise ValueError("Jam upload harus berupa HH:MM yang valid.")
        result.add(item)
    return sorted(result)


def parse_schedule_time(value, zone_name):
    """Accept an offset timestamp or an unambiguous local wall-clock minute."""
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Tanggal dan jam upload tidak valid.") from exc
    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?", str(value)):
        raise ValueError("Isi tanggal dan jam upload lengkap.")
    zone = ZoneInfo(zone_name)
    candidates = set()
    for fold in (0, 1):
        candidate = parsed.replace(tzinfo=zone, fold=fold).astimezone(timezone.utc)
        if candidate.astimezone(zone).replace(tzinfo=None) == parsed:
            candidates.add(candidate)
    if not candidates:
        raise ValueError("Jam tersebut tidak tersedia akibat pergantian zona waktu. Pilih jam lain.")
    if len(candidates) > 1:
        raise ValueError("Jam tersebut berulang akibat pergantian zona waktu. Pilih jam lain.")
    return candidates.pop()


def publication_day(publication, zone_name):
    """Recompute legacy reservations in the current global zone."""
    return parse_schedule_time(publication["scheduled_at"], zone_name).astimezone(ZoneInfo(zone_name)).date().isoformat()


def display_schedule_time(value, zone_name):
    """Format human-facing exports independently of the machine's locale/zone."""
    if not value:
        return ""
    local = parse_schedule_time(value, zone_name).astimezone(ZoneInfo(zone_name))
    label = "WITA" if zone_name == DEFAULT_TIMEZONE else zone_name
    period = "AM" if local.hour < 12 else "PM"
    return f"{local.day:02d}/{local.month:02d}/{local.year:04d} {local.hour % 12 or 12:02d}:{local.minute:02d} {period} ({label})"
