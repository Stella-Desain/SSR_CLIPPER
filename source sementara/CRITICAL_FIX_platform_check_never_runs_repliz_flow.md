# FIX — Upload "Sukses" Tapi Gak Ada yang Beneran Terkirim ke Repliz

**File yang diubah:** `app.py` SAJA
**Sifat perubahan:** Hapus 1 kondisi `if` yang salah (dari SPEC A sebelumnya), sisanya TIDAK berubah.
**Prioritas:** KRITIS — ini akar masalah kenapa upload selalu "gagal" (padahal toast bilang sukses) dan kalender Repliz selalu kosong.

---

## Akar masalah

Di `preview_distribution()`, field `platform` tiap assignment diisi dari:
```python
"platform": candidate.get("type", "repliz"),
```
`candidate.get("type")` itu **jenis platform sosial akun** (`"tiktok"`, `"instagram"`, dst — dari Repliz API), BUKAN nama layanan yang dipakai. Karena akun yang dipakai adalah akun TikTok, nilai `platform` di setiap assignment SELALU `"tiktok"`, TIDAK PERNAH literally `"repliz"`.

Tapi di `confirm_distribution()`, ada kondisi:
```python
if platform == "repliz":
    # ...seluruh logic upload ke Storage, pilih musik AI, create_schedule...
```
Kondisi ini SELALU `False` untuk akun manapun (karena `platform` isinya `"tiktok"`/`"instagram"`/dst, bukan `"repliz"`) — jadi seluruh blok di dalamnya **tidak pernah dieksekusi**. `entry["status"]` tetap nilai default `"terjadwal"` dan tidak pernah berubah jadi `"sukses"`/`"gagal"`. Sementara itu `quick_upload()` (pemanggil `confirm_distribution`) menghitung sukses berdasarkan JUMLAH assignment yang diproses (`len(preview["assignments"])`), BUKAN berdasarkan apakah request beneran berhasil dikirim — jadi toast tetap bilang "berhasil dijadwalkan" walau tidak ada satupun panggilan API yang benar-benar terjadi.

**Fakta kunci:** Satu-satunya sumber akun di `assignments` adalah `get_repliz_accounts()` (lihat `preview_distribution()`, tidak ada jalur lain). Artinya SEMUA entry yang masuk ke `confirm_distribution()` memang harus diproses lewat Repliz — kondisi `if platform == "repliz"` ini tidak perlu ada sama sekali.

---

## Fix

Cari blok ini di `confirm_distribution()` (persis seperti sekarang):

```python
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
```

Ganti jadi (HAPUS baris `if platform == "repliz":`, ganti indentasi baris di bawahnya supaya sejajar dengan `entry = {...}`, sisanya SAMA PERSIS):

```python
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

                entry["attempted_at"] = datetime.now().isoformat()
```

**PENTING:** Semua baris SETELAH `if platform == "repliz":` yang tadinya ada di DALAM blok `if` (mulai dari `if not access_key or not secret_key:` sampai baris terakhir sebelum `if "scheduled_uploads" not in cdata:`) — kurangi indentasi-nya 1 level (4 spasi) supaya sejajar dengan `entry["attempted_at"] = ...` di atas, TAPI ISI KODENYA SAMA PERSIS, TIDAK ADA YANG DIUBAH selain indentasi. Jadi hasil akhirnya persis seperti ini (bandingkan dengan versi lama untuk pastikan cuma indentasi + hapus 1 baris `if` yang berubah):

```python
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
```

Bagian setelah ini (`if "scheduled_uploads" not in cdata: ...` sampai akhir function) TIDAK berubah sama sekali — tetap di indentasi 16-spasi seperti sebelumnya (sejajar dengan `entry = {`), karena itu memang sudah di LUAR blok `if` yang dihapus.

---

## ATURAN KETAT

- JANGAN ubah isi logic di dalamnya sama sekali (bagian upload storage, pilih musik, create_schedule) — HANYA kurangi indentasi 1 level dan hapus baris `if platform == "repliz":`.
- JANGAN sentuh `_upload_scheduler()`, `upload_clip()`, atau bagian lain — itu di luar scope fix ini.
- JANGAN ubah `preview_distribution()` — field `platform` di situ boleh tetap isinya jenis akun sosial (`"tiktok"` dst), itu tetap berguna buat ditampilkan/disimpan sebagai metadata, cuma jangan dipakai sebagai kondisi routing lagi.

---

## Cara Test

1. Generate/pilih 1 clip yang campaign-nya sudah ada akun TikTok terhubung.
2. Upload dari Stock Clip.
3. Cek `data.json` clip: `scheduled_uploads` entry terbaru HARUS punya `status: "sukses"` (dengan `repliz_schedule_id`) atau `status: "gagal"` dengan `error_message` yang JELAS (bukan lagi diam-diam `"terjadwal"` selamanya).
4. Cek dashboard Repliz (Schedule Content) — post baru HARUS muncul di tanggal yang sesuai.
5. Kalau masih `"gagal"` — sekarang `error_message`-nya akan kasih tau alasan SPESIFIK (misal error dari Repliz API), bukan sekedar "tidak terupload" tanpa penjelasan. Kirim isi `error_message` itu ke saya kalau masih gagal, itu kunci buat debug lebih lanjut.
