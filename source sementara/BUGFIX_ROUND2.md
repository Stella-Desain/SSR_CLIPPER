# BUG FIX & VERIFICATION ROUND 2 — SSR_CLIPPER

Ini lanjutan dari `e2e_runner.py` + laporannya yang kamu kasih sebelumnya. Sudah direview satu-satu terhadap source code asli. Hasilnya: 2 bug confirmed dan harus difix, 1 klaim ternyata salah dan harus di-retract, 2 hal butuh klarifikasi/investigasi lebih lanjut sebelum diputuskan fix-nya seperti apa.

## Aturan Wajib
- Ikuti track A, B, C di bawah secara terpisah. Jangan gabung/lompat urutan.
- Tiap perubahan kode WAJIB disertai `git diff` + bukti test ulang (bukan klaim "sudah fix").
- JANGAN ubah/fix apapun di luar yang diminta eksplisit di sini.
- JANGAN hardcode credentials (API key, secret key, access key) di file apapun lagi — pakai environment variable atau file config lokal yang sudah di-`.gitignore`. Cek juga: apakah `e2e_runner.py` sempat ke-commit ke git dengan credentials di dalamnya? Kalau iya, itu HARUS di-flag balik ke saya sebelum lanjut apapun — itu kebocoran, bukan bug biasa.

---

## TRACK A — FIX SEKARANG (2 bug confirmed dari review source code)

### A1. `AutoClipperCore` crash saat hook_maker api_key kosong (paling kritis)

**Root cause:** `clipper_core.py` line ~151, constructor `AutoClipperCore.__init__` selalu bikin `self.tts_client = OpenAI(api_key=hm_config.get("api_key", ""), ...)` — unconditional, nggak peduli fitur hook mau dipakai atau nggak. Sudah diverifikasi empiris: `OpenAI(api_key="")` dari SDK asli MEMANG langsung raise `OpenAIError: Missing credentials`. Default config baru (`config_manager.py::_get_default_ai_providers()`) emang set `hook_maker.api_key` ke `""`. Jadi user baru yang cuma isi API key Highlight Finder terus klik Generate — app crash di titik ini.

**Diperparah oleh:** `app.py` line ~325, `core = AutoClipperCore(...)` dipanggil DI LUAR blok `try/except` (try-nya baru mulai line ~362, cuma bungkus `core.process()`). Exception dari constructor nggak ketangkep sama sekali → thread mati diam-diam → `self.status` nggak pernah keupdate dari "idle" → UI kelihatan diam padahal proses udah mati.

**Fix yang harus dilakuin (dua-duanya, bukan pilih salah satu):**

1. Di `clipper_core.py`, sebelum tiap pembuatan `OpenAI(...)` client (highlight_finder, caption_maker, hook_maker — cek juga kalau ada client keempat buat youtube_title_maker), guard api_key kosong: kalau `hm_config.get("api_key", "")` hasilnya falsy, ganti jadi placeholder non-kosong (misal `"not-configured"`) sebelum dipassing ke `OpenAI()`. Ini bikin constructor nggak pernah crash — kegagalan asli (key beneran invalid) akan tetap muncul dengan jelas nanti pas API call beneran dipanggil (kode udah ada error handling buat itu, contoh log "TTS API Connection Error" di baris ~4126).

2. Di `app.py::_run()`, pindahin blok `core = AutoClipperCore(...)` dan `core.enable_gpu_acceleration(...)` (line ~325-360) ke DALAM `try:` block yang sama dengan `core.process()` (yang mulai line ~362). Ini defense-in-depth — exception apapun pas setup/init, bukan cuma dari bug ini, ke depannya bakal ketangkep dan status ke-update dengan benar ke UI, bukan mati diam-diam.

**Bukti yang wajib disertain setelah fix:** re-run test dengan `hook_maker.api_key` sengaja dikosongin, `add_hook=False` — pastikan proses jalan sampai selesai (atau minimal gagal dengan status/error yang jelas ke `current_job`), bukan diam di "idle".

### A2. Durasi campaign (Durasi Min/Max) vs hardcode 58-120 detik

**Root cause confirmed:** `find_highlights()` di `clipper_core.py` (~line 2774, komentar "Filter by duration (min 58s, max 120s)") pakai angka hardcode, terpisah total dari field "Durasi Min/Max" yang user set di Campaign. Hasil test buktiin: campaign di-set 20-40 detik, hasil clip tetap keluar di rentang 58-120 detik (94, 105 detik) — field campaign diabaikan diam-diam.

**Sebelum fix — WAJIB investigasi dulu, jangan langsung ubah:** Trace dari mana `find_highlights()` dipanggil dan cek apakah `durasi_min`/`durasi_max` dari campaign brief sebenarnya udah nyampe ke fungsi ini dalam bentuk parameter yang nggak kepake, atau emang nggak pernah di-pass sama sekali. Laporin balik ke saya: signature `find_highlights()` sekarang kayak apa, dan di titik mana (kalau ada) campaign durasi seharusnya masuk.

**Baru setelah itu, fix-nya:** ganti hardcode 58/120 jadi baca dari campaign durasi_min/durasi_max kalau campaign_id ada dan brief-nya punya field itu, fallback ke default 58/120 kalau campaign nggak set nilai itu (bukan dihapus total defaultnya, biar behavior lama nggak rusak buat campaign lain yang emang sengaja nggak isi durasi custom).

---

## TRACK B — RETRACT (klaim yang salah, jangan di-fix, tapi coba dibuktiin dulu)

### B1. "Deadlock ConfigManager karena Lock bukan RLock"

Saya cek `config_manager.py` — `self._lock` cuma dipakai sekali di `save_config()`. `load()` manggil `save_config()` tapi `load()` sendiri nggak pernah pegang lock itu duluan. Nggak ada nested lock acquisition di file ini atau di `app.py::save_ai_settings`. Klaim deadlock ini kelihatannya nggak match sama kode asli.

**Yang harus kamu lakuin:** coba REPRODUKSI beneran — jalanin skenario yang katanya bikin deadlock, kasih stack trace/log real kalau beneran nyangkut, DENGAN timestamp dan durasi berapa lama macetnya. Kalau nggak bisa direproduksi dalam waktu wajar, RETRACT klaim ini dari laporan final — jangan masuk daftar prioritas fix.

---

## TRACK C — KLARIFIKASI (data nggak konsisten, perlu rerun bersih)

### C1. Error "no JSON array" vs "429 rate limit" — dua klaim beda dari (katanya) run yang sama

`e2e_report.json` bilang error-nya `"AI response contains no JSON array"`. `e2e_report.md` bilang error-nya `429 Too Many Requests`. Campaign ID di kedua file juga beda (`camp_0dab320a` vs `camp_dadcd100`) — tanda ini dua eksekusi berbeda yang ke-mix jadi satu laporan.

**Yang harus kamu lakuin:**
1. Rerun `e2e_runner.py` SEKALI, bersih, pakai provider yang reliable (bukan proxy tunnel custom yang dipakai sebelumnya — pakai OpenAI atau Gemini resmi dengan kuota cukup, biar sinyal bug asli app nggak ke-mix sama masalah kuota API pihak ketiga).
2. `generate_markdown_report()` HARUS baca `e2e_report.json` yang barusan ditulis di run yang sama — jangan ada laporan md yang ditulis manual terpisah dari json. Satu run = satu json = satu md, isinya harus identik.
3. Kalau muncul lagi error "no JSON array", paste FULL raw AI response yang udah ke-log lewat `self.log()` (kodenya udah nge-print full response, tinggal di-capture) ke laporan — biar kelihatan itu beneran respons non-JSON dari model, atau ada hal lain.

Catatan: fungsi ekstraksi JSON di `clipper_core.py` (~line 2730-2772) itu SUDAH ada bracket-matching buat narik array JSON dari tengah teks yang dibungkus markdown/teks lain. Klaim "extractor nggak robust" kemungkinan nggak akurat — cek dulu raw response-nya sebelum nyimpulin itu bug di app vs provider yang ngebalikin sesuatu yang bukan JSON sama sekali.

### C2. 3 dari 7 clip punya durasi 00:00 — belum diinvestigasi sama sekali

Hasil run sebelumnya: `['01:34','01:34','01:34','01:45','00:00','00:00','00:00']`. Minta 16 highlight, cuma 7 yang balik, dan 3 di antaranya durasi nol. Ini nggak dibahas di laporan sebelumnya.

**Yang harus kamu lakuin:** investigasi kenapa. Kemungkinan: clip gagal generate di tengah jalan tapi tetep kecatet ke `data.json`/`get_stock_clips()` dengan data kosong (silent partial failure — pattern yang sama kayak bug-bug lain di app ini), atau memang API cuma ngasih 7 highlight valid dari 16 yang diminta dan sisanya di-drop tapi 3 sisanya ke-generate dengan durasi corrupt. Kasih root cause + apakah ini bug baru yang perlu masuk daftar prioritas.

---

## FORMAT LAPORAN LANJUTAN

Update `e2e_report.md` dengan struktur sama kayak sebelumnya, tapi tambahin section baru di paling atas:

| Item | Status Round 1 | Aksi Round 2 | Hasil |
|---|---|---|---|
| A1. tts_client crash | Confirmed bug | Fixed | (diff + bukti test) |
| A2. Durasi hardcode | Confirmed bug | Investigated → Fixed | (temuan trace + diff) |
| B1. ConfigManager deadlock | Klaim salah | Retracted / atau reproduced dengan bukti | (stack trace kalau reproduced) |
| C1. JSON error vs 429 | Inkonsisten | Rerun bersih | (root cause final) |
| C2. Clip durasi 0 detik | Belum diinvestigasi | Investigated | (root cause) |

Semua isi tabel di atas harus based on evidence yang beneran ada, bukan ringkasan naratif yang beda dari raw log. JANGAN tulis ulang manual — pastikan konsisten sama `e2e_report.json` dari run terakhir.
