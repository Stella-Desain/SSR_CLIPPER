# Create Clip — GUI Ada, Program Tidak Ada/Tidak Terhubung
File: `web/components/home.js`

## 1. Button "Cookies"
- Lokasi: `#cookies-btn`, home.js:30-34
- Status: program tidak ada
- Aksi: buat endpoint `upload_cookies(file_content)` / pakai `pywebview.create_file_dialog` untuk pilih file cookies.txt, simpan ke app_dir; wire tombol ini

## 2. "Upload Your Cookies Here" (upload-zone)
- Lokasi: home.js:123-131
- Status: program tidak ada
- Masalah: cuma `<div>`, bukan file input, tidak ada handler
- Aksi: sama seperti item 1 — implement file picker + endpoint simpan cookies

## 3. Toggle "Num Clips"
- Lokasi: home.js:97, id=`num-clips-toggle`
- Status: program ada TAPI salah wiring
- Masalah: nilai asli dikirim ke backend diambil dari `<select id="clips">` tersembunyi (default 5), TIDAK sinkron dengan toggle switch yang dilihat user
- Aksi: ganti toggle switch dengan kontrol angka yang benar-benar mengubah `clipsSelect.value` (stepper atau select terlihat)

## 4. Toggle "Portrait Mode"
- Lokasi: home.js:100, id=`portrait`
- Status: program tidak ada
- Masalah: checked-state tidak pernah dibaca; `start_processing()` (app.py) tidak punya parameter aspect ratio
- Aksi: tambah parameter `portrait: bool` di `start_processing()` -> teruskan ke `AutoClipperCore`; baca `homeView.fields.portrait.checked` di app.js saat submit (perlu tambah field `portrait` di return object home.js)

## 5. Button "Save Default Configuration"
- Lokasi: home.js:138-141
- Status: program tidak ada
- Aksi: buat endpoint `save_default_config(settings)` (num_clips, captions, hook, portrait, subtitle) -> simpan ke config.json; load kembali saat `init()`

## 6. Button "Copy" (terminal log)
- Lokasi: home.js:206
- Status: program tidak ada (murni frontend, tidak butuh backend)
- Aksi: `navigator.clipboard.writeText(terminal.textContent)` on click
