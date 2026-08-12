# Create Clip — GUI Terputus
File utama: `web/components/home.js` (+ `app.py` untuk `start_processing`, `save_default_config`)

ATURAN: scope hanya task di bawah. Jangan ubah signature backend (`AutoClipperCore`) kecuali diminta eksplisit di task. Line number = perkiraan.

## Task 1: Upload zone "Upload Your Cookies Here" cuma div kosong
- Lokasi: line 130. Tidak ada file input/handler — upload cookies asli cuma via tombol "Cookies" di header.
- Fix: reuse handler yang sudah dipakai tombol "Cookies" di header (cari fungsinya, jangan buat logic upload baru). Sambungkan div ini supaya klik/drop trigger handler yang sama (misal via `<input type="file">` tersembunyi + drag-drop event, yang manggil fungsi upload cookies existing).
- Acceptance: klik atau drag-drop file di zone ini berhasil upload cookies lewat jalur yang sama dengan tombol "Cookies" header.

## Task 2: `<select id="clips">` & `<select id="subtitle">` di-hide dari user
- Lokasi: elemen ber-class `hidden`. Backend `start_processing` sudah support `num_clips` & `subtitle_lang`, tapi user tidak bisa ubah dari UI (selalu default 5 & "id").
- Fix: hapus class `hidden` dari dua elemen ini, taruh di posisi wajar dekat pengaturan clip lainnya. Pastikan value-nya sudah ikut ke object `fields` (kalau belum, tambahkan) sehingga terkirim ke `start_processing()`.
- Acceptance: user bisa pilih jumlah clip & bahasa subtitle dari UI, dan payload `start_processing()` berisi value pilihan user (bukan selalu default).

## Task 3: Highlight Finder & YT Title Maker toggle kosmetik doang
- Lokasi: checked state disimpan di `fields`, ikut `save_default_config()`, tapi TIDAK dikirim ke `start_processing()`. Backend juga belum punya parameter untuk ini.
- Fix:
  1. Frontend: tambahkan kedua value toggle ini ke payload saat memanggil `start_processing()`.
  2. Backend (`app.py`): tambahkan parameter baru (misal `highlight_finder: bool`, `yt_title_maker: bool`) di method `start_processing`, teruskan ke `AutoClipperCore`/`clipper_core.py` sebagai parameter baru.
  3. Kalau logic pemrosesan untuk fitur ini BELUM ada sama sekali di `clipper_core.py` — cukup wiring parameter-nya sampai masuk ke core (terima tapi belum dipakai), tulis `# TODO: logic highlight_finder/yt_title_maker belum diimplementasi di core` — JANGAN mengarang logic AI/processing baru.
- Acceptance: toggle mempengaruhi payload request; backend menerima & meneruskan parameter sampai ke core (logic pemrosesannya boleh TODO kalau memang belum ada).

## Task 4: "Save Default Configuration" tidak pernah di-load balik
- Lokasi: tersimpan ke `config.json` key `default_clip_settings`, tapi tidak ada fungsi yang load balik saat init.
- Fix: buat fungsi `loadDefaultConfig()` (atau nama sejenis sesuai konvensi file ini) yang dipanggil saat component Create Clip di-init/mounted. Fungsi ini ambil `default_clip_settings` dari config (lewat WebAPI method yang sesuai — cek apakah sudah ada method get config, kalau belum buat yang simpel), lalu isi semua field form termasuk field yang di-unhide di Task 2.
- Acceptance: setelah save default config lalu reload halaman, semua field Create Clip (termasuk num_clips & subtitle_lang) terisi otomatis sesuai config tersimpan.
