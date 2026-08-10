# Settings — Program Ada, GUI Tidak Ada
File lama terkait: `pages/settings/*.py`; dipakai aktif oleh `clipper_core.py` via config.json

## 1. Watermark settings
- Config key: `watermark`; referensi lama: `pages/settings/watermark_settings.py`
- Status: program ada & aktif dipakai `AutoClipperCore`, GUI baru tidak ada
- Aksi: buat section "Watermark" (enable toggle, upload image, posisi, opacity) -> simpan ke config key `watermark`

## 2. Credit watermark settings
- Config key: `credit_watermark`; referensi lama: `pages/settings/credit_watermark_settings.py`
- Status: sama seperti di atas
- Aksi: buat section "Credit Watermark"

## 3. Hook style settings
- Config key: `hook_style`; referensi lama: `pages/settings/hook_style_settings.py`
- Status: program ada, GUI tidak ada
- Aksi: buat section "Hook Style" (font/warna/posisi teks hook)

## 4. Face tracking / mediapipe settings
- Config key: `face_tracking_mode`, `mediapipe_settings`; referensi lama: `pages/settings/performance_settings.py`
- Status: program ada, dipakai untuk crop/tracking wajah di clipper_core.py; GUI tidak ada
- Aksi: buat section "Face Tracking / Performance" (pilih opencv/mediapipe + threshold params)

## 5. Output directory
- Config key: `output_dir`; referensi lama: `pages/settings/output_settings.py`
- Status: program ada, dipakai `_run()` & semua listing clip; GUI tidak ada
- Aksi: buat field "Output Folder" + tombol browse (`pywebview.create_file_dialog`) di Settings

## 6. YouTube API credentials
- Referensi lama: `pages/settings/youtube_api_settings.py`; dipakai `youtube_uploader.py`
- Status: program ada, GUI tidak ada
- Aksi: buat section "YouTube API" (client_id/secret/token)

## 7. Dependency installer (`utils/dependency_manager.py`)
- Status: program ada, hanya SEBAGIAN diekspos (`check_dependencies` saja); instalasi belum fungsional
- Aksi: lihat item 6 di `04-settings_gui-belum-terhubung.md`
