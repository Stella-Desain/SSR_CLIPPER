# SPEC A — Repliz Storage Upload, AI Sound Selection & Create Schedule

**File yang diubah:** `app.py` SAJA
**PRASYARAT WAJIB:** SPEC B (`get_repliz_tiktok_music`) dan SPEC C (field `"transcript"` di data.json) HARUS SUDAH SELESAI dikerjakan sebelum spec ini. Spec ini akan MEMANGGIL keduanya.
**Sifat perubahan:** Ganti total isi class `ReplizUploaderAdapter` + ganti total isi method `confirm_distribution` + 1 baris kecil di `_upload_scheduler`.

---

## Kenapa spec ini perlu (baca dulu, jangan di-skip)

Saat ini, kalau user pencet tombol "Upload" di halaman Stock Clip:

1. `confirm_distribution()` cuma nulis status `"terjadwal"` ke `data.json` — TIDAK ada video yang beneran ke-upload kemana-mana saat itu.
2. Ada thread background (`_upload_scheduler`, jalan tiap 60 detik) yang NANTI, pas jam yang dijadwalkan tiba, manggil `api.upload_clip(...)`.
3. `upload_clip()` untuk platform `"repliz"` manggil `uploader.upload_video_to_storage(...)` dan `uploader.upload_to_repliz(...)` — **DUA METHOD INI TIDAK PERNAH ADA** di class `ReplizUploaderAdapter` (cuma ada `__init__`). Jadi setiap upload repliz PASTI gagal dengan `AttributeError`.

Spec ini benerin itu semua SEKALIGUS, dan menggabungkannya dengan pemilihan musik AI, dengan cara:
- Bikin `ReplizUploaderAdapter` beneran bisa upload file (pakai Repliz Storage API 3-langkah) dan bikin scheduled post (pakai Repliz Schedule API, yang juga support attach musik TikTok resmi).
- Proses ini dijalankan **LANGSUNG saat user pencet tombol Upload** (di dalam `confirm_distribution()`), BUKAN nunggu `_upload_scheduler` nanti. `scheduled_at` cukup dikirim ke Repliz — Repliz sendiri yang nanti publish di waktu yang tepat, SSR_CLIPPER gak perlu nyala terus.

---

## TASK 1 — Ganti isi class `ReplizUploaderAdapter`

Cari blok ini di `app.py` (sekitar baris 55-59), PERSIS seperti ini:

```python
class ReplizUploaderAdapter:
    def __init__(self, access_key, secret_key):
        self.access_key = access_key
        self.secret_key = secret_key
```

GANTI TOTAL jadi ini (nambah 2 method baru, `__init__` tetap sama):

```python
class ReplizUploaderAdapter:
    def __init__(self, access_key, secret_key):
        self.access_key = access_key
        self.secret_key = secret_key

    def upload_video_to_storage(self, file_path):
        """Upload file video ke Repliz Storage pakai 3-step flow resmi:
        Init File -> PUT ke presigned URL -> Complete File.

        Returns:
            str: public URL file (dari field 'url' response Init), kalau sukses
            None: kalau gagal di step manapun
        """
        import requests
        from requests.auth import HTTPBasicAuth
        import os
        try:
            auth = HTTPBasicAuth(self.access_key, self.secret_key)
            filename = os.path.basename(file_path)
            size = os.path.getsize(file_path)
            mimetype = "video/mp4"

            # Step 1: Init File
            init_res = requests.post(
                "https://api.repliz.com/public/storage/file/init",
                json={"filename": filename, "size": size, "mimetype": mimetype},
                auth=auth,
                timeout=30
            )
            if init_res.status_code != 200:
                return None
            init_data = init_res.json()
            file_id = init_data.get("id")
            upload_url = init_data.get("upload")
            public_url = init_data.get("url")
            if not file_id or not upload_url or not public_url:
                return None

            # Step 2: PUT raw binary ke presigned URL
            with open(file_path, "rb") as f:
                put_res = requests.put(
                    upload_url,
                    data=f,
                    headers={"Content-Type": mimetype},
                    timeout=300
                )
            if put_res.status_code not in (200, 201, 204):
                return None

            # Step 3: Complete File
            complete_res = requests.post(
                f"https://api.repliz.com/public/storage/file/{file_id}/complete",
                auth=auth,
                timeout=30
            )
            if complete_res.status_code != 200:
                return None

            return public_url
        except Exception:
            return None

    def create_schedule(self, account_id, title, description, media_url, schedule_at_iso, music=None):
        """Buat scheduled post video lewat POST /public/schedule.

        Args:
            account_id: ID akun Repliz tujuan
            title: judul (dipakai platform tertentu, boleh string kosong)
            description: caption post
            media_url: URL video hasil upload_video_to_storage()
            schedule_at_iso: string ISO 8601, format "YYYY-MM-DDTHH:MM:SS.000Z"
            music: dict {"id","artist","name","thumbnail"} ATAU None kalau gak ada musik

        Returns:
            (True, schedule_id) kalau sukses
            (False, error_message) kalau gagal
        """
        import requests
        from requests.auth import HTTPBasicAuth
        try:
            auth = HTTPBasicAuth(self.access_key, self.secret_key)
            music_obj = music if music else {"id": "", "artist": "", "name": "", "thumbnail": ""}
            body = {
                "title": title or "",
                "description": description or "",
                "topic": "",
                "type": "video",
                "medias": [{
                    "alt": "",
                    "customThumbnail": False,
                    "type": "video",
                    "thumbnail": "",
                    "url": media_url
                }],
                "meta": {"title": "", "description": "", "url": ""},
                "additionalInfo": {
                    "isAiGenerated": False,
                    "isDraft": False,
                    "isAutoAddMusic": False,
                    "collaborators": [],
                    "mentions": [],
                    "music": music_obj,
                    "products": [],
                    "tags": []
                },
                "replies": [],
                "accountId": account_id,
                "scheduleAt": schedule_at_iso
            }
            res = requests.post(
                "https://api.repliz.com/public/schedule",
                json=body,
                auth=auth,
                timeout=30
            )
            if res.status_code == 200:
                return True, res.json().get("scheduleId", "")
            else:
                try:
                    msg = res.json().get("message", f"HTTP {res.status_code}")
                except Exception:
                    msg = f"HTTP {res.status_code}"
                return False, msg
        except Exception as e:
            return False, str(e)
```

---

## TASK 2 — Tambah method `_select_background_sound` di class `WebAPI`

Tambahkan method baru ini di manapun di dalam class `WebAPI` (misal: taruh persis sebelum method `confirm_distribution`). Method ini yang jadi "AI" pemilih musik:

```python
    def _select_background_sound(self, transcript, title, hook_text, tracks):
        """AI pilih 1 track trending paling cocok buat 1 clip, berdasarkan isi clip.

        Args:
            transcript: potongan transcript clip (dari data.json, field "transcript")
            title: judul clip
            hook_text: hook clip
            tracks: list track dari get_repliz_tiktok_music() -> tracks

        Returns:
            dict {"id","artist","name","thumbnail"} kalau AI berhasil pilih 1 track valid
            None kalau gagal / tidak ada track cocok / API key belum diset
        """
        if not tracks:
            return None
        try:
            cfg = self._get_cfg()
            provider = cfg.get("ai_providers", {}).get("highlight_finder", {})
            api_key = provider.get("api_key")
            base_url = provider.get("base_url")
            model = provider.get("model")
            if not api_key:
                return None

            track_list_text = "\n".join(
                f'- id="{t["id"]}" | "{t.get("name","")}" by {t.get("artist","")}'
                for t in tracks[:20] if t.get("id")
            )
            if not track_list_text:
                return None

            from openai import OpenAI
            client = OpenAI(api_key=api_key, base_url=base_url)
            messages = [
                {"role": "system", "content": (
                    'Kamu memilih 1 lagu trending TikTok yang paling cocok jadi backsound '
                    'untuk sebuah clip video, berdasarkan isi/mood clip tersebut. '
                    'HANYA balas JSON persis format ini, tanpa teks lain: {"id": "..."}\n'
                    'id HARUS persis salah satu id dari daftar yang diberikan. '
                    'Kalau tidak ada yang cocok sama sekali, balas {"id": ""}.'
                )},
                {"role": "user", "content": (
                    f"Judul clip: {title}\n"
                    f"Hook: {hook_text}\n"
                    f"Transcript clip: {(transcript or '')[:1500]}\n\n"
                    f"Daftar lagu trending:\n{track_list_text}"
                )}
            ]
            response = client.chat.completions.create(model=model, messages=messages, temperature=0.3)
            raw = response.choices[0].message.content.strip()
            if raw.startswith("```json"):
                raw = raw[7:]
            if raw.endswith("```"):
                raw = raw[:-3]
            picked = json.loads(raw.strip())
            picked_id = picked.get("id")
            if not picked_id:
                return None
            for t in tracks:
                if t.get("id") == picked_id:
                    return {"id": t["id"], "artist": t.get("artist", ""), "name": t.get("name", ""), "thumbnail": t.get("thumbnail", "")}
            return None
        except Exception:
            return None
```

> Method ini SENGAJA pakai konfigurasi AI provider `"highlight_finder"` yang SUDAH ADA di Settings (yang sama dipakai buat cari highlight clip) — supaya user gak perlu setting API key baru lagi. JANGAN bikin field Settings baru untuk ini.

---

## TASK 3 — Ganti total isi method `confirm_distribution`

Cari method ini di `app.py` (PERSIS seperti ini sekarang):

```python
    def confirm_distribution(self, assignments):
        """Menerima hasil preview dan memperbarui metadata data.json."""
        import uuid
        from datetime import datetime
        
        updated_clips = 0
        try:
            # We need to find data.json for each clip.
            # Clip path can be found in `get_stock_clips()`
            all_clips = self.get_stock_clips()
            clip_path_map = {c["id"]: c["path"] for c in all_clips}
            
            for asn in assignments:
                clip_id = asn.get("clip_id")
                clip_path_str = clip_path_map.get(clip_id) or asn.get("clip_path")
                if not clip_path_str:
                     continue
                     
                clip_path = Path(clip_path_str)
                data_json_path = clip_path.parent / "data.json"
                
                # Coba baca data.json
                if not data_json_path.exists():
                     # Fallback to parent dir if it's legacy
                     data_json_path = clip_path.parent.parent / "data.json"
                     if not data_json_path.exists():
                         continue

                with open(data_json_path, 'r', encoding='utf-8') as f:
                     cdata = json.load(f)
                     
                cdata["upload_status"] = "terjadwal"
                if "scheduled_uploads" not in cdata:
                     cdata["scheduled_uploads"] = []
                     
                caption = self._build_caption(asn.get("campaign_id"))
                cdata["scheduled_uploads"].append({
                    "id": f"sched_{uuid.uuid4().hex[:8]}",
                    "campaign_id": asn.get("campaign_id", ""),
                    "account_id": asn.get("account_id"),
                    "platform": asn.get("platform", "repliz"),
                    "scheduled_at": asn.get("scheduled_at"),
                    "status": "terjadwal",
                    "attempted_at": None,
                    "error_message": None,
                    "caption": caption
                })
                
                with open(data_json_path, 'w', encoding='utf-8') as f:
                     json.dump(cdata, f, indent=2, ensure_ascii=False)
                     
                updated_clips += 1
                
            return {"status": "ok", "message": f"{updated_clips} clips scheduled"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
```

GANTI TOTAL (dari `def confirm_distribution` sampai `return {"status": "error", "message": str(e)}` di akhirnya) jadi:

```python
    def confirm_distribution(self, assignments):
        """Menerima hasil preview: upload video ke Repliz Storage, pilih background
        sound pakai AI, lalu buat scheduled post lewat Repliz Schedule API.
        Update data.json dengan hasil akhirnya (sukses/gagal), bukan cuma status lokal."""
        import uuid
        from datetime import datetime

        updated_clips = 0
        cfg = self._get_cfg()
        repliz_cfg = cfg.get("repliz", {})
        access_key = repliz_cfg.get("access_key")
        secret_key = repliz_cfg.get("secret_key")

        # Ambil daftar musik trending SEKALI untuk semua clip di batch upload ini
        music_tracks = []
        if access_key and secret_key:
            music_res = self.get_repliz_tiktok_music()
            if music_res.get("status") == "ok":
                music_tracks = music_res.get("tracks", [])

        try:
            all_clips = self.get_stock_clips()
            clip_path_map = {c["id"]: c["path"] for c in all_clips}

            for asn in assignments:
                clip_id = asn.get("clip_id")
                clip_path_str = clip_path_map.get(clip_id) or asn.get("clip_path")
                if not clip_path_str:
                     continue

                clip_path = Path(clip_path_str)
                data_json_path = clip_path.parent / "data.json"

                if not data_json_path.exists():
                     data_json_path = clip_path.parent.parent / "data.json"
                     if not data_json_path.exists():
                         continue

                with open(data_json_path, 'r', encoding='utf-8') as f:
                     cdata = json.load(f)

                caption = self._build_caption(asn.get("campaign_id"))
                platform = asn.get("platform", "repliz")

                entry = {
                    "id": f"sched_{uuid.uuid4().hex[:8]}",
                    "campaign_id": asn.get("campaign_id", ""),
                    "account_id": asn.get("account_id"),
                    "platform": platform,
                    "scheduled_at": asn.get("scheduled_at"),
                    "status": "terjadwal",
                    "attempted_at": None,
                    "error_message": None,
                    "caption": caption
                }

                if platform == "repliz":
                    entry["attempted_at"] = datetime.now().isoformat()
                    if not access_key or not secret_key:
                        entry["status"] = "gagal"
                        entry["error_message"] = "Repliz keys not configured"
                    else:
                        uploader = ReplizUploaderAdapter(access_key, secret_key)
                        media_url = uploader.upload_video_to_storage(str(clip_path))
                        if not media_url:
                            entry["status"] = "gagal"
                            entry["error_message"] = "Gagal upload video ke Repliz Storage"
                        else:
                            music = None
                            if music_tracks:
                                music = self._select_background_sound(
                                    cdata.get("transcript", ""),
                                    cdata.get("title", ""),
                                    cdata.get("hook_text", ""),
                                    music_tracks
                                )
                            if music:
                                entry["music_attached"] = {
                                    "id": music["id"], "name": music["name"], "artist": music["artist"]
                                }

                            try:
                                sched_dt = datetime.fromisoformat(asn.get("scheduled_at"))
                                schedule_at_iso = sched_dt.strftime('%Y-%m-%dT%H:%M:%S.000Z')
                            except Exception:
                                schedule_at_iso = datetime.now().strftime('%Y-%m-%dT%H:%M:%S.000Z')

                            success, result = uploader.create_schedule(
                                account_id=asn.get("account_id"),
                                title=cdata.get("title", ""),
                                description=caption,
                                media_url=media_url,
                                schedule_at_iso=schedule_at_iso,
                                music=music
                            )
                            if success:
                                entry["status"] = "sukses"
                                entry["repliz_schedule_id"] = result
                            else:
                                entry["status"] = "gagal"
                                entry["error_message"] = result

                if "scheduled_uploads" not in cdata:
                     cdata["scheduled_uploads"] = []
                cdata["scheduled_uploads"].append(entry)

                statuses = [e.get("status") for e in cdata["scheduled_uploads"]]
                if "uploading" in statuses:
                    cdata["upload_status"] = "uploading"
                elif "terjadwal" in statuses:
                    cdata["upload_status"] = "terjadwal"
                elif "gagal" in statuses:
                    cdata["upload_status"] = "gagal"
                else:
                    cdata["upload_status"] = "sukses"

                with open(data_json_path, 'w', encoding='utf-8') as f:
                     json.dump(cdata, f, indent=2, ensure_ascii=False)

                updated_clips += 1

            return {"status": "ok", "message": f"{updated_clips} clips scheduled"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
```

**Catatan penting soal alur user (biar konteksnya jelas):** Saat user pencet tombol "Upload" di Stock Clip → `quick_upload()` (SUDAH ADA, JANGAN DIUBAH) manggil `preview_distribution()` lalu `confirm_distribution()`. Dengan perubahan di atas, `confirm_distribution()` INI YANG langsung upload+pilih musik+buat jadwal ke Repliz, semua di background thread yang sudah ada (pywebview call ini otomatis async dari sisi JS, jadi UI gak freeze). Status akhirnya ("sukses"/"gagal") langsung kebaca oleh `get_clip_upload_status_summary()` yang sudah dipakai frontend — TIDAK PERLU ubah apapun di frontend/JS.

---

## TASK 4 — Cegah double-processing di `_upload_scheduler`

Cari fungsi module-level `_upload_scheduler(api)` di `app.py` (di luar class `WebAPI`, di bagian bawah file). Di dalamnya cari baris PERSIS ini:

```python
                for entry in scheduled_uploads:
                    if entry.get("status") == "terjadwal":
```

Ganti jadi:

```python
                for entry in scheduled_uploads:
                    if entry.get("status") == "terjadwal" and entry.get("platform") != "repliz":
```

Ini cuma jaga-jaga: dengan perubahan TASK 3, entry `platform: "repliz"` HARUSNYA gak pernah lagi nyangkut di status `"terjadwal"` lebih dari sedetik (langsung jadi "sukses"/"gagal" oleh `confirm_distribution`), tapi baris ini mencegah scheduler lama nyoba proses ulang entry repliz kalau ada skenario aneh.

---

## ATURAN KETAT — JANGAN LAKUKAN INI

- JANGAN ubah `quick_upload()`, `preview_distribution()`, `get_stock_clips()`, `_build_caption()` — semua ini tetap dipakai APA ADANYA.
- JANGAN ubah apapun di frontend (`web/`). Semua perubahan ini backend-only, transparan buat UI yang sudah ada.
- JANGAN hapus/ubah cabang `platform == "tiktok"` atau `platform == "youtube"` di method `upload_clip()` (kalau ada) — itu di luar scope spec ini, biarkan apa adanya.
- Kalau `music_tracks` kosong (gagal fetch, atau API key premium gak aktif) — proses upload+schedule HARUS TETAP JALAN tanpa musik (`music=None` → jadi object kosong di payload), BUKAN gagal total. Attach musik itu bonus, bukan syarat wajib video ke-upload.
- Kalau `_select_background_sound` return `None` (AI gagal milih / gak ada API key) — sama, upload+schedule tetap jalan tanpa musik.

---

## Cara Test

1. Pastikan Repliz Access/Secret Key valid di Settings, dan minimal 1 akun TikTok terhubung di Repliz.
2. Generate 1 video (pastikan SPEC C sudah aktif, jadi `data.json` clip punya field `"transcript"` terisi).
3. Ke halaman Stock Clip, pilih 1 clip, pencet Upload.
4. Cek `data.json` clip tersebut: harus ada entry baru di `scheduled_uploads` dengan `status: "sukses"` dan ada `repliz_schedule_id`. Kalau ada musik yang berhasil dipilih AI, harus ada `music_attached`.
5. Cek dashboard/inbox Repliz (repliz.com) — harus muncul scheduled post baru dengan video yang sesuai, dan (kalau AI berhasil pilih musik) musik ter-attach.
6. Test skenario gagal: kosongkan Secret Key di Settings, pencet Upload lagi — harus dapat `status: "gagal"` dengan `error_message` yang jelas, BUKAN crash aplikasi.
7. Test skenario gagal-storage: pakai Access/Secret Key yang salah — pastikan gagal dengan rapi di step upload storage, bukan lanjut ke create_schedule dengan `media_url=None`.
