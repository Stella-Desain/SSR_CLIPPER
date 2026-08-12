# Stock Clip — GUI Belum Ada
File utama: `app.py` (WebAPI) + backend logic sudah ada di `tiktok_uploader.py`, `youtube_uploader.py`, `dialogs/repliz_upload.py`

PENTING: file `03-stockclip-terputus.md` Task 4 & 6 DEPENDS on task di file ini. Kerjakan file ini duluan.

## Task 1: Logic upload TikTok/YouTube/Repliz ada, tapi tidak diekspos lewat WebAPI
- Konteks: `tiktok_uploader.py`, `youtube_uploader.py`, `dialogs/repliz_upload.py` sudah punya logic upload lengkap, tapi tidak ada method `upload_clip()` (atau sejenisnya) di `WebAPI` class di `app.py`, jadi frontend tidak bisa memicu upload sama sekali.
- Fix:
  1. Tambahkan method baru di WebAPI (`app.py`), misal `upload_clip(clip_path, platform, **kwargs)`.
  2. Di dalam method ini, panggil fungsi upload yang SUDAH ADA di `tiktok_uploader.py` / `youtube_uploader.py` / `dialogs/repliz_upload.py` sesuai `platform` yang dipilih. JANGAN tulis ulang logic upload dari nol — reuse fungsi yang sudah ada.
  3. Return status yang jelas ke frontend: `success`, `error` (dengan pesan error asli, misal kredensial belum diisi), atau `progress` kalau uploader support progress callback.
  4. Kalau kredensial (API key/token) untuk platform tersebut belum diisi user, return error message yang jelas ("Kredensial [platform] belum diisi di Settings"), jangan crash.
- Acceptance: memanggil `upload_clip(path, "tiktok")` dari frontend (bisa test manual via console/devtools dulu) benar-benar memicu proses uploader asli dan mengembalikan status yang sesuai (sukses/gagal dengan alasan jelas).
