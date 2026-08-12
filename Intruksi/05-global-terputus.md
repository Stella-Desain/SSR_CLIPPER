# Global/Shell — GUI Terputus
File utama: `web/components/header.js`

ATURAN: kalau task butuh keputusan scope produk yang ambigu, JANGAN mengarang — pilih opsi paling aman (sembunyikan/nonfungsi eksplisit) + tulis TODO, laporkan sebagai butuh keputusan.

## Task 1: Search bar "Search anything..." decorative
- Masalah: tidak ada handler/endpoint search. Scope fitur ini belum jelas (search apa: job? campaign? clip?).
- Fix: JANGAN implement fitur search yang mengarang scope sendiri. Ambil salah satu:
  - Opsi A (disarankan, aman & cepat): implementasi client-side filter sederhana yang search job/campaign berdasarkan nama, dari data yang sudah ada di frontend (tidak perlu endpoint backend baru).
  - Opsi B: kalau tidak yakin data apa yang harus di-search, sembunyikan search bar (`hidden`) dan tulis `// TODO: scope search belum ditentukan` — jangan biarkan tetap terlihat tapi mati.
- Acceptance: search bar berfungsi (minimal filter data yang sudah ada) ATAU disembunyikan — jangan biarkan decorative-tapi-terlihat-aktif.

## Task 2: Wallet icon & notification bell tanpa `onclick`
- Fix: kalau tidak ada fitur wallet/notifikasi yang direncanakan dalam waktu dekat, sembunyikan (`hidden`) dua icon ini dari header supaya tidak menyesatkan user (terlihat clickable tapi mati). Kalau memang direncanakan, tulis `// TODO: fitur wallet/notifikasi belum diimplementasi` di kode, jangan buat UI palsu (misal dropdown kosong).
- Acceptance: kedua icon tidak lagi terlihat interaktif-tapi-mati — baik disembunyikan, atau berfungsi.

## Task 3: Username "Bintang SSR" hardcode
- Masalah: tidak ada endpoint user/profile, nama hardcode tidak relevan dengan user yang pakai app.
- Fix: kalau belum ada sistem auth/user profile, ganti string ini supaya ambil dari config (misal nama app/owner yang sudah ada di `config.json`), bukan nama orang hardcode. Kalau ada rencana sistem auth, tulis `// TODO: auth/user profile belum ada` — jangan buat sistem auth palsu.
- Acceptance: tidak ada lagi hardcoded nama personal yang tidak relevan; minimal diganti value dari config yang masuk akal.
