# Create Clip — GUI Belum Ada
File utama: `web/components/home.js`

ATURAN: jangan ubah signature backend `start_processing`/`AutoClipperCore`. Parameter `portrait` sudah ada, hanya perlu wiring dari UI.

## Task 1: Portrait Mode toggle hilang total dari UI
- Konteks: UI lama punya toggle Portrait Mode, UI baru tidak punya sama sekali. Padahal `start_processing()` & `AutoClipperCore` masih punya parameter `portrait`.
- Fix:
  1. Tambahkan toggle/checkbox "Portrait Mode" di `home.js`, taruh di area pengaturan clip (dekat toggle Highlight Finder/YT Title Maker).
  2. Masukkan value-nya ke object `fields`.
  3. Kirim sebagai `portrait` di payload `start_processing()` — nama parameter harus persis sama dengan yang sudah dipakai backend, jangan ganti nama.
  4. Pastikan juga ikut tersimpan/di-load di `save_default_config()` / `loadDefaultConfig()` (lihat file `02-createclip-terputus.md` Task 4) supaya konsisten.
- Acceptance: toggle Portrait Mode muncul di UI, value-nya benar-benar terkirim sebagai parameter `portrait` ke `start_processing()`, dan hasil proses clip portrait sesuai pilihan (verify minimal lewat parameter yang diteruskan ke core, kalau tidak bisa test full run).
