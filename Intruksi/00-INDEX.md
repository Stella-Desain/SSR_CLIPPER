# INDEX — Instruksi Fix Bug (AutoClipper Web)

10 file task, per halaman ada 2 file:
- `*-terputus.md` = GUI sudah ada tapi tidak nyambung ke backend / logic salah / hardcode.
- `*-gui-belum-ada.md` = backend/logic sudah ada & dipakai, tapi GUI-nya belum dibuat sama sekali.

## Urutan pengerjaan yang disarankan
1. `01-dashboard-terputus.md` + `01-dashboard-gui-belum-ada.md`
2. `02-createclip-terputus.md` + `02-createclip-gui-belum-ada.md`
3. `03-stockclip-terputus.md` (kerjakan task 1-3,5 dulu) → `03-stockclip-gui-belum-ada.md` (endpoint upload) → balik ke `03-stockclip-terputus.md` task 4 & 6 (Upload Semua & onUpload, dependency ke endpoint upload)
4. `04-settings-terputus.md` + `04-settings-gui-belum-ada.md`
5. `05-global-terputus.md` + `05-global-gui-belum-ada.md`

## Cara pakai (per file)
1. Kasih 1 file MD ke Gemini 3.1 Pro utuh, tanpa dipotong.
2. Suruh Gemini kerjakan task satu-satu sesuai urutan di file, dan wajib lapor: file yang diubah + ringkasan tiap task.
3. Output Gemini dibawa balik ke sini (Claude) untuk direview sebelum lanjut ke file berikutnya.

## Aturan global (berlaku di SEMUA file task)
- Scope HANYA task yang tertulis di file itu. Dilarang refactor/ubah fitur lain di luar task.
- Dilarang hapus kode yang masih terpakai. Kalau ragu dipakai atau tidak, grep dulu, baru putuskan.
- Line number di dokumen ini adalah PERKIRAAN (kode bisa sudah geser) — cari elemen berdasarkan nama fungsi/id/class, bukan cuma nomor baris.
- Kalau task butuh keputusan produk yang ambigu (misal: scope fitur search, logic AI baru yang belum ada) — JANGAN dikarang/diasumsikan sendiri. Buat implementasi minimal yang aman + TODO comment jelas, dan laporkan sebagai "butuh keputusan" alih-alih pura-pura selesai.
- Reuse logic backend yang sudah ada (di file lama `pages/*.py`, `*_uploader.py`, dll) — jangan tulis ulang dari nol kalau function-nya sudah ada, cukup di-wiring/di-expose lewat WebAPI.
- Setelah tiap task: test manual dulu sebelum bilang "selesai".
