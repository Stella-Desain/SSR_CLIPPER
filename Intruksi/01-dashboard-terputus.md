# Dashboard — GUI Terputus
File utama: `web/components/dashboard.js` (+ `app.py` untuk WebAPI/backend)

ATURAN: scope hanya task di bawah. Jangan refactor bagian lain. Line number = perkiraan, cari via nama elemen/fungsi.

## Task 1: Tombol "Restock Clip" mati total
- Lokasi: header Campaign card, ±line 168. Tidak ada `onclick`, tidak ada endpoint backend.
- Masalah: tombol ada di UI tapi tidak melakukan apa-apa.
- Fix:
  1. Cek `clipper_core.py` / `app.py`, cari apakah ada fungsi yang cocok untuk "restock" (kemungkinan: re-run/reprocess campaign yang sudah selesai). Kalau ADA fungsi yang jelas cocok → tambahkan `onclick` yang panggil WebAPI method baru, WebAPI method panggil fungsi tersebut.
  2. Kalau TIDAK ada fungsi backend yang jelas cocok → JANGAN mengarang logic baru. Tambahkan `onclick` yang munculkan toast/alert "Fitur belum tersedia" + tulis komentar `// TODO: backend restock_clip belum ada, perlu keputusan produk` di kode. Laporkan ini sebagai blocker di ringkasan akhir.
- Acceptance: klik tombol tidak lagi silent no-op — baik trigger action asli, atau tampilkan pesan jelas + TODO tercatat.

## Task 2: Tombol "New Clip" mati total
- Lokasi: header Jobs Proses, ±line 319. Tidak ada `onclick`.
- Fix: tambahkan `onclick` yang pindah ke view "Create Clip". Cari pattern navigasi antar-page yang sudah dipakai di project (misal fungsi `switchView()`/sejenis di `app.js` atau nav handler di `header.js`) dan pakai pattern yang sama — jangan buat mekanisme navigasi baru.
- Acceptance: klik "New Clip" berpindah ke halaman Create Clip.

## Task 3: Instagram count hardcode `12`
- Lokasi: ±line 74-78.
- Masalah: TikTok & YouTube count sudah dinamis via `refresh()`, Instagram masih statis.
- Fix: cari di `refresh()` bagaimana TikTok/YouTube count diambil (dari mana datanya, field apa). Terapkan pola yang sama untuk Instagram. Kalau data Instagram count belum di-expose oleh backend, tambahkan field itu di response endpoint yang dipakai `refresh()`, default `0` — JANGAN biarkan angka statis `12`.
- Acceptance: Instagram count berubah mengikuti data asli saat `refresh()` dipanggil, sama seperti TikTok/YouTube.

## Task 4: `makeTreeItem()` dead code
- Lokasi: line 179-259.
- Masalah: fungsi lengkap dengan data dummy, tidak pernah dipanggil (sudah digantikan render dinamis di line 376+).
- Fix: grep penggunaan `makeTreeItem` di seluruh project dulu untuk pastikan benar-benar tidak dipanggil di manapun. Kalau konfirmasi tidak dipakai → hapus seluruh fungsi ini.
- Acceptance: fungsi terhapus, dashboard tetap render tree dengan benar (tidak ada regresi, karena render sudah dihandle bagian dinamis di bawahnya).
