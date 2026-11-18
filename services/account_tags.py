"""Campaign account mentions scoped to the destination's social platform."""
import re

from .additionals import ADDITIONAL_PLATFORMS, platform_key


def normalize_account_tags(brief):
    """Legacy shared mentions become visible in both editors, without losing data."""
    if "tagged_accounts_by_platform" not in brief:
        shared = brief.get("tagged_accounts", [])
        raw = {platform: shared for platform in ADDITIONAL_PLATFORMS}
    else:
        raw = brief["tagged_accounts_by_platform"]
    if not isinstance(raw, dict) or set(raw) - set(ADDITIONAL_PLATFORMS):
        raise ValueError("Tag akun harus dipisahkan untuk TikTok dan Instagram.")
    result = {}
    for platform in ADDITIONAL_PLATFORMS:
        values = raw.get(platform, [])
        if not isinstance(values, list) or len(values) > 100 or any(not isinstance(v, str) for v in values):
            raise ValueError("Tag akun harus berupa daftar teks, maksimal 100 akun per sosmed.")
        mentions, seen = [], set()
        for value in values:
            value = value.strip()
            if not value:
                continue
            if len(value) > 200 or any(c.isspace() for c in value) or "," in value:
                raise ValueError("Pisahkan tag akun dengan koma; satu tag tidak boleh berisi spasi.")
            value = value if value.startswith("@") else "@" + value
            if value == "@":
                raise ValueError("Lengkapi nama akun sesudah @.")
            if value.casefold() not in seen:
                mentions.append(value)
                seen.add(value.casefold())
        result[platform] = mentions
    return result


def tags_for_platform(brief, platform):
    scoped = brief.get("tagged_accounts_by_platform")
    if isinstance(scoped, dict):
        return scoped.get(platform_key(platform), [])
    # Existing reviewed clips retain their original shared-tag behavior.
    return brief.get("tagged_accounts", [])


def caption_has_term(caption, term):
    end = r"(?![\w.])" if term.startswith("@") else r"(?!\w)"
    return bool(re.search(r"(?<!\w)" + re.escape(term) + end, caption, re.IGNORECASE))


def append_mentions(caption, mentions):
    missing = [term for term in mentions if not caption_has_term(caption, term)]
    return "\n\n".join(part for part in (caption.strip(), " ".join(missing)) if part)


def publication_caption(clip, platform):
    key = platform_key(platform)
    override = (clip.get("captions") or {}).get(key)
    if override and override.strip():
        return override
    brief = (clip.get("campaign_snapshot") or {}).get("brief", {})
    return append_mentions(clip.get("caption", ""), tags_for_platform(brief, key))


def platform_captions(base, brief):
    if "tagged_accounts_by_platform" not in brief:
        return append_mentions(base, brief.get("tagged_accounts", [])), {}
    tags = normalize_account_tags(brief)
    return base, {platform: append_mentions(base, mentions) for platform, mentions in tags.items()} if any(tags.values()) else {}
