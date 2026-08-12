# Stock Clip — GUI Terputus
File utama: `web/components/stock-clip.js` (+ `app.py` untuk WebAPI)

ATURAN: Task 4 & 6 punya dependency ke file `03-stockclip-gui-belum-ada.md` Task 1 (endpoint `upload_clip`) — kerjakan endpoint itu DULU sebelum Task 4 & 6 di sini.

## Task 1: `onDelete` job item kosong `() => {}`
- Lokasi: line 129. Tidak ada endpoint `delete_job()` di backend.
- Fix:
  1. Backend: buat method `delete_job(job_id)` di WebAPI (`app.py`). Ikuti pattern penyimpanan job yang sudah ada (cek bagaimana job disimpan/dibaca di endpoint lain) supaya hapus job konsisten (hapus entry data + file terkait kalau relevan).
  2. Frontend: isi `onDelete` supaya panggil endpoint ini. WAJIB tampilkan dialog konfirmasi sebelum delete beneran (safety, karena ini operasi destruktif). Setelah sukses, refresh list job.
- Acceptance: klik delete → muncul konfirmasi → confirm → job hilang dari data & UI ter-update.

## Task 2: Filter "Campaign: All" statis
- Lokasi: line 36. Dropdown cuma 1 opsi, tidak ada `onchange`, tidak filter apapun.
- Fix: populate dropdown dari daftar campaign asli (reuse data campaign yang sudah dipakai render di tempat lain, jangan bikin fetch baru kalau data sudah ada di frontend). Tambahkan `onchange` yang filter clip yang ditampilkan sesuai campaign terpilih (filter client-side cukup).
- Acceptance: pilih campaign tertentu → list clip yang tampil cuma dari campaign itu. Pilih "All" → semua tampil lagi.

## Task 3: "Clips: 45" hardcode
- Lokasi: line 37.
- Fix: hitung jumlah clip asli dari data yang di-render, update angka ini setiap `refresh()`/render dipanggil. Hapus hardcode `45`.
- Acceptance: angka berubah sesuai jumlah clip data asli.

## Task 4: "Upload Semua" tombol tanpa handler
- Lokasi: `clipsHeader`, line 78.
- DEPENDENCY: kerjakan `03-stockclip-gui-belum-ada.md` Task 1 dulu (endpoint `upload_clip`).
- Fix: tambahkan handler yang loop semua clip yang sedang ditampilkan, panggil endpoint `upload_clip` untuk masing-masing. Tampilkan progress/status per clip (sukses/gagal), jangan silent — total N clip diupload, tampilkan hasil akhir (misal "X berhasil, Y gagal").
- Acceptance: klik "Upload Semua" benar-benar upload semua clip yang tampil, ada feedback progress & hasil.

## Task 5: Clips subheader hardcode (judul video, "Clips: 45", "Size: 45mb")
- Lokasi: line 85-93.
- Fix: ambil judul video, jumlah clip per video, dan ukuran file dari data asli yang sudah di-fetch untuk video tersebut. Render dinamis, hapus semua hardcode di area ini.
- Acceptance: subheader menampilkan info sesuai video/clip asli, beda video → beda angka.

## Task 6: `onUpload` per clip cuma manggil `open_output_folder()`
- Lokasi: line 159. Bukan upload beneran.
- DEPENDENCY: kerjakan `03-stockclip-gui-belum-ada.md` Task 1 dulu.
- Fix: ganti `onUpload` supaya panggil endpoint `upload_clip` beneran untuk clip tersebut. Kalau perlu user pilih platform (TikTok/YouTube/Repliz), tambahkan pilihan platform sederhana (dropdown/button group) sebelum trigger upload. Pertahankan akses "buka folder" sebagai ikon/aksi terpisah kalau masih dibutuhkan user (jangan hilangkan fungsi lama, pindahkan ke tombol/ikon sendiri).
- Acceptance: klik upload di 1 clip benar-benar mengunggah lewat `upload_clip`, bukan cuma buka folder. Fungsi buka folder tetap ada di tempat lain kalau masih relevan.
