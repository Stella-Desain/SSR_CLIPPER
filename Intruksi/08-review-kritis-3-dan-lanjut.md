# REVIEW KRITIS #3 — Sisa Kecil + Lanjut ke Settings Form

STATUS: Sebagian besar D1-D7 DITERIMA. Tinggal 3 verifikasi kecil (poin E) yang tidak menghalangi kerja baru — boleh dikerjakan paralel sambil mulai Settings Form (poin F).

## E. Verifikasi kecil sisa (jawab kapan saja, tidak blocking)

### E1. Nama variabel `hfValidateBtn` untuk tombol Test API — mencurigakan
Di D3 Task 1 kamu tulis: `hfValidateBtn: openai.testBtn`. Nama `hfValidateBtn` ("hf" = Highlight Finder?) tidak nyambung secara semantik dengan tombol Test OpenAI/Anthropic/Gemini. Ini kemungkinan:
- (a) cuma nama variabel lama yang kepakai ulang tapi fungsinya sudah benar, ATAU
- (b) salah bind — sebenarnya nyambung ke elemen/listener yang salah.
Konfirmasi: apa isi lengkap object/mapping tempat `hfValidateBtn` didefinisikan (tunjukkan 5-10 baris sekitarnya)? Dan pastikan binding lama ke `dummyBtn` (elemen hidden dari bug awal) benar-benar SUDAH DIHAPUS, bukan cuma ditambah binding baru di sampingnya (supaya tidak double-listener).

### E2. Urutan argumen `upload_to_repliz`
Call site: `uploader.upload_to_repliz(account_id, title, desc, vid_url)`. Tunjukkan signature asli method `upload_to_repliz` di `dialogs/repliz_upload.py` (baris `def upload_to_repliz(self, ...)`) untuk pastikan urutan parameter di call site sudah cocok persis — kalau urutannya salah (misal harusnya `desc` sebelum `title`), upload akan jalan tanpa error tapi datanya ketuker.

### E3. Bukti registrasi nama view `'create-clip'` di router
Untuk menutup D5 100%, tunjukkan potongan kode router (`setActiveView` atau daftar view yang valid di `app.js`/`header.js`) yang berisi string `'create-clip'` persis — supaya kepastian bukan typo/beda-kapital dengan identifier di tempat lain.

## F. Lampu hijau: lanjut ke `04-settings-gui-belum-ada.md` (Task 1-6)

Boleh mulai. Satu pengingat proses, karena beberapa laporan sebelumnya kena masalah gara-gara terlalu banyak digabung sekaligus:

- **Laporkan SETIAP SELESAI 1 task**, jangan digabung 6 task jadi satu laporan besar di akhir. Urutan bebas, tapi 1 laporan = 1 task (Watermark dulu, review, lanjut Credit Watermark, dst).
- Tetap ikuti aturan di `04-settings-gui-belum-ada.md`: reuse logic dari `pages/settings/*.py` lama, jangan tulis ulang dari nol, dan sertakan snippet kode asli di tiap laporan (bukan cuma prosa) — khususnya untuk method WebAPI save/load config yang baru dibuat.
- Kalau di tengah jalan nemu ambiguitas produk (contoh kasus field config yang belum ada default value-nya), ambil opsi paling aman + tulis TODO, seperti pola yang sudah bagus dipakai di D2.3 (Repliz account dropdown yang auto-disable saat API belum tersedia).

Mulai dari Task 1 (Watermark settings) dan laporkan begitu selesai.
