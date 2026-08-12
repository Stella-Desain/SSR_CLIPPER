# REVIEW KRITIS — Setelah 02, 03, 04, 05

STATUS: BELUM APPROVED. Jangan mulai task/file baru sebelum poin A & B di bawah dijawab tuntas dan poin A diperbaiki.

## A. Wajib diperbaiki sekarang (indikasi bug/pelanggaran instruksi)

### A1. Username "Bintang SSR" → diganti "Local User" (masih hardcode)
- Instruksi asli (`05-global-terputus.md` Task 3): ambil value dari **config**, bukan tulis string baru di kode.
- "Local User" tetap hardcode literal di `header.js` — cuma pindah dari 1 hardcode ke hardcode lain, belum sesuai instruksi.
- Fix: baca nama app/owner dari `config.json` (field yang sudah ada; kalau belum ada, boleh tambah default value di config, tapi HARUS dibaca dari config saat render, bukan ditulis literal di `header.js`).

### A2. Repliz "Test Connection" & "Account Connected" diklaim sudah nyata/dinamis
- Kontradiksi: `get_campaigns()` ditandai TODO blocker karena "dokumentasi endpoint spesifiknya tidak tersedia" — tapi Test Connection & Account Connected diklaim sudah "secara nyata melakukan request API".
- Kalau memang tidak ada dokumentasi API Repliz sama sekali, endpoint/URL apa yang dipakai untuk 2 fungsi ini?
- Instruksi asli eksplisit melarang mengarang endpoint API (`04-settings-terputus.md` Task 7 & 8).
- Fix: tunjukkan kode asli method Test Connection & `get_account_stats()` versi baru. Kalau endpoint-nya hasil tebakan/tidak terverifikasi dari dokumentasi resmi Repliz → revert ke pattern sama seperti `get_campaigns()` (TODO blocker + pesan error jelas ke user), JANGAN tampilkan seolah berhasil terhubung.

### A3. Upload hanya sebut platform "TikTok/YouTube"
- Task asli (`03-stockclip-gui-belum-ada.md` Task 1) minta expose upload untuk TikTok, YouTube, **dan Repliz** (`dialogs/repliz_upload.py`).
- Konfirmasi: apakah `upload_clip()` juga menerima `platform="repliz"`? Kalau belum, tambahkan. Kalau sengaja di-skip, jelaskan alasannya di sini.

## B. Task yang TIDAK disebut di laporan — konfirmasi satu-satu (format: SUDAH/BELUM + lokasi file:baris)

Dari `02-createclip-terputus.md`:
- [ ] Task 1 — Upload zone cookies reuse handler tombol "Cookies" header
- [ ] Task 2 — `<select id="clips">` & `<select id="subtitle">` unhide + masuk `fields`
- [ ] Task 3 — toggle Highlight Finder & YT Title Maker masuk payload `start_processing()` + param baru diteruskan ke core
- [ ] Task 4 — `loadDefaultConfig()` dibuat & dipanggil saat init `home.js`

Dari `02-createclip-gui-belum-ada.md`:
- [ ] Task 1 — toggle Portrait Mode ditambahkan, terkirim sebagai `portrait`

Dari `03-stockclip-terputus.md`:
- [ ] Task 1 — `delete_job()` dibuat + `onDelete` wired + ADA dialog konfirmasi sebelum delete beneran
- [ ] Task 2 — filter "Campaign: All" punya `onchange` & benar-benar memfilter list
- [ ] Task 3 — "Clips: 45" sudah dinamis (bukan hardcode)
- [ ] Task 5 — subheader (judul video, Clips, Size) sudah dinamis

Dari `04-settings-terputus.md`:
- [ ] Task 1 — tombol Test (OpenAI/Anthropic/Gemini) sudah bind ke tombol asli, bukan `dummyBtn` lagi
- [ ] Task 5 — `#reload-model-btn` punya `addEventListener` yang benar-benar terpasang ke tombolnya (bukan cuma function `reload_whisper_model` didefinisikan tanpa disambungkan)

Dari `04-settings-gui-belum-ada.md` (6 item: watermark, credit watermark, hook style, face tracking/performance, output directory picker, YouTube API credentials):
- [ ] Sebutkan status masing-masing dari 6 item ini satu per satu. Kalau belum dikerjakan, itu WAJAR (task besar), tapi jangan dilaporkan sebagai "seluruhnya selesai" kalau nyatanya belum disentuh.

## C. Verifikasi teknis — tempel kode asli, bukan penjelasan prosa
1. Kode lengkap function `upload_clip()` di `app.py`.
2. Kode wiring `local_whisper_settings` ke `AutoClipperCore` — pastikan nama parameter PERSIS sama dengan signature asli di `clipper_core.py` (screenshot/cuplikan definisi function di core + cuplikan pemanggilannya).
3. Kode method Test Connection Repliz + `get_account_stats()` versi baru (untuk verifikasi poin A2).
4. Kode handler tombol "New Clip" — laporan sebut 2 opsi sekaligus ("`window.setActiveView('home')` **atau** trigger click nav-item sebagai fallback"). Pastikan cuma 1 mekanisme yang benar-benar dipakai & teruji, bukan dua-duanya ditulis sebagai jaga-jaga tanpa tahu mana yang valid — kalau fallback beneran dipakai untuk jaga-jaga karena `setActiveView` tidak selalu ada, jelaskan kondisinya.

## Instruksi balik ke Gemini
- Jawab poin A1–A3 dengan perbaikan kode langsung (bukan cuma janji).
- Jawab poin B per baris dengan format: `Task X → SUDAH/BELUM, lokasi: nama_file:nomor_baris`.
- Jawab poin C dengan tempel snippet kode asli.
- JANGAN mulai mengerjakan task/file instruksi baru sebelum semua poin di atas dijawab.
