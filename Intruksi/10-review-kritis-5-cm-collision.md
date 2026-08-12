# REVIEW KRITIS #5 — Cek Key Collision `cm` + Lanjut Task 3

STATUS: G1 & G2 DITERIMA (dest_path lengkap, Browse wiring rapi). Task 2 Credit Watermark DITERIMA. Boleh mulai Task 3 (Hook Style) sekarang — tapi poin H di bawah WAJIB dijawab sebelum Task 3 dilaporkan selesai, karena ini potensi bug silent yang bisa merembet ke fitur lain.

## H. Potensi key collision prefix `cm` (Custom Provider vs Anthropic)

Fakta yang saya lihat dari 2 laporan berbeda:
- Laporan sebelumnya (E1): `cmUrl: cmUrlInput` — konteksnya "Custom Provider" (dari `04-settings-terputus.md` Task 2: endpoint URL + key + Test button Custom Provider).
- Laporan ini (G3): `cmValidateBtn: anthropic.testBtn`, `cmValidateStatus: anthropic.status` — dilabeli sebagai "Anthropic (Caption Maker)".

Prefix `cm` dipakai untuk 2 hal yang beda: Custom Provider DAN Anthropic. Ini bahaya kalau field-nya sampai ada yang nama key-nya PERSIS SAMA (misal Custom Provider ternyata juga punya `cmValidateBtn` untuk tombol Test-nya sendiri per instruksi `04-settings-terputus.md` Task 2 — "Sambungkan juga tombol Test-nya"). Kalau 2 assignment `cmValidateBtn: X` muncul di object literal yang sama, yang kedua akan diam-diam menimpa yang pertama — salah satu tombol Test (Custom Provider ATAU Anthropic) akan berhenti berfungsi tanpa error apapun.

### Wajib dijawab:
1. Tempel ISI LENGKAP object `fields` di `ai-settings.js` (semua key, jangan dipotong dengan `// [...]` lagi) — supaya bisa dicek manual tidak ada key yang duplikat.
2. Konfirmasi eksplisit: apakah Custom Provider (dari `04-settings-terputus.md` Task 2) SUDAH punya tombol Test yang tersambung sesuai instruksi lama? Kalau sudah, key apa yang dipakai untuk tombol Test Custom Provider tersebut — dan pastikan itu BUKAN `cmValidateBtn` (harus key yang beda dari punya Anthropic).
3. Kalau ternyata memang ada duplikasi key: perbaiki dengan rename salah satu supaya unik (misal Custom Provider pakai prefix lain, `cpValidateBtn` misalnya), lalu konfirmasi ulang kedua tombol (Custom Provider Test & Anthropic Test) jalan independen.

## Lanjut
Silakan kerjakan Task 3 (Hook Style). Jawab poin H di laporan Task 3 nanti (boleh digabung, ini cuma verifikasi bukan task baru). Catatan kecil: prefix `hm` dipakai untuk Gemini ("Hook Maker") — pastikan penamaan field baru untuk fitur "Hook Style" (Task 3) tidak numpang prefix yang sama (`h...`) dan bikin collision serupa seperti kasus `cm` di atas. Cek dulu field apa saja yang sudah ada sebelum nambah field baru.
