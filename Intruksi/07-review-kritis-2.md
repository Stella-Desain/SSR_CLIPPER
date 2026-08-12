# REVIEW KRITIS #2

STATUS: sebagian sudah oke, tapi ada gap & 1 kontradiksi yang HARUS dijawab dulu sebelum lanjut ke Settings Form (Watermark dkk) yang belum digarap.

## Sudah OK (tidak perlu diulang lagi)
- A2 (Repliz Test Connection): pendekatan benar — jujur bilang dokumentasi API belum ada, revert ke status error/TODO alih-alih pura-pura berhasil terhubung. Pertahankan pola ini untuk kasus serupa ke depannya.
- C2 (parameter `process()`): nama parameter konsisten antara `app.py` dan `clipper_core.py`. Bagus.

## D. Masih harus dibuktikan / diperbaiki

### D1. Snippet A1 (Local User → config) belum ditunjukkan
Instruksi minta kode asli, bukan cuma deskripsi. Tempel: kode `get_app_config()` di `app.py`, dan kode di `app.js`/`header.js` yang consume hasilnya — termasuk fallback kalau field `owner_name` belum ada di `config.json`.

### D2. `MockReplizUploader` — beberapa risiko harus dicek
1. Nama "Mock" menyesatkan — ini dipakai untuk fitur produksi asli (upload beneran), bukan testing/stub. Ganti nama, misal `ReplizUploaderAdapter`, supaya developer lain tidak salah kira ini kode test-only dan dihapus/diabaikan nanti.
2. `upload_video_to_storage` & `upload_to_repliz` dipinjam langsung dari `ReplizUploadDialog` TANPA memanggil `__init__` aslinya. Cek: apakah kedua method itu memakai attribute lain selain `self.access_key`/`self.secret_key` (misal `self.session`, `self.parent`, `self.headers`, koneksi HTTP, dsb) yang biasanya di-set di `__init__` asli `ReplizUploadDialog`? Kalau ya, `MockReplizUploader` akan lempar `AttributeError` saat dipakai. WAJIB cek isi `ReplizUploadDialog.__init__` dan laporkan attribute apa saja yang benar-benar dipakai kedua method tsb.
3. `account_id` di-require dari `kwargs`, tapi apakah `stock-clip.js` sudah punya UI untuk user memilih akun Repliz mana yang dituju? Kalau belum ada UI pilih akun, upload Repliz akan SELALU gagal dengan "Missing account_id" — secara teknis "tersambung" tapi tidak bisa dipakai end-to-end. Konfirmasi ini, dan kalau belum ada, tambahkan dropdown pilih akun (bisa pakai data dari `get_account_stats()`).
4. `class MockReplizUploader` didefinisikan ulang di dalam method setiap kali dipanggil (nested class di dalam blok `if`). Pindahkan ke level module/file terpisah — bukan bug fatal, tapi bukan praktik baik untuk kode produksi.

### D3. `04-settings-terputus.md` Task 1 & Task 5 — TIDAK dikonfirmasi
Sudah diminta eksplisit di review sebelumnya (poin B) tapi tidak muncul di laporan terakhir:
- [ ] Task 1 — tombol Test (OpenAI/Anthropic/Gemini) beneran bind ke tombol asli, bukan `dummyBtn` lagi? Lokasi file:baris?
- [ ] Task 5 — `#reload-model-btn` punya `addEventListener` yang benar-benar terpasang ke tombolnya? Lokasi file:baris?
Jawab dengan format sama seperti item lain di poin B (SUDAH/BELUM + lokasi).

### D4. `03-stockclip-terputus.md` Task 4, 5, 6 — belum lengkap dikonfirmasi
Laporan terakhir cuma sebut Task 1, 2, 3.
- Task 4 (Upload Semua) & Task 6 (onUpload per clip) sempat disebut di laporan ROUND SEBELUMNYA (bukan di jawaban D ini) — konfirmasi ulang status + lokasi baris terbaru.
- Task 5 (subheader "Clips: 45", "Size: 45mb", judul video hardcode) BELUM PERNAH dikonfirmasi sama sekali di 2 laporan manapun. Cek, kerjakan kalau belum, laporkan lokasi baris.
- Task 1 (`delete_job`): tunjukkan snippet kode dialog konfirmasi sebelum delete — instruksi mewajibkan ini karena delete itu aksi destruktif. Jangan cuma disebut prosa, tunjukkan kodenya (baik `window.confirm()` atau custom modal).

### D5. Ketidakcocokan handler "New Clip" — WAJIB diluruskan
- Laporan ROUND SEBELUMNYA: `window.setActiveView('home')`.
- Laporan TERAKHIR (poin C4): `window.setActiveView('create-clip')`.
Dua identifier ini beda ('home' vs 'create-clip'). Cek definisi `setActiveView` / daftar nama view yang valid di routing, pastikan cuma 1 value yang benar dipakai di kode saat ini, lalu TES benar-benar berpindah ke halaman Create Clip saat tombol diklik. Laporkan value yang benar & hasil tes.

### D6. `04-settings-gui-belum-ada.md` — status tidak match nomor task asli
File aslinya punya 6 task: (1) Watermark, (2) Credit watermark, (3) Hook style, (4) Face tracking/Mediapipe, (5) Output directory picker, (6) YouTube API credentials.
Laporan kemarin cuma sebut 3 item dengan deskripsi longgar (general settings / MediaPipe form / font scanner+hook style) — tidak jelas itu task nomor berapa, dan Watermark, Credit watermark, Output directory picker, YouTube API credentials sama sekali tidak disebut statusnya.
Restate status keenam task PERSIS sesuai nomor di file aslinya (Task 1–6), satu-satu, format SUDAH/BELUM.

### D7. Isi function `process()` untuk `highlight_finder` & `yt_title_maker`
Snippet yang ditunjukkan cuma baris signature. Tunjukkan juga bagian isi `process()` yang memakai kedua parameter ini — pastikan kalau logic-nya memang belum ada, ada comment `# TODO` yang jelas (bukan logic yang dikarang/pura-pura berjalan).

## Instruksi balik
Jawab D1–D7 satu-satu dengan kode asli (snippet), bukan prosa ringkasan. Setelah semua poin ini clear (terutama D5 karena itu kontradiksi langsung), baru boleh lanjut ke pengerjaan Settings Form (Watermark dkk) yang memang belum tersentuh.
