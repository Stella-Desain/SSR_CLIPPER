"""Audience-aware publication planning and a small Repliz transport."""
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from zoneinfo import ZoneInfo
import uuid

from .storage import digest, utc_now
from .scheduling import normalize_upload_times, parse_schedule_time, publication_day, scheduling_timezone
from .clip_variants import publication_media
from .additionals import platform_key
from .account_tags import publication_caption


ACTIVE = {"queued", "uploading", "scheduled", "publishing", "published", "needs_attention", "failed"}


def scope(value):
    return " ".join(str(value or "").casefold().split())


def overlapping(left, right):
    if left.get("clip_id", left.get("id")) == right.get("clip_id", right.get("id")):
        return True
    for a in left.get("source_ranges", []):
        for b in right.get("source_ranges", []):
            if not a.get("source_id") or a["source_id"] != b.get("source_id"):
                continue
            if max(float(a["start_seconds"]), float(b["start_seconds"])) < min(float(a["end_seconds"]), float(b["end_seconds"])):
                return True
    return False


def account_limit(campaign, profile):
    # Saved account settings are authoritative. Keep the old campaign value only
    # as a migration default for profiles that have never saved a daily limit.
    legacy = campaign.get("brief", {}).get("max_clips_per_day", campaign.get("max_clips_per_day", 2))
    return max(1, min(100, int(profile.get("daily_limit", legacy))))


def eligible_accounts(campaign, profiles, accounts):
    expected = scope(campaign.get("audience_scope"))
    if not expected:
        raise ValueError("Lengkapi lingkup audiens campaign sebelum distribusi.")
    profile_map = {str(p.get("account_id", p.get("id"))): p for p in profiles}
    assigned = {str(aid) for aid in campaign.get("account_ids", [])}
    if not assigned:
        raise ValueError("Pilih akun tujuan di Campaign sebelum membuat preview distribusi.")
    result = []
    reasons = []
    available = set()
    allowed_platforms = campaign.get("platforms", campaign.get("brief", {}).get("platforms", []))
    if isinstance(allowed_platforms, str):
        allowed_platforms = [allowed_platforms]
    for account in accounts:
        aid = str(account.get("_id", account.get("id", "")))
        available.add(aid)
        profile = profile_map.get(aid, {})
        if aid not in assigned:
            continue
        name = account.get("name") or aid
        if account.get("isConnected") is False:
            reasons.append(f"{name}: koneksi akun terputus; hubungkan kembali di Repliz")
            continue
        if not scope(profile.get("audience_scope")):
            reasons.append(f"{name}: isi dan simpan profil audiens akun di Campaign")
            continue
        if scope(profile.get("audience_scope")) != expected:
            reasons.append(f"{name}: audiens akun '{profile.get('audience_scope')}' berbeda dari campaign '{campaign.get('audience_scope')}'")
            continue
        if campaign.get("language") and profile.get("language") and scope(campaign["language"]) != scope(profile["language"]):
            reasons.append(f"{name}: bahasa akun berbeda dari campaign")
            continue
        if allowed_platforms and scope(account.get("type")) not in {scope(p) for p in allowed_platforms}:
            reasons.append(f"{name}: platform {account.get('type')} tidak termasuk platform campaign")
            continue
        result.append((account, profile))
    if not result:
        if assigned - available:
            reasons.append("Akun yang dipilih tidak ditemukan di Repliz; periksa koneksi dan penugasan akun di Campaign")
        raise ValueError("Distribusi belum siap. " + "; ".join(reasons))
    return result


def plan_distribution(clips, campaigns, profiles, accounts, existing, now=None, timezone_name="Asia/Makassar"):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Waktu scheduler harus menyertakan zona waktu.")
    zone_name = scheduling_timezone({"timezone": timezone_name})
    zone = ZoneInfo(zone_name)
    planned = []
    history = list(existing)
    for clip in clips:
        cid = clip.get("campaign_id")
        campaign = next((c for c in campaigns if c.get("id") == cid), None)
        if not campaign:
            raise ValueError("Clip belum terhubung dengan campaign yang tersedia.")
        if campaign.get("status") not in (None, "active"):
            raise ValueError("Campaign tidak aktif.")
        if clip.get("review_status") != "approved":
            raise ValueError(f"Review dan setujui clip {clip.get('title', clip['id'])} terlebih dahulu.")
        choices = []
        allowed_accounts = eligible_accounts(campaign, profiles, accounts)
        filtered_accounts = 0
        for account, profile in allowed_accounts:
            platform = platform_key(account.get("type", ""))
            if clip.get("platform_eligibility", {}).get(platform) is False:
                filtered_accounts += 1
                continue
            media = publication_media(clip, platform)
            aid = str(account.get("_id", account.get("id")))
            used = [p for p in history if p["account_id"] == aid and p["status"] in ACTIVE]
            if any(overlapping(clip, p) for p in used):
                continue
            local_now = now.astimezone(zone)
            limit = account_limit(campaign, profile)
            upload_times = normalize_upload_times(profile.get("upload_times"))
            for offset in range(366):
                day = local_now.date() + timedelta(days=offset)
                same_day = [p for p in used if publication_day(p, zone_name) == day.isoformat()]
                if len(same_day) >= limit:
                    continue
                found = False
                for slot in upload_times:
                    try:
                        scheduled = parse_schedule_time(day.isoformat() + "T" + slot, zone_name)
                    except ValueError:
                        # A repeated/nonexistent DST wall-clock slot is unsafe; use another.
                        continue
                    if scheduled < now + timedelta(minutes=5):
                        continue
                    if any(abs((parse_schedule_time(p["scheduled_at"], zone_name) - scheduled).total_seconds()) < 60 for p in same_day):
                        continue
                    choices.append((scheduled, len(same_day), len(used), aid, account, profile, limit))
                    found = True
                    break
                if found:
                    break
        if not choices:
            if filtered_accounts == len(allowed_accounts):
                raise ValueError("Clip tidak lolos Additional pada sosmed akun tujuan. Pilih clip lain atau periksa aturan campaign.")
            raise ValueError(f"Semua akun yang sesuai sudah memakai materi overlap untuk {clip.get('title', clip['id'])}.")
        when, _, _, aid, account, profile, limit = min(choices, key=lambda c: c[:4])
        platform = platform_key(account.get("type", ""))
        media = publication_media(clip, platform)
        caption = publication_caption(clip, platform)
        revision = clip.get("revision_id")
        key = digest({"clip_id": clip["id"], "account_id": aid})
        publication = {
            "id": "pub_" + uuid.uuid4().hex, "dedupe_key": key,
            "clip_id": clip["id"], "clip_title": clip.get("title", ""), "clip_path": media["path"],
            "campaign_id": cid, "campaign_version_id": clip.get("campaign_version_id"),
            "revision_id": revision, "file_hash": media["file_hash"], "approval_hash": clip.get("approval_hash"),
            "account_id": aid, "account_name": account.get("name", aid), "platform": platform,
            "audience_scope": campaign.get("audience_scope"), "daily_limit": limit,
            "timezone": zone_name, "upload_times": normalize_upload_times(profile.get("upload_times")),
            "scheduled_at": when.isoformat(), "local_day": when.astimezone(zone).date().isoformat(),
            "caption": caption, "status": "queued", "source_ranges": clip.get("source_ranges", []),
            "created_at": utc_now(), "error": None,
        }
        planned.append(publication)
        history.append(publication)
    return planned


def validate_reservation(publication, existing, now=None):
    zone_name = scheduling_timezone({"timezone": publication.get("timezone")})
    scheduled = parse_schedule_time(publication["scheduled_at"], zone_name)
    if scheduled <= (now or datetime.now(timezone.utc)):
        raise ValueError("Jadwal sudah lewat. Pilih tanggal dan jam upload yang akan datang.")
    day = publication_day(publication, zone_name)
    if publication.get("local_day") != day:
        raise ValueError("Tanggal jadwal tidak sesuai zona waktu global. Buat preview ulang.")
    relevant = [p for p in existing if p["account_id"] == publication["account_id"] and p["status"] in ACTIVE]
    if sum(publication_day(p, zone_name) == day for p in relevant) >= publication["daily_limit"]:
        raise ValueError("Slot akun baru saja terisi. Buat preview distribusi ulang.")
    if any(abs((parse_schedule_time(p["scheduled_at"], zone_name) - scheduled).total_seconds()) < 60 for p in relevant):
        raise ValueError("Akun ini sudah memiliki upload pada menit tersebut. Pilih jam lain.")
    # A reviewed batch may explicitly include different edits of overlapping
    # source material. This never permits posting the same clip twice.
    if any(p.get("clip_id") == publication.get("clip_id") for p in relevant):
        raise ValueError("Clip yang sama sudah terjadwal pada akun ini.")
    if publication.get("allow_source_overlap") is not True and any(overlapping(publication, p) for p in relevant):
        raise ValueError("Materi overlap sudah terjadwal pada akun ini. Buat preview ulang.")


class ReplizClient:
    def __init__(self, access_key, secret_key, session=None):
        import requests
        self.session = session or requests.Session()
        self.auth = (access_key, secret_key)
        if not access_key or not secret_key:
            raise ValueError("Repliz keys belum dikonfigurasi.")

    def get(self, path, params=None):
        response = self.session.get("https://api.repliz.com/public/" + path, params=params, auth=self.auth, timeout=25)
        response.raise_for_status()
        return response.json()

    def schedule(self, schedule_id):
        return self.get("schedule/" + quote(str(schedule_id), safe=""))

    def retry(self, schedule_id):
        response = self.session.put("https://api.repliz.com/public/schedule/" + quote(str(schedule_id), safe="") + "/retry",
                                    json={}, auth=self.auth, timeout=25)
        response.raise_for_status()

    def reconcile(self, publication):
        """Adopt only an exact unique match; absence is not proof of non-submission."""
        when = datetime.fromisoformat(publication["scheduled_at"])
        matches = []
        for page in range(1, 21):
            raw = self.get("schedule", {"page": page, "limit": 100, "accountIds[]": publication["account_id"],
                "fromDate": (when - timedelta(minutes=1)).isoformat(), "toDate": (when + timedelta(minutes=1)).isoformat()})
            data = raw.get("data", raw)
            for item in data.get("docs", []):
                if matches_publication(item, publication):
                    matches.append(item)
            if not data.get("hasNextPage"):
                break
        else:
            raise ValueError("Daftar provider terlalu panjang untuk direkonsiliasi; periksa jadwal secara manual.")
        if len(matches) != 1:
            raise ValueError("Pengiriman belum dapat dipastikan. Tidak ada satu jadwal yang cocok persis; periksa provider sebelum mengulang.")
        item = matches[0]
        schedule_id = item.get("_id") or item.get("id")
        if not schedule_id:
            raise ValueError("Jadwal cocok tetapi ID provider belum tersedia.")
        return {**schedule_update(item), "schedule_id": schedule_id, "uncertain_submission": False, "error": None}

    def statistics(self, post_id, account_id):
        return self.get("content/" + quote(str(post_id), safe="") + "/statistic", {"accountId": account_id})

    def content(self, post_id, account_id):
        return self.get("content/" + quote(str(post_id), safe=""), {"accountId": account_id})


def matches_publication(item, publication):
    try:
        same_time = abs((datetime.fromisoformat(item["scheduleAt"].replace("Z", "+00:00")) - datetime.fromisoformat(publication["scheduled_at"])).total_seconds()) < 1
        return (same_time and str(item.get("accountId")) == str(publication["account_id"])
                and bool(publication.get("media_url"))
                and [m.get("url") for m in item.get("medias", [])] == [publication["media_url"]]
                and item.get("description", "") == publication.get("caption", ""))
    except (ValueError, KeyError, TypeError):
        return False


def schedule_update(raw):
    item = raw.get("data", raw) if isinstance(raw, dict) else {}
    status = {"pending": "scheduled", "process": "publishing", "error": "failed", "success": "published"}.get(item.get("status"))
    if status is None:
        return {"sync_error": "Status provider belum dikenali.", "last_synced_at": utc_now()}
    result = {"status": status, "provider_status": item.get("status"), "last_synced_at": utc_now(), "sync_error": None, "error": None}
    if item.get("postId"):
        result["post_id"] = item["postId"]
    if item.get("url") or item.get("postUrl"):
        result["post_url"] = item.get("postUrl") or item.get("url")
    if status == "failed":
        result["error"] = str(item.get("errorMessage") or item.get("error") or item.get("message") or "Provider gagal menerbitkan konten.")
    return result
