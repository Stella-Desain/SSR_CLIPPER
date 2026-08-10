# Stock Clip — GUI Ada, Program Tidak Ada/Tidak Terhubung
File: `web/components/stock-clip.js`

## 1. `onDelete` pada job item
- Lokasi: stock-clip.js:126
- Status: program tidak ada
- Aksi: buat endpoint `delete_job(job_id)` (hapus dari job_history), wire tombol delete

## 2. `onDelete` pada clip item
- Lokasi: stock-clip.js:150
- Status: program tidak ada
- Aksi: buat endpoint `delete_clip(clip_path)` (hapus file mp4 + entry data.json), wire tombol delete

## 3. `onUpload` pada clip item
- Lokasi: stock-clip.js:151
- Status: program tidak ada di WebAPI baru — TAPI logic upload SUDAH ADA di kode lama (`tiktok_uploader.py`, `youtube_uploader.py`, `dialogs/repliz_upload.py`)
- Aksi: buat endpoint `upload_clip(clip_path, platform)` yang memanggil uploader lama; wire tombol upload

## 4. `onPlay` pada clip item
- Lokasi: stock-clip.js:152
- Status: program ada tapi salah — cuma panggil `open_output_folder()`, bukan "play video"
- Aksi: buat endpoint `play_clip(path)` (buka file spesifik via `os.startfile`/`subprocess`, bukan folder)
