# Settings — GUI Belum Ada
File utama: `web/components/ai-settings.js` (atau file settings baru, ikuti pattern yang sama) + `app.py` untuk WebAPI

Backend logic-nya sudah ada semua di `pages/settings/*.py` (kode lama). Tugas di sini: expose lewat WebAPI + buat UI counterpart di web baru. JANGAN tulis ulang logic dari nol.

ATURAN TAMBAHAN: kerjakan 1 item per commit/PR, jangan digabung jadi 1 komponen raksasa — biar gampang direview & ditest satu-satu.

## Task 1: Watermark settings
- Sumber logic lama: `pages/settings/watermark_settings.py`, config key `watermark`.
- Fix: buat section/tab baru "Watermark" di Settings page. Buat method WebAPI save/load yang baca-tulis config key `watermark`. UI minimal: field-field yang dulu ada di `watermark_settings.py` (posisi, opacity, path gambar, dll — cek isi file itu untuk tahu field apa saja).
- Acceptance: user ubah setting watermark dari UI baru, tersimpan ke config, dan value itu benar dipakai saat proses clip jalan (verify minimal via parameter yang diteruskan ke core).

## Task 2: Credit watermark settings
- Sumber logic lama: `credit_watermark_settings.py`.
- Fix: sama pattern seperti Task 1 — section baru, WebAPI save/load, UI sesuai field di file lama.
- Acceptance: sama seperti Task 1, untuk credit watermark.

## Task 3: Hook style settings
- Sumber logic lama: `hook_style_settings.py`.
- Fix: sama pattern seperti Task 1.
- Acceptance: sama seperti Task 1, untuk hook style.

## Task 4: Face tracking / Mediapipe settings
- Sumber logic lama: `performance_settings.py`.
- Fix: sama pattern seperti Task 1.
- Acceptance: sama seperti Task 1, untuk face tracking/performance.

## Task 5: Output directory picker
- Sumber logic lama: `output_settings.py`.
- Fix: buat UI folder picker (kalau environment desktop app support native dialog, reuse cara `open_output_folder()` membuka folder untuk referensi API yang tersedia). Simpan path terpilih ke config, load balik saat init.
- Acceptance: user pilih folder output dari UI, tersimpan, dipakai sebagai lokasi output saat proses clip jalan.

## Task 6: YouTube API credentials
- Sumber logic lama: `youtube_api_settings.py`.
- Fix: buat form input credential YouTube API (client id/secret/token sesuai field di file lama), WebAPI save/load ke config, sambungkan ke flow upload YouTube (`youtube_uploader.py`, lihat juga `03-stockclip-gui-belum-ada.md`).
- Acceptance: credential tersimpan & ter-load, dipakai saat proses upload YouTube (minimal verify credential terbaca oleh `youtube_uploader.py`).
