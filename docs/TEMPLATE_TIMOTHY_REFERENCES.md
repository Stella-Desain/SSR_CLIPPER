# Dua template dari referensi Timothy Ronald

28 September 2026. Dibuat setelah implementasi Highlight Finder per campaign selesai.
Pemeriksaan memakai file lokal, FFmpeg, transkrip tersimpan, serta tes tanpa GUI/API berbayar.
Video sumber dan konfigurasi campaign pengguna tidak diubah.

## Cara memakai

1. Buka **Campaign → Edit → Template editing**.
2. Aktifkan **Tegas 4:3** dan/atau **Sinematik 16:9**. Atur bobot peluang.
3. Untuk Sinematik, tambahkan gambar/video pada file campaign dan pilih peran
   **B-roll (template sinematik)**. File dengan subtitle/logo lama akan tetap menampilkan
   teks/logo tersebut; gunakan aset bersih untuk hasil baru.
4. Pilih musik campaign atau kebijakan musik otomatis, lalu simpan campaign.
5. Pada Create Clip, masukkan sumber, campaign, jumlah clip, dan cookie jika diperlukan.
6. Tinjau hasil final beserta penilaian highlight sebelum distribusi.

Dua template baru mula-mula nonaktif. Campaign lama mempertahankan template sebelumnya;
campaign baru tetap mengaktifkan Standar dan Podcast Kotak. Satu template aktif berarti
seluruh clip memakai template itu. Undian template tersimpan, sehingga retry/revisi memakai
pilihan yang sama. Kdenlive dan Template Studio tidak perlu dijalankan untuk kedua template ini.

## Bentuk kedua template

| | Tegas 4:3 | Sinematik 16:9 |
|---|---|---|
| Referensi | `ssstik.io_@tccc.134_1790533248864.mp4` | `ssstik.io_@yoaclips7_1790533294185.mp4` |
| Hasil | 1440×1080, 30 fps | 1920×1080, 30 fps |
| Gambar | Pembicara di kiri saat crop memungkinkan, vignette lebih gelap di kanan | Pembicara bergantian dengan B-roll; warna hangat dan vignette |
| Subtitle | Putih kapital, kanan atas, frasa pendek | Putih tebal; frasa penekanan memakai teks besar dengan aksen oranye |
| Font terbundel | Roboto Regular | Montserrat Black |
| Animasi teks | Pergantian frasa | Masuk singkat dengan blur/fade, lalu pergantian frasa |
| Highlight / caption / judul | Aktif | Aktif |
| Hook tambahan | Mati | Mati |
| Musik | Mengikuti campaign; wajib berhasil dicampur | Mengikuti campaign; wajib berhasil dicampur |

Subtitle mengikuti timestamp kata dari Caption Maker. Segment tanpa timestamp kata
ditolak dengan petunjuk konfigurasi, bukan dibagi menjadi waktu kata buatan. Frasa dipisah
menurut jeda, tanda baca, panjang teks, jumlah kata, dan durasi; jeda ucapan tidak diisi teks.
Penekanan sinematik saat ini memakai kata kunci dan frasa terakhir yang bukan hanya filler,
bukan penilaian emosi AI. Frasa dipisah setelah kata penting agar kata lanjutan seperti
“ya dan lu” tidak menjadi teks utama. Pasangan seperti “tanggung jawab” dan “lakukan sekarang”
tetap bersama ketika waktunya memungkinkan.

## B-roll dan urutan proses

Sumber → transkrip → highlight sesuai profil campaign → pemeriksaan akhir ucapan/konteks
→ undian template → filter wajah Additional → framing rasio → template/B-roll → subtitle
→ musik → watermark sesuai sosmed → pemeriksaan final → review → distribusi.

B-roll memakai urutan aset campaign yang diulang: tiga detik pembuka dari pembicara,
kemudian sampai tiga detik B-roll, dua detik pembicara, dan seterusnya. Aset singkat
memperpendek shot B-roll. Clip kurang dari tiga detik tetap menampilkan pembicara.
Penutup/sisipan sesudah materi utama tidak diganti B-roll. Panjang video tidak ditambah.

File B-roll disalin sebagai aset campaign dengan hash dan ikut snapshot job. B-roll bukan
scene wajib yang ditempel di akhir. Suara B-roll dibuang; suara sumber tetap berjalan pada
timestamp yang sama, lalu musik campaign dicampur. Aset hilang/berubah atau rentang
tidak valid menghentikan render. Sinematik aktif tanpa B-roll memberi blocker produksi;
draft campaign tetap dapat disimpan.

Pilihan rasio Additional otomatis mencakup **4:3** setelah template ini tersedia.
Scope sosmed dan aturan hanya/tidak digunakan pada template tetap berlaku.

## Batas kecocokan referensi

Ini template yang meniru struktur visual referensi, belum klaim identik piksel 100%.
File contoh adalah hasil video yang sudah menyatu: font/project asli dan aset B-roll
bersih tidak disertakan. Framing, konten, panjang ucapan, dan pilihan aset baru juga berubah.
Roboto/Montserrat adalah pendekatan font; pemilihan B-roll sekarang bergilir dari campaign,
belum mencari footage atau mencocokkan maknanya secara otomatis. Gambar diam tetap diam.
Bagian hitam sekitar tujuh detik pada akhir referensi pertama sengaja tidak dijadikan efek.

Tes lokal memeriksa kanvas, timing/jeda subtitle, teks besar satu kata, warna aksen,
durasi/audio, pergantian B-roll, perlindungan penutup, snapshot aset, serta job campuran
yang wajib bermusik. Hasil ASR/provider dan kualitas framing pada sumber panjang baru
tetap perlu diperiksa lewat review pengguna.

Implementasi: `services/reference_templates.py`, registrasi preset/template,
`services/core_workflow.py`, `services/framing.py`, dan `clipper_core.py`.
