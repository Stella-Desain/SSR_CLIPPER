# FIX — Repliz Storage Upload SELALU "Gagal" Padahal File Sudah Ke-upload

**File yang diubah:** `app.py` SAJA (4 lokasi, 1 class + 3 method)
**Kamu (eksekutor) TIDAK PERLU memutuskan logic apapun.** Semua sudah didesain di bawah — cari blok kode PERSIS seperti yang ditulis, ganti PERSIS dengan yang disediakan. Kalau blok yang kamu temukan di file TIDAK PERSIS sama dengan "Kode SEKARANG" di bawah (beda walau cuma 1 karakter/spasi), STOP dan laporkan — jangan dipaksakan.
**Sumber kebenaran teknis:** Dokumentasi resmi Repliz — https://docs.repliz.com/api/storage/complete-file.html dan https://docs.repliz.com/api/guides/storage-upload.html (dikutip persis di TASK 1).

---

## Ringkasan Temuan

| # | Bug | Lokasi (`app.py`) | Prioritas | Wajib bareng? |
|---|-----|--------------------|-----------|----------------|
| 1 | Step 3 (`Complete File`) cek `status_code != 200`, padahal API resmi Repliz balikin **HTTP 204 No Content** kalau sukses (BUKAN 200) | `class ReplizUploaderAdapter.upload_video_to_storage()` | 🔴 KRITIS — **INI AKAR MASALAH "gagal upload ke storage"** | TASK 1+2+3 satu paket |
| 2 | Semua error di 3 step upload storage dibuang diam-diam (`return None`), gak ada info step mana / alasan apa | Method yang sama | 🟠 TINGGI — bikin gak bisa didiagnosis | TASK 1+2+3 satu paket |
| 3 | `_upload_scheduler()` manggil `upload_video_to_storage()` juga → HARUS ikut update return-nya | `def upload_clip()` cabang `elif platform == "repliz":` | 🟢 wajib ikut TASK 1 | TASK 1+2+3 satu paket |
| 4 | Guard `entry.get("platform") != "repliz"` gak akan pernah `False` (field `platform` isinya `"tiktok"`/`"instagram"` dst, bukan literal `"repliz"`) | `def _upload_scheduler(api)` | 🟡 SEDANG (laten, soal data lama) | Independen, boleh terpisah |

---

## Kenapa Bug #1 & #2 terjadi (baca dulu, penting buat kamu ngerti konteksnya)

Repliz Storage API pakai flow 3 langkah: **Init File → PUT ke presigned URL → Complete File**.

Dokumentasi resmi Complete File (https://docs.repliz.com/api/storage/complete-file.html) bilang respons SUKSES-nya begini:

```
Response: 204
// No content returned on success
```

Tapi kode `app.py` SEKARANG nulis:

```python
complete_res = requests.post(
    f"https://api.repliz.com/public/storage/file/{file_id}/complete",
    auth=auth,
    timeout=30
)
if complete_res.status_code != 200:
    return None
```

Karena API selalu balikin **204**, dan kode ini cuma nerima **200**, kondisi `!= 200` ini SELALU `True` — jadi fungsi SELALU `return None` di step 3, **PADAHAL file-nya sudah 100% berhasil ke-upload dan sudah di-mark selesai/success di sisi Repliz**. Ini kenapa toast selalu bilang "Gagal upload video ke Repliz Storage" walau sebenarnya prosesnya sukses total — cuma kode yang salah baca sinyal suksesnya.

Ditambah lagi, di ketiga step (Init, PUT, Complete), setiap kegagalan cuma `return None` tanpa bawa info kenapa gagal (bisa jadi kuota storage penuh → Repliz balikin `{"code": 429, "message": "upgrade to get more storage"}` per dokumentasi Init File, bisa juga key salah, bisa juga network error di step PUT) — makanya pesan yang user lihat SELALU sama persis: *"Gagal upload video ke Repliz Storage"*, gak peduli akar masalahnya apa.

---

## TASK 1 — Ganti isi method `upload_video_to_storage` di class `ReplizUploaderAdapter`

Cari blok ini di `app.py` (dalam class `ReplizUploaderAdapter`, sekitar baris 60-115), PERSIS seperti ini:

```python
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
```

GANTI TOTAL jadi ini:

```python
    def upload_video_to_storage(self, file_path):
        """Upload file video ke Repliz Storage pakai 3-step flow resmi:
        Init File -> PUT ke presigned URL -> Complete File.

        Returns:
            (True, public_url)      kalau sukses
            (False, error_message)  kalau gagal di step manapun — error_message berisi
                                     alasan SPESIFIK (HTTP code + pesan dari Repliz kalau ada),
                                     bukan pesan generik.
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
                try:
                    msg = init_res.json().get("message", f"HTTP {init_res.status_code}")
                except Exception:
                    msg = f"HTTP {init_res.status_code}"
                return False, f"Init File gagal: {msg}"
            init_data = init_res.json()
            file_id = init_data.get("id")
            upload_url = init_data.get("upload")
            public_url = init_data.get("url")
            if not file_id or not upload_url or not public_url:
                return False, "Init File gagal: response tidak lengkap (id/upload/url kosong)"

            # Step 2: PUT raw binary ke presigned URL
            with open(file_path, "rb") as f:
                put_res = requests.put(
                    upload_url,
                    data=f,
                    headers={"Content-Type": mimetype},
                    timeout=300
                )
            if put_res.status_code not in (200, 201, 204):
                return False, f"Upload ke presigned URL gagal: HTTP {put_res.status_code}"

            # Step 3: Complete File
            # PENTING: endpoint ini balikin HTTP 204 No Content kalau SUKSES (BUKAN 200!).
            # Sumber: https://docs.repliz.com/api/storage/complete-file.html
            # Bug lama di sini cuma nerima 200, padahal API selalu balikin 204,
            # jadi upload SELALU dianggap gagal walau sebenarnya sudah sukses.
            complete_res = requests.post(
                f"https://api.repliz.com/public/storage/file/{file_id}/complete",
                auth=auth,
                timeout=30
            )
            if complete_res.status_code not in (200, 204):
                try:
                    msg = complete_res.json().get("message", f"HTTP {complete_res.status_code}")
                except Exception:
                    msg = f"HTTP {complete_res.status_code}"
                return False, f"Complete File gagal: {msg}"

            return True, public_url
        except Exception as e:
            return False, f"Exception saat upload ke storage: {str(e)}"
```

---

## TASK 2 — Update pemanggil di `confirm_distribution()` (WAJIB, satu paket sama TASK 1)

TASK 1 mengubah return value `upload_video_to_storage()` dari `str atau None` menjadi tuple `(True, url)` / `(False, pesan_error)`. SEMUA pemanggil method ini WAJIB ikut diupdate, kalau tidak nanti `media_url` isinya tuple (selalu truthy) dan logic-nya salah total.

Cari blok ini di method `confirm_distribution()` (sekitar baris 1910-1914), PERSIS seperti ini:

```python
                    uploader = ReplizUploaderAdapter(access_key, secret_key)
                    media_url = uploader.upload_video_to_storage(str(clip_path))
                    if not media_url:
                        entry["status"] = "gagal"
                        entry["error_message"] = "Gagal upload video ke Repliz Storage"
                    else:
```

GANTI jadi:

```python
                    uploader = ReplizUploaderAdapter(access_key, secret_key)
                    storage_ok, storage_result = uploader.upload_video_to_storage(str(clip_path))
                    if not storage_ok:
                        entry["status"] = "gagal"
                        entry["error_message"] = storage_result
                    else:
                        media_url = storage_result
```

**PENTING:** Baris-baris SETELAH `else:` ini (mulai dari `music = None` sampai akhir blok, yang manggil `create_schedule(...)` pakai `media_url`) **TIDAK DIUBAH SAMA SEKALI** — biarkan apa adanya, karena variabel `media_url` sekarang didefinisikan oleh baris baru `media_url = storage_result` yang barusan ditambahkan tepat di bawah `else:`.

---

## TASK 3 — Update pemanggil "mati" di `upload_clip()` (WAJIB, satu paket sama TASK 1)

Cabang ini di method `upload_clip()` SAAT INI tidak pernah benar-benar kepanggil di alur normal aplikasi (upload Repliz sekarang diproses langsung oleh `confirm_distribution()`, bukan lewat `upload_clip()`). TAPI dia masih manggil method `uploader.upload_to_repliz(...)` yang **TIDAK PERNAH ADA** di class `ReplizUploaderAdapter` — kalau cabang ini suatu saat kepanggil (termasuk gara-gara TASK 4 di bawah), dia bakal crash `AttributeError`. Sekalian dibenerin di sini, plus disesuaikan sama return value baru dari TASK 1.

Cari blok ini di method `upload_clip()`, di dalam `elif platform == "repliz":` (sekitar baris 1610-1624), PERSIS seperti ini:

```python
            try:
                title = kwargs.get("title", Path(clip_path).stem)
                desc = kwargs.get("description", "")
                
                vid_url = uploader.upload_video_to_storage(clip_path)
                if not vid_url:
                     return {"status": "error", "message": "Failed to upload video to storage"}
                     
                success, msg = uploader.upload_to_repliz(account_id, title, desc, vid_url)
                if success:
                     return {"status": "success", "message": msg}
                else:
                     return {"status": "error", "message": msg}
            except Exception as e:
                return {"status": "error", "message": str(e)}
```

GANTI jadi:

```python
            try:
                title = kwargs.get("title", Path(clip_path).stem)
                desc = kwargs.get("description", "")

                storage_ok, storage_result = uploader.upload_video_to_storage(clip_path)
                if not storage_ok:
                     return {"status": "error", "message": storage_result}
                vid_url = storage_result

                schedule_ok, schedule_result = uploader.create_schedule(
                    account_id=account_id,
                    title=title,
                    description=desc,
                    media_url=vid_url,
                    schedule_at_iso=datetime.now().strftime('%Y-%m-%dT%H:%M:%S.000Z')
                )
                if schedule_ok:
                     return {"status": "success", "message": f"Scheduled, id={schedule_result}"}
                else:
                     return {"status": "error", "message": schedule_result}
            except Exception as e:
                return {"status": "error", "message": str(e)}
```

Catatan: `datetime` TIDAK PERLU di-import baru — sudah ada `from datetime import datetime` di baris paling atas `app.py` (baris 11), jadi langsung bisa dipakai.

---

## TASK 4 — Nonaktifkan guard scheduler yang salah logic (independen, boleh dikerjakan terpisah dari TASK 1-3)

### Kenapa

`preview_distribution()` ngisi field `platform` tiap assignment dari `candidate.get("type", "repliz")` — dan `candidate` itu akun dari Repliz (`get_repliz_accounts()`), field `type`-nya berisi JENIS AKUN SOSIAL (`"tiktok"`, `"instagram"`, dst — nilai asli dari API Repliz), **BUKAN PERNAH literal string `"repliz"`**. Jadi field `entry["platform"]` di `scheduled_uploads` isinya SELALU sesuatu seperti `"tiktok"`, tidak pernah persis `"repliz"`.

Di `_upload_scheduler()` ada baris:

```python
                for entry in scheduled_uploads:
                    if entry.get("status") == "terjadwal" and entry.get("platform") != "repliz":
```

Kondisi `entry.get("platform") != "repliz"` ini **SELALU `True`** (karena `platform` emang gak pernah persis `"repliz"`), padahal maksud aslinya adalah SKIP entry yang sudah ditangani Repliz. Efeknya: kalau ada entry yang nyangkut di status `"terjadwal"` (misal data lama sebelum fix-fix sebelumnya diterapkan), scheduler ini bakal salah rute — manggil `upload_clip()` dengan platform asli (misal `"tiktok"`), yang bakal masuk ke cabang `TikTokUploader` NATIVE (OAuth TikTok App terpisah, BUKAN Repliz) — sistem yang kemungkinan besar TIDAK PERNAH dikonfigurasi user yang pakai Repliz. Hasilnya: error membingungkan `"Kredensial TikTok belum diisi di Settings"` yang gak ada hubungannya sama Repliz sama sekali.

**Fakta kunci:** semua entry `scheduled_uploads` di aplikasi ini SEKARANG dibuat SATU-SATUNYA oleh `confirm_distribution()`, dan `confirm_distribution()` SELALU langsung meng-update status jadi `"sukses"` atau `"gagal"` di eksekusi yang sama (tidak pernah membiarkan status `"terjadwal"` menggantung). Jadi loop retry di `_upload_scheduler()` ini sebenarnya sudah gak relevan lagi untuk arsitektur sekarang — dia cuma perlu dijaga supaya TIDAK PERNAH jalan (bukan dihapus, biar gampang direstore kalau nanti ada kebutuhan platform non-Repliz lagi).

### Fix

Cari baris ini di fungsi module-level `_upload_scheduler(api)` (di luar class `WebAPI`, di bagian bawah `app.py`), PERSIS seperti ini:

```python
                for entry in scheduled_uploads:
                    if entry.get("status") == "terjadwal" and entry.get("platform") != "repliz":
```

GANTI jadi:

```python
                for entry in scheduled_uploads:
                    # Semua entry sekarang dibuat & langsung diselesaikan (sukses/gagal) oleh
                    # confirm_distribution() lewat Repliz — gak pernah ada lagi entry yang perlu
                    # diproses ulang di sini. Kondisi lama `entry.get("platform") != "repliz"`
                    # SELALU True (field platform isinya "tiktok"/dst, bukan literal "repliz"),
                    # jadi blok ini salah-rute entry lama ke uploader native yang gak dikonfigurasi.
                    # Sengaja dinonaktifkan total (bukan dihapus) sebagai jaring pengaman.
                    if False:
```

**JANGAN ubah baris apapun setelah ini di dalam fungsi** — semua kode di bawah `if False:` (isi loop) tetap sama persis, cuma sekarang gak akan pernah dieksekusi.

---

## ATURAN KETAT — JANGAN LAKUKAN INI

- JANGAN ubah `create_schedule()`, `_select_background_sound()`, `get_repliz_accounts()`, `get_repliz_tiktok_music()`, `preview_distribution()`, `get_stock_clips()`, `_build_caption()`, `quick_upload()` — semua ini SUDAH BENAR, jangan disentuh.
- JANGAN ubah apapun di folder `web/` (frontend). Semua perubahan di sini backend-only.
- JANGAN ubah cabang `platform == "tiktok"` atau `platform == "youtube"` di `upload_clip()` — itu sistem terpisah (native OAuth), di luar scope fix ini.
- TASK 1, TASK 2, TASK 3 **HARUS dikerjakan bertiga sekaligus** dalam 1 kali jalan — kalau cuma TASK 1 saja tanpa TASK 2 & 3, kode akan crash (`media_url`/`vid_url` jadi tuple, bukan string).
- TASK 4 boleh dikerjakan terpisah kapan saja, tidak bergantung ke TASK 1-3.
- Kalau ketemu bagian source code yang TIDAK PERSIS sama dengan blok "Kode SEKARANG" yang dicontohkan di atas — STOP, JANGAN ditebak-tebak/dipaksa cocokin, laporkan balik teks yang kamu temukan.

---

## Cara Test

1. **Test akar masalah (TASK 1-3):** Pastikan Access Key/Secret Key Repliz valid di Settings, minimal 1 akun TikTok terhubung. Generate/pilih 1 clip di Stock Clip, pencet Upload.
2. Cek `data.json` clip tersebut → harus ada entry baru di `scheduled_uploads` dengan `status: "sukses"` dan `repliz_schedule_id` terisi (BUKAN lagi `"gagal"` dengan pesan generik seperti sebelumnya).
3. Cek dashboard Repliz (repliz.com → Schedule Content) → post baru harus muncul di kalender sesuai jadwal.
4. **Test pesan error spesifik (TASK 1-2):** Kosongkan/rusak Secret Key Repliz di Settings sementara, upload lagi → `error_message` di `data.json` sekarang harus berisi alasan SPESIFIK (misal `"Init File gagal: unauthorized"` atau kode HTTP-nya), BUKAN lagi cuma `"Gagal upload video ke Repliz Storage"` yang generik.
5. **Test TASK 3 (dead code):** Cukup pastikan `app.py` tetap bisa di-import/dijalankan tanpa `SyntaxError` — cabang ini memang tidak akan kepanggil di jalur normal, cukup pastikan tidak merusak apapun.
6. **Test TASK 4:** Cari clip lama (kalau ada) yang `data.json`-nya masih punya entry `scheduled_uploads` dengan `status: "terjadwal"` dari sebelum fix ini. Biarkan aplikasi jalan >1 menit (interval scheduler). Pastikan entry itu **TIDAK** berubah jadi `"gagal"` dengan pesan soal TikTok/YouTube credential — harusnya dibiarkan diam (tidak diproses ulang oleh scheduler ini).
7. Laporkan balik ke saya: (a) isi `error_message` persis kalau masih ada yang gagal di langkah 2-4, dan (b) potongan `data.json` hasil `scheduled_uploads` terbaru — itu kunci buat verifikasi lanjut.
