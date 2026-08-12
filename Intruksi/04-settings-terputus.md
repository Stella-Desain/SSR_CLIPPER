# Settings — GUI Terputus
File utama: `web/components/ai-settings.js` (+ `app.js` untuk event binding, `app.py` untuk `save_ai_settings`, `check_dependencies`, `_run`, `get_repliz_dashboard_url`, `get_account_stats`, `get_campaigns`)

ATURAN: scope hanya task di bawah. Jangan ubah signature `AutoClipperCore` — parameter `local_whisper_settings` sudah ada, tinggal wiring.

## Task 1: Tombol "Test" (OpenAI/Anthropic/Gemini) bind ke elemen hidden `dummyBtn`
- Masalah: di `app.js`, event listener terpasang ke `dummyBtn` (elemen hidden, tidak pernah masuk DOM), bukan ke tombol Test yang benar-benar terlihat (`openai.testBtn`, dst).
- Fix: ganti target listener di `app.js` dari `dummyBtn` ke id tombol Test yang asli & visible (cek nama id persis di `ai-settings.js`, jangan asumsi). Kalau `dummyBtn` memang tidak dipakai lagi di tempat lain, hapus elemennya.
- Acceptance: klik tombol Test yang terlihat di UI benar-benar trigger test koneksi API (bukan silent no-op).

## Task 2: Custom Provider (endpoint + key + Test) tidak masuk `fields`
- Masalah: elemen dibuat di UI tapi tidak dimasukkan ke object `fields`, jadi app.js tidak bisa baca value-nya, dan tidak masuk payload `save_ai_settings`.
- Fix: tambahkan input endpoint URL & API key Custom Provider ke object `fields`. Pastikan value-nya ikut ke payload saat `save_ai_settings()` dipanggil. Sambungkan tombol Test-nya dengan pattern yang sama seperti Task 1 (provider lain).
- Acceptance: isi Custom Provider → save → reload halaman → value masih ada (persist). Tombol Test Custom Provider berfungsi.

## Task 3: YT Title Maker dropdown tidak masuk payload `save_ai_settings`
- Fix: tambahkan value dropdown ini ke `fields` & payload `save_ai_settings`.
- Acceptance: pilihan tersimpan dan ter-load balik setelah reload halaman.

## Task 4: Whisper Model select tidak tersimpan & tidak dipakai backend
- Masalah: elemen dibuat tapi tidak masuk `fields` (jadi tidak pernah di-save/load), dan `_run()` di `app.py` tidak baca setting ini sama sekali — padahal `AutoClipperCore` sudah support parameter `local_whisper_settings`.
- Fix:
  1. Frontend: masukkan whisper model select ke `fields`, pastikan ikut save/load lewat `save_ai_settings`.
  2. Backend: di `_run()` (`app.py`), baca value whisper model dari settings tersimpan, teruskan ke `AutoClipperCore` sebagai `local_whisper_settings` — nama parameter harus sama persis, jangan ubah signature core.
- Acceptance: ganti whisper model di Settings, jalankan proses clip, parameter `local_whisper_settings` yang diteruskan ke core sesuai pilihan user (verify via log/print debug kalau perlu).

## Task 5: "Reload Model" (`#reload-model-btn`) tanpa listener
- Fix: tambahkan event listener. Cek dulu apakah sudah ada fungsi backend untuk reload/re-init whisper model. Kalau ada, sambungkan ke situ. Kalau belum ada, buat method WebAPI minimal yang re-init whisper model berdasarkan setting terbaru — jangan bikin logic loading model baru dari nol, cukup panggil ulang inisialisasi yang sudah ada di core kalau memungkinkan.
- Acceptance: klik "Reload Model" trigger proses reload, ada loading state & feedback sukses/gagal.

## Task 6: Dep status dots — deno & whisper selalu hardcode `True`
- Lokasi: `check_dependencies()` di `app.py`.
- Masalah: yt-dlp & ffmpeg sudah dicek asli, tapi `"deno": True, "whisper": True` selalu hardcode.
- Fix: implementasikan pengecekan asli untuk deno (misal cek binary `deno` ada di PATH / `shutil.which("deno")`) dan whisper (cek library/model whisper ready untuk dipakai) — ikuti pattern pengecekan yang dipakai untuk yt-dlp/ffmpeg di fungsi yang sama.
- Acceptance: dot status deno & whisper mencerminkan kondisi asli (merah kalau memang belum terinstall/ready).

## Task 7: Panel Repliz 100% dummy
- Elemen: Access Key, Secret Key, "Test Connection", "16 Account Connected" (hardcode), "Connect More" — nol koneksi ke backend.
- Fix (minimal viable, jangan overbuild):
  1. Sambungkan input Access Key & Secret Key ke save/load settings (persist ke config, pattern sama seperti provider AI lain).
  2. "Test Connection": buat endpoint WebAPI yang validasi credential ke Repliz API. Kalau tidak ada dokumentasi/spesifikasi API Repliz yang jelas di codebase, JANGAN pura-pura selalu sukses — buat stub yang return error jelas ("Repliz API belum terintegrasi") + tulis `# TODO` dan laporkan sebagai blocker.
  3. "16 Account Connected": ganti jadi angka asli dari `get_account_stats()` (lihat Task 8) — bukan hardcode.
- Acceptance: Access/Secret Key tersimpan & ter-load balik. Test Connection memberi response asli (bukan selalu "sukses" tanpa validasi).

## Task 8: `get_repliz_dashboard_url()`, `get_account_stats()`, `get_campaigns()` masih mock data
- Fix: ganti implementasi supaya panggil Repliz API asli (butuh credential dari Task 7). Kalau tidak ada dokumentasi API Repliz yang tersedia di codebase/project, JANGAN mengarang endpoint API. Tandai jelas `# TODO: butuh dokumentasi Repliz API` dan laporkan sebagai blocker ke user — JANGAN tandai task ini "selesai" kalau masih mock.
- Acceptance: data yang tampil di UI berasal dari API asli, ATAU ada laporan blocker eksplisit kalau memang tidak bisa dikerjakan karena kurang info API.
