# MASTER REVIEW & LANJUTAN — AutoClipper Web Migration

## Konteks
Project migrasi UI lama (Tkinter, `pages/*.py`) ke web UI baru (`web/components/*.js` + `app.py` sebagai WebAPI/pywebview backend). Sudah beberapa ronde audit & fix bug (GUI terputus dari backend, backend ada tapi GUI belum ada), dikerjakan bertahap per task dengan review ketat tiap ronde. Sebagian besar sudah closed. File ini kumpulan SEMUA yang masih open + sisa pekerjaan, supaya bisa dilanjutkan tuntas dalam satu putaran.

## ATURAN WAJIB (pelajaran dari ronde-ronde review sebelumnya — WAJIB dibaca dulu)
Sepanjang project ini, beberapa masalah yang pernah ditemukan pas review:
- Klaim "sudah terhubung ke API asli" padahal endpoint-nya dikarang tanpa dokumentasi (kasus Repliz — akhirnya diperbaiki jadi TODO blocker yang jujur).
- Snippet kode dipotong pakai `# ...` / `// ...` yang bikin bug tersembunyi susah kedeteksi (kasus `dest_path` undefined — ternyata di source lengkap tapi hampir lolos review).
- Kontradiksi antar laporan — laporan A bilang identifier routing `'home'`, laporan B (kode aslinya) ternyata `'create-clip'`.
- Risiko key collision di object `fields`/`aiView.fields` karena prefix penamaan historis yang tidak konsisten dengan nama fitur aslinya (`hf`=OpenAI, `cm`=Anthropic, `hm`=Gemini, `cp`=Custom Provider — bukan singkatan yang match nama providernya).

Karena itu:
1. JANGAN percaya laporan ronde sebelumnya begitu saja — audit ulang independen terhadap kode ASLI sebelum melanjutkan.
2. SELALU tempel snippet kode LENGKAP tanpa elipsis (`...`) untuk bagian yang relevan verifikasi. Kalau perlu diringkas untuk laporan, tulis eksplisit "diringkas untuk laporan" DAN tetap sertakan bagian paling kritis (definisi variable, isi function, assignment).
3. Kalau ada ambiguitas produk atau endpoint API pihak ketiga yang dokumentasinya tidak ada di codebase → JANGAN mengarang. Buat implementasi aman minimal (disable/nonaktif dengan pesan jelas) + TODO comment + laporkan sebagai blocker.
4. Reuse logic dari file lama (`pages/*.py`, `*_uploader.py`, dll) — jangan tulis ulang dari nol.
5. Satu laporan = satu task. Jangan gabung banyak task jadi satu laporan besar (pernah bikin beberapa item kelewat review).

## A. Open items — WAJIB diverifikasi ulang / diselesaikan dulu (prioritas tinggi, cepat)

### A1. Task Hook Style — kode load/save slider masih ada elipsis
Laporan terakhir menunjukkan:
```javascript
if (aiView.fields.hsFontSize) { ...; aiView.fields.hsFontSize.dispatchEvent(new Event('input')); }
// ... (slider values update)
```
Tempel kode LENGKAP tanpa dipotong untuk load & save: Font Size, Corner Radius, Position X, Position Y, Font Color, BG Color — pastikan SEMUA field benar-benar di-set saat load (bukan cuma Font Size yang jadi contoh), dan semua ikut ke payload saat save.

### A2. Mapping `font_name` (dropdown) ↔ `font_path` (dipakai render) — BELUM JELAS, ini prioritas tertinggi
Laporan bilang: `get_system_fonts()` menarik daftar font terinstall (kemungkinan cuma nama), dan `save_hook_style_settings()` "decode absolute font_path sebelum disave".
Pertanyaan yang HARUS dijawab dengan kode, bukan asumsi:
- Apakah `get_system_fonts()` return pasangan `{name, path}` per font, atau cuma array nama string?
- Kalau user pilih "Arial" di dropdown, bagaimana backend tahu path file `.ttf` yang benar — terutama kalau ada beberapa varian (Arial Regular/Bold/Italic, atau beberapa font beda folder dengan nama sama)?
- Baca `utils/font_scanner.py` dan logic asli di `pages/settings/hook_style_settings.py` (versi Tkinter lama) — lihat cara mapping ini dilakukan di versi lama, pastikan versi web ikut pattern yang SAMA PERSIS (jangan bikin logic mapping baru yang beda perilaku).
- Tempel kode lengkap `get_system_fonts()` di `app.py` dan bagian `save_hook_style_settings()` yang menghandle `font_path`.
- Test manual: pilih font di dropdown, save, lalu cek isi `config.json` — pastikan value yang tersimpan adalah path file yang benar-benar valid & bisa dibuka di sistem (bukan cuma nama string yang nanti gagal dipakai FFmpeg/PIL saat render).

### A3. Full audit key collision — dump SELURUH object `fields`
Sejauh ini sudah dikonfirmasi aman: `hf` (OpenAI), `cm` (Anthropic), `hm` (Gemini), `cp` (Custom Provider), `wm` (Watermark), `cw` (Credit Watermark), `hs` (Hook Style). Tapi ini ditemukan reaktif satu-satu tiap ronde, belum pernah di-audit sekaligus.
WAJIB: dump SELURUH isi object `fields`/`aiView.fields` di `ai-settings.js` dari baris pertama sampai terakhir, TANPA dipotong. Cek manual apakah ada 2 key dengan nama PERSIS SAMA dimanapun dalam object literal tsb. Kalau ada duplikat → rename salah satu jadi prefix unik, lalu konfirmasi kedua fitur tetap jalan independen.

## B. Task yang masih BELUM dikerjakan (dari scope `04-settings-gui-belum-ada.md`)

- [ ] **Task 4 — Face tracking / Mediapipe settings** (sumber logic lama: `performance_settings.py`). Buat section/tab baru di Settings, WebAPI save/load ke config key yang sesuai, UI mengikuti field-field yang ada di file lama.
- [ ] **Task 5 — Output directory picker** (sumber logic lama: `output_settings.py`). Buat UI folder picker native (cek dokumentasi pywebview untuk `create_file_dialog` mode FOLDER — pattern mirip `browse_watermark_image()` yang sudah ada, tapi untuk folder bukan file gambar). Simpan path ke config, load balik saat init.
- [ ] **Task 6 — YouTube API credentials** (sumber logic lama: `youtube_api_settings.py`). Buat form input credential (client id/secret/token — cek field persis di file lama), WebAPI save/load ke config, sambungkan ke flow upload YouTube (`youtube_uploader.py`) supaya credential-nya BENAR-BENAR dipakai saat proses upload — bukan cuma tersimpan tapi tidak pernah dibaca (mirip bug lama di Whisper Model sebelum diperbaiki).

Ikuti pola yang sama seperti Watermark/Credit Watermark/Hook Style: satu laporan per task, snippet kode lengkap tanpa elipsis, reuse logic lama, cek collision key sebelum menambah field baru (lihat aturan A3).

## C. Instruksi umum (berlaku sepanjang sisa pekerjaan)
1. Sebelum klaim task "selesai", baca ulang kode yang baru ditulis LANGSUNG DARI FILE aslinya (bukan dari ingatan hasil edit), pastikan tidak ada elipsis/placeholder yang lolos ke source code sungguhan.
2. Setiap laporan WAJIB berisi: file yang diubah, snippet kode utuh untuk bagian kritis (endpoint baru, wiring event listener baru, payload save/load), dan konfirmasi eksplisit tidak ada key/nama yang bentrok dengan yang sudah ada.
3. Ambiguitas produk atau dokumentasi API pihak ketiga yang tidak tersedia → pilih opsi paling aman (nonaktifkan + pesan jelas) + TODO comment. JANGAN mengarang implementasi supaya terlihat selesai.
4. Setelah Task 4, 5, 6 selesai, buat SATU laporan akhir yang me-list ULANG SEMUA endpoint WebAPI baru yang ditambahkan sepanjang seluruh project ini (nama fungsi + parameter + fungsinya singkat), supaya bisa direview menyeluruh sekali lagi sebelum dianggap benar-benar kelar.

---
Urutan kerja: selesaikan A1–A3 dulu (ini verifikasi cepat, bukan kerjaan baru), baru lanjut B (Task 4, 5, 6) satu per satu dengan laporan terpisah per task, tutup dengan laporan akhir sesuai poin C4.
