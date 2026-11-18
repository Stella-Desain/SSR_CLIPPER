"""Read public campaign data without executing website scripts or fetching assets.

Clippo currently embeds initialCampaign in Next.js Flight. This is a site adapter,
not a documented API: match the requested identity, resolve JSON/text references,
and fail visibly on incompatible schema changes. No browser dependency at runtime.
"""
from __future__ import annotations

import copy
import hashlib
from html.parser import HTMLParser
import json
import re
import threading
import time
from collections import OrderedDict
from datetime import datetime, timezone
from urllib.parse import urlsplit

ADAPTER_VERSION = 1
MAX_BYTES = 2 * 1024 * 1024
CACHE_SECONDS = 300
_CACHE = OrderedDict()
_LOCK = threading.RLock()
_PLATFORMS = {0: "tiktok", 1: "instagram"}  # Verified against public campaign labels.
_PUBLIC_FIELDS = {
    "id", "title", "minDuration", "maxDuration", "hashtags", "campaignTags",
    "campaignHook", "contentMainFocus", "contentPersona", "campaignPurpose",
    "notes", "ctaLabel", "campaignDos", "campaignDonts", "requirementsV2",
    "requirements", "agreements", "platformSupported", "languages", "guidelines",
    "assetVideoUrls", "assetVideoUrlsV2", "relevantLinks", "irrelevantLinks",
    "productLinks", "productLinkNames", "campaignVideoUrl", "imageUrl", "bannerUrl",
    "startDate", "endDate", "ratePer1K", "maxRewardPerBatch", "budgetPercentage", "status",
}


def campaign_url(value):
    if not isinstance(value, str) or len(value) > 4096:
        raise ValueError("Link campaign tidak valid")
    parsed = urlsplit(value.strip())
    if (parsed.scheme != "https" or parsed.hostname not in {"app.clippo.id", "clippo.id"}
            or parsed.username or parsed.password or parsed.port not in {None, 443}):
        raise ValueError("Gunakan link https://app.clippo.id/campaigns/…")
    match = re.fullmatch(r"/campaigns/([A-Za-z0-9_-]{8,100})/?", parsed.path)
    if not match:
        raise ValueError("Link harus menuju satu campaign Clippo, bukan halaman daftar")
    return f"https://app.clippo.id/campaigns/{match[1]}", match[1]


def public_link(value):
    if not isinstance(value, str) or len(value) > 4096:
        return ""
    try:
        parsed = urlsplit(value.strip())
        if parsed.scheme in {"http", "https"} and parsed.hostname and not parsed.username and not parsed.password:
            return value.strip()
    except ValueError:
        pass
    return ""


def normalize_source_links(items):
    if not isinstance(items, list) or len(items) > 100:
        raise ValueError("Daftar tautan materi campaign tidak valid (maksimal 100)")
    links = []
    for item in items:
        if not isinstance(item, dict) or not public_link(item.get("url")):
            raise ValueError("Tautan materi harus berupa URL HTTP/HTTPS yang valid")
        kind = item.get("kind", "asset")
        if kind not in {"asset", "guide", "product", "reference", "avoid_reference", "tutorial"}:
            raise ValueError("Jenis tautan campaign tidak dikenal")
        url = public_link(item["url"])
        link = {"id": hashlib.sha256((kind + url).encode()).hexdigest()[:20], "url": url,
                "kind": kind, "name": str(item.get("name") or url)[:300],
                "required": item.get("required") is True, "asset_id": str(item.get("asset_id") or "")[:200]}
        if not any(x["id"] == link["id"] for x in links):
            links.append(link)
    return links


class _HTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = {"tag": "root", "attrs": {}, "parts": []}
        self.stack = [self.root]
        self.scripts = []

    def handle_starttag(self, tag, attrs):
        node = {"tag": tag, "attrs": dict(attrs), "parts": []}
        self.stack[-1]["parts"].append(node)
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}:
            self.stack.append(node)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i]["tag"] == tag:
                if tag == "script":
                    self.scripts.append(self.stack[i])
                del self.stack[i:]
                break

    def handle_data(self, data):
        self.stack[-1]["parts"].append(data)


def _walk(node):
    yield node
    for part in node["parts"]:
        if isinstance(part, dict):
            yield from _walk(part)


def _text(node):
    if node["tag"] in {"script", "style", "svg"}:
        return ""
    value = "".join(_text(p) if isinstance(p, dict) else p for p in node["parts"])
    return value + ("\n" if node["tag"] in {"p", "div", "li", "br", "h1", "h2", "h3", "h4"} else "")


def rich_text(value):
    if isinstance(value, dict) and isinstance(value.get("ops"), list):
        # Quill embeds are data, never instructions or executable markup.
        value = "".join(op.get("insert", "") for op in value["ops"]
                        if isinstance(op, dict) and isinstance(op.get("insert"), str))
    if not isinstance(value, str):
        return ""
    parser = _HTML()
    parser.feed(value)
    return _text(parser.root).strip()


def _flight_records(scripts):
    chunks = []
    for script in scripts:
        raw = "".join(p for p in script["parts"] if isinstance(p, str))
        # Parse the JSON argument only. Never eval JavaScript from a remote page.
        for match in re.finditer(r"self\.__next_f\.push\(\s*", raw):
            try:
                chunk, _ = json.JSONDecoder().raw_decode(raw[match.end():])
                if isinstance(chunk, list) and len(chunk) == 2 and chunk[0] == 1 and isinstance(chunk[1], str):
                    chunks.append(chunk[1])
            except (ValueError, TypeError):
                continue
    data = "".join(chunks).encode("utf-8")
    records, pos = {}, 0
    while pos < len(data):
        head = re.match(rb"([0-9a-f]+):", data[pos:])
        if not head:
            end = data.find(b"\n", pos)
            pos = len(data) if end < 0 else end + 1
            continue
        key = head[1].decode()
        start = pos + head.end()
        text_header = re.match(rb"T([0-9a-f]+),", data[start:])
        if text_header:
            start += text_header.end()
            end = start + int(text_header[1], 16)  # Flight string length is UTF-8 bytes.
            if end > len(data):
                raise ValueError("Data teks campaign terpotong; muat ulang link")
            records[key] = data[start:end].decode("utf-8")
            pos = end
        else:
            end = data.find(b"\n", start)
            end = len(data) if end < 0 else end
            try:
                records[key] = json.loads(data[start:end])
            except (ValueError, UnicodeDecodeError):
                pass  # Module, suspense and other non-data records.
            pos = end + 1
    return records


def _resolve(value, records, seen=frozenset()):
    if isinstance(value, str) and re.fullmatch(r"\$[0-9a-f]+", value):
        key = value[1:]
        if key not in records or key in seen:
            raise ValueError("Referensi data campaign berubah atau tidak lengkap")
        return _resolve(records[key], records, seen | {key})
    if isinstance(value, dict):
        return {k: _resolve(v, records, seen) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve(v, records, seen) for v in value]
    return value


def _find_initial(value, campaign_id, records):
    if isinstance(value, dict):
        candidate = value.get("initialCampaign")
        if isinstance(candidate, str) and re.fullmatch(r"\$[0-9a-f]+", candidate):
            candidate = records.get(candidate[1:])
        if isinstance(candidate, dict) and candidate.get("id") == campaign_id:
            return candidate
        if isinstance(candidate, dict) and candidate.get("id"):
            raise ValueError("ID campaign halaman berbeda dari link yang diminta")
        for item in value.values():
            found = _find_initial(item, campaign_id, records)
            if found is not None:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _find_initial(item, campaign_id, records)
            if found is not None:
                return found
    return None


def parse_clippo(body, campaign_id):
    parser = _HTML()
    parser.feed(body)
    records = _flight_records(parser.scripts)
    candidate = None
    for value in records.values():
        candidate = _find_initial(value, campaign_id, records)
        if candidate is not None:
            break
    if candidate is None:
        for script in parser.scripts:
            if script["attrs"].get("id") == "__NEXT_DATA__":
                candidate = _find_initial(json.loads("".join(script["parts"])), campaign_id, records)
                if candidate is not None:
                    break
    sections = {n["attrs"]["data-section-id"]: n for n in _walk(parser.root)
                if n["attrs"].get("data-section-id")}
    if candidate is None and ("brief-campaign" not in sections or "do-and-dont" not in sections):
        raise ValueError("Halaman tidak menyediakan brief publik. Campaign mungkin perlu login, dihapus, atau format Clippo berubah.")
    general = []
    for node in _walk(sections.get("do-and-dont", {"tag": "root", "attrs": {}, "parts": []})):
        paragraphs = [p for p in node["parts"] if isinstance(p, dict) and p["tag"] == "p"]
        if len(paragraphs) == 2:
            general.append({"title": _text(paragraphs[0]).strip(), "description": _text(paragraphs[1]).strip()})
    if candidate is None:
        # The caller can use its existing AI extractor on scoped visible content.
        headings = [n for n in _walk(parser.root) if n["tag"] == "h1"]
        text = "\n".join([_text(n) for n in headings[:1]] + [_text(n) for n in sections.values()])
        return {"data": None, "general_rules": general, "brief_text": text[:120000], "method": "html_ai"}
    public = _resolve({k: v for k, v in candidate.items() if k in _PUBLIC_FIELDS}, records)
    if (not isinstance(public.get("title"), str) or not public["title"].strip()
            or not all(isinstance(public.get(k), (int, float)) and not isinstance(public[k], bool)
                       for k in ("minDuration", "maxDuration"))):
        raise ValueError("Schema campaign Clippo berubah; durasi/nama tidak valid. Isi brief manual sementara.")
    return {"data": public, "general_rules": general, "method": "embedded_json",
            "warnings": [] if general else ["Aturan umum halaman belum terbaca. Periksa halaman campaign sebelum produksi."]}


def fetch_clippo(value, *, refresh=False):
    import requests
    url, campaign_id = campaign_url(value)
    # Serialize identical UI requests; keep at most 32 small public snapshots.
    with _LOCK:
        cached = _CACHE.get(url)
        if cached and not refresh and time.monotonic() - cached[0] < CACHE_SECONDS:
            return {**copy.deepcopy(cached[1]), "cache_hit": True}
        headers = {"User-Agent": "SSR_CLIPPER/2 campaign-import", "Accept": "text/html"}
        if cached:
            headers.update(cached[2])
        try:
            with requests.get(url, headers=headers, timeout=(5, 20), stream=True, allow_redirects=False) as response:
                if response.status_code == 304 and cached:
                    page, validators = copy.deepcopy(cached[1]), cached[2]
                else:
                    if response.status_code in {301, 302, 303, 307, 308, 401, 403}:
                        raise ValueError("Clippo meminta login atau membatasi akses. Tidak ada data privat yang diambil; gunakan brief manual.")
                    if response.status_code == 404:
                        raise ValueError("Campaign Clippo tidak ditemukan")
                    response.raise_for_status()
                    if "text/html" not in response.headers.get("Content-Type", "").lower():
                        raise ValueError("Respons Clippo bukan halaman campaign HTML")
                    parts, size = [], 0
                    for chunk in response.iter_content(65536):
                        size += len(chunk)
                        if size > MAX_BYTES:
                            raise ValueError("Halaman campaign melebihi batas 2 MB")
                        parts.append(chunk)
                    page = parse_clippo(b"".join(parts).decode("utf-8"), campaign_id)
                    validators = {}
                    for name, header in (("ETag", "If-None-Match"), ("Last-Modified", "If-Modified-Since")):
                        if response.headers.get(name):
                            validators[header] = response.headers[name]
                    page.update({"url": url, "campaign_id": campaign_id, "adapter_version": ADAPTER_VERSION,
                                 "fetched_at": datetime.now(timezone.utc).isoformat()})
        except requests.RequestException as exc:
            raise ValueError("Campaign belum dapat diambil dari Clippo. Periksa koneksi lalu coba lagi.") from exc
        _CACHE[url] = (time.monotonic(), copy.deepcopy(page), validators)
        _CACHE.move_to_end(url)
        while len(_CACHE) > 32:
            _CACHE.popitem(last=False)
        return {**page, "cache_hit": False}


def map_clippo(page):
    data = page["data"]
    brief = {"durasi_min": data["minDuration"], "durasi_max": data["maxDuration"],
             "hashtags": data.get("hashtags", []), "tagged_accounts_by_platform": {"tiktok": [], "instagram": []},
             "hooks": rich_text(data.get("campaignHook")).splitlines(),
             "angles": rich_text(data.get("contentMainFocus")).splitlines(),
             "persona": rich_text(data.get("contentPersona")), "tujuan": rich_text(data.get("campaignPurpose")),
             "cta": rich_text(data.get("ctaLabel")),
             "catatan": "\n\n".join(filter(None, [rich_text(data.get("notes")), rich_text(data.get("requirementsV2") or data.get("requirements"))]))}
    for tag in data.get("campaignTags") or []:
        if isinstance(tag, dict) and tag.get("platform") in _PLATFORMS:
            brief["tagged_accounts_by_platform"][_PLATFORMS[tag["platform"]]] = tag.get("tags") or []
    brief["platforms"] = [_PLATFORMS[p] for p in data.get("platformSupported", []) if isinstance(p, int) and p in _PLATFORMS]
    extracted = {"name": data["title"], "source_platform": "Clippo", "brief": brief,
                 "do_rules": data.get("campaignDos", []), "dont_rules": data.get("campaignDonts", []),
                 "aturan_umum": page["general_rules"]}
    # Read explicit language labels; do not assume language from the site's locale.
    language = re.search(r"Languages?\s*:\s*(Indonesia|Indonesian|English)\b", brief["catatan"], re.I)
    if language:
        extracted["language"] = "en" if language[1].lower() == "english" else "id"
    links = []
    def add(url, kind, label="", required=False):
        url = public_link(url)
        if not url:
            return
        existing = next((x for x in links if x["url"] == url and x["kind"] == kind), None)
        if existing:
            existing["required"] |= required
            if label:
                existing["name"] = str(label)[:300]
            return
        links.append({"id": hashlib.sha256((kind + url).encode()).hexdigest()[:20], "url": url,
                      "kind": kind, "name": str(label or url)[:300], "required": bool(required), "asset_id": ""})
    for item in data.get("assetVideoUrlsV2") or []:
        if isinstance(item, dict):
            add(item.get("url"), "asset", item.get("displayText"), item.get("isRequired") is True)
    for url in data.get("assetVideoUrls") or []:
        add(url, "asset")
    for key, kind in (("guidelines", "guide"), ("productLinks", "product"), ("relevantLinks", "reference"), ("irrelevantLinks", "avoid_reference")):
        for url in data.get(key) or []:
            # Legacy guidelines duplicate source material, so retain one entry.
            if kind == "guide" and any(x["url"] == url for x in links):
                continue
            add(url, kind)
    add(data.get("campaignVideoUrl"), "tutorial", "Panduan campaign")
    text = json.dumps({"campaign": data, "aturan_umum": page["general_rules"]}, ensure_ascii=False)
    metadata = {k: page[k] for k in ("url", "campaign_id", "adapter_version", "method", "fetched_at") if k in page}
    metadata.update({"brief_text": text[:120000], "image_url": public_link(data.get("imageUrl")),
                     "commercial": {k: data[k] for k in ("startDate", "endDate", "ratePer1K", "maxRewardPerBatch", "budgetPercentage", "status") if k in data},
                     "unmapped_platforms": [p for p in data.get("platformSupported", []) if p not in _PLATFORMS]})
    metadata["warnings"] = page.get("warnings", [])
    return extracted, links, metadata
