# Global/Shell — GUI Belum Ada
Nav/sidebar: `web/components/header.js` (atau file nav terpisah kalau ada). Logic lama ada di `pages/*.py`.

ATURAN TAMBAHAN: kerjakan 1 halaman per commit/PR, jangan gabung semua jadi 1 PR besar — biar gampang direview & ditest satu-satu.

Halaman lama yang punya logic aktif tapi belum ada nav item di web baru:
1. Session Browser
2. File Tree / Browse
3. Highlight Selection
4. Results Page
5. Contact Page

## Task per halaman (ulangi pola ini untuk tiap 1-5 di atas)
- Fix:
  1. Tambahkan nav item baru di sidebar untuk halaman tersebut.
  2. Buat component baru `web/components/[nama-halaman].js` sebagai view halaman itu.
  3. Reuse logic dari file `pages/[nama_halaman].py` lama yang sesuai — port logic-nya jadi method WebAPI (`app.py`) + UI di component baru. JANGAN tulis ulang logic dari nol kalau logic-nya sudah ada di file lama.
  4. Sambungkan routing pakai pattern navigasi yang sama dengan halaman lain (Dashboard/Create Clip/dst) — cari fungsi switch-view yang sudah dipakai, jangan bikin mekanisme baru.
- Acceptance per halaman: nav item muncul di sidebar, klik nav pindah ke halaman baru, halaman menampilkan data/fungsi asli sesuai logic dari `pages/*.py` lama (bukan placeholder kosong).

## Bonus/Cleanup (opsional, prioritas rendah — kerjakan terakhir kalau ada waktu)
- `get_asset_paths()` & `get_icon_data()` di `app.py` tidak pernah dipanggil dari `web/` manapun.
- Fix: grep dulu pastikan benar-benar tidak dipanggil di manapun (termasuk file yang belum sempat di-review). Kalau konfirmasi tidak dipakai dan tidak direncanakan dipakai → hapus. Kalau ragu, biarkan saja, jangan hapus asal-asalan.
