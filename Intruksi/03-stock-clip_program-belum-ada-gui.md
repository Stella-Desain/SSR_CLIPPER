# Stock Clip — Program Ada, GUI Tidak Ada
File terkait (kode lama): `tiktok_uploader.py`, `youtube_uploader.py`, `dialogs/repliz_upload.py`

## 1. TikTok uploader
- Status: logic lengkap ada di `tiktok_uploader.py`, tidak diekspos ke WebAPI baru
- Aksi: endpoint `upload_clip(path, platform='tiktok')`

## 2. YouTube uploader
- Status: logic lengkap ada di `youtube_uploader.py`, tidak diekspos ke WebAPI baru
- Aksi: endpoint `upload_clip(path, platform='youtube')`

## 3. Repliz uploader
- Status: logic ada di `dialogs/repliz_upload.py`, tidak diekspos ke WebAPI baru
- Aksi: endpoint `upload_clip(path, platform='repliz')` + lengkapi UI Repliz fungsional (lihat file Settings)
