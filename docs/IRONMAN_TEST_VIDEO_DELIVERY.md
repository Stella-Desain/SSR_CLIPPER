# Ironman — tiga video uji, 13 Oktober 2026

Campaign aplikasi: `camp_8d3c32dfe5b9`, **BEVAN PRAMUDITO (Hanya Clip Bahasan
Ironman Triathlon)**. Akun tujuan yang diminta pengguna dan diverifikasi melalui
Repliz: **Anak.clipo**, username **@anak.clip0**, platform Instagram.

Penerbitan terkonfirmasi pada **14 Oktober 2026 (WITA)**: ketiga jadwal provider
berstatus `success` dan ketiga catatan aplikasi berstatus `published`, masing-masing
dengan post ID Instagram. Pada pengiriman awal campaign memiliki satu akun,
39 aset lokal, dan tiga clip di stok. Revisi berikutnya menambah draft terpisah.

| Video | Post ID Instagram | File lokal |
| --- | --- | --- |
| Dinamis · 20 detik | `18117203194826350` | [MP4](<E:/PROJECT/Vibe code/C-Project/yt-short-clipper-2.0.5-beta/output/ironman-tests-20261013/clips/clip-001/master.mp4>) |
| Editorial · 26 detik | `18370675504246140` | [MP4](<E:/PROJECT/Vibe code/C-Project/yt-short-clipper-2.0.5-beta/output/ironman-tests-20261013/clips/clip-002/master.mp4>) |
| Film Burn · 22 detik | `18021471272928498` | [MP4](<E:/PROJECT/Vibe code/C-Project/yt-short-clipper-2.0.5-beta/output/ironman-tests-20261013/clips/clip-003/master.mp4>) |

Permalink tidak dikembalikan endpoint schedule. Endpoint Content Repliz
mengembalikan HTTP 402 untuk paket yang terhubung; status penerbitan diverifikasi
melalui jadwal dan post ID. Bukti terstruktur ada di `delivery-result.json`.

## Revisi 14 Oktober 2026

**Film Burn · Revisi penutup** mengganti detik 18–22 dengan frame Bevan tersenyum
dari vlog resmi pada detik 746,2. Zoom dikurangi dari 1,45 ke 1,12 dan crop
meliputi lebih banyak torso. Hook, tujuh adegan pertama, musik, transisi dan
durasi 22 detik tetap sama. File publikasi lama beserta hash-nya dipertahankan.
Versi revisi disimpan sebagai draft stok tersendiri, tanpa perubahan unggahan
Instagram: [MP4 revisi](<E:/PROJECT/Vibe code/C-Project/yt-short-clipper-2.0.5-beta/output/ironman-tests-20261013/revisions/film-burn-v2/master.mp4>).

**Jedag Jedug** menambahkan template native berbasis recipe yang dapat diedit,
dengan contoh Ironman 23,067 detik. Cut mengikuti beat musik yang diperkirakan
120 BPM, disertai punch-in, shake ringan, roll kecil, dua aksen film burn, dan
penutup stabil tiga detik. Contoh menjadi draft, tanpa upload otomatis:
[MP4 Jedag Jedug](<E:/PROJECT/Vibe code/C-Project/yt-short-clipper-2.0.5-beta/output/ironman-tests-20261013/jedag-jedug/master.mp4>).
Pengaturan dan cara memakai untuk campaign lain ada di `JEDAG_JEDUG_TEMPLATE.md`.

QA kedua draft memeriksa decode penuh, audio, durasi, tidak adanya interval
hitam/mute, serta frame di cut dan penutup. Tiga unit test memeriksa efek beat
yang konsisten saat seek, hook/ending stabil, serta validasi parameternya.
Template Jedag Jedug belum menjadi preset dropdown editor visual; file JSON
menyimpan pengaturan yang dipakai renderer native.

## Hasil dan template

| Uji | Gaya | Durasi | Film burn |
| --- | --- | --- | --- |
| 01 | Dinamis; kartu putih, kapital hitam, garis merah | 20 detik | 2 aksen, 0,4 detik |
| 02 | Editorial; kartu rata kiri, IRONMAN merah, inset abu-abu | 26 detik | 1 aksen, 0,5 detik |
| 03 | Variasi Dinamis dengan film burn lebih kuat | 22 detik | 3 aksen, 0,5 detik |

Dua definisi template dan tiga recipe ada di
`output/ironman-tests-20261013/templates` dan `recipes`. Kartu hook dibuat dari
teks, font, warna dan bounds yang dapat diedit; bukan gambar judul yang diratakan.
Recipe juga menyimpan footage, in/out sumber, framing, anchor pan yang halus,
musik, waktu transisi, intensitas, seed dan penutup. Renderer:
`services/achievement_montage.py`. Render ulang dengan:

```powershell
py -3.12 tools/render_ironman_tests.py render
```

Untuk campaign lain, ubah hook dan `constraints`, lalu pilih materi dan musik
yang sesuai. Renderer tidak mengunci kata IRONMAN di kode. Canvas memakai
dimensi genap dan 30 fps. CTA merupakan adegan opsional; bila campaign
mewajibkannya dan adegan CTA tidak tersedia, validasi menolak render.

Ini merupakan template native berbasis recipe yang sudah dipakai untuk video
uji, belum menjadi pilihan preset baru di editor visual aplikasi. Campaign
menyimpan lokasi recipe dan menggunakan stok hasil renderer tersebut. Tombol
render ulang editor highlight lama belum menjadi editor recipe montase.

## Bahan, musik dan batas pemeriksaan

Referensi clipper hanya dipakai untuk gaya. Sumber produksi berasal dari Drive
resmi campaign dan vlog resmi Bevan `u9d14ssEc0c`. Folder Ironman Sunshine
ditemukan melalui shortcut di VLOG Bevan → September. Inventory lokal berisi
45 raw asset yang diunduh; bahan lifestyle yang tidak relevan tidak dipakai.
Rentang setiap adegan dan kelompok visualnya tercatat dalam recipe dan metadata.
Tidak ada rentang footage yang diulang dalam satu video. Beberapa sesi latihan
yang sama muncul dari take berbeda pada video uji yang berbeda.

File HDR/HLG dikonversi ke SDR Rec.709 untuk render. Crop diperiksa per adegan;
portrait dan inset memakai anchor yang ditentukan dari posisi tokoh. Shot sepeda
memakai jalur anchor yang difilter agar tokoh tetap terlihat sepanjang geraknya. Tidak ada
tracking kepala yang berpindah mendadak. Foto penutup uji 01 memakai wobble dan
pulse ringan; uji 02 memakai freeze frame Bevan di area finish, sedangkan uji 03
memakai frame resmi setelah finish sebagai freeze frame.

Musik yang dipilih: **Drink's Afterhouse — Felixjd** dan **Trance Etude 2 —
Zeropage**, tercatat sebagai CC BY 3.0 pada metadata Jamendo. Kredit, tautan
sumber, lisensi, dan keterangan perubahan masuk caption. Musik ini berbeda dari
lagu referensi yang identitas dan izin penggunaannya belum terverifikasi.
Font produksi dipilih Arial Black/Arial; identitas font asli referensi tetap
belum dipastikan. Film burn merupakan tambahan yang diminta pengguna, bukan
klaim bahwa efek yang sama teramati di semua cut referensi.

Campaign baru tidak mewajibkan CTA GMGN atau link referral. Hook memuat IRONMAN
selama lima detik pertama. Caption memakai @bevanpramudt dan hashtag campaign.
Kelayakan pembayaran masih bergantung pada aturan campaign dan statistik
publikasi; render atau upload tidak membuktikan kelayakan pembayaran.

## Bukti hasil

`output/ironman-tests-20261013/qa-result.json` mencatat hash hasil render,
durasi, full decode, audio, dan status pemeriksaan visual. `registered-clips.json`
menghubungkan file dengan stok aplikasi. `publication-result.json` mencatat
status dan URL yang benar-benar dikembalikan provider; scheduled dibedakan dari
published. Pengiriman memakai pemeriksaan file, approval hash, akun tujuan dan
deduplikasi native aplikasi. Hasil pengiriman yang tidak pasti tidak dikirim ulang
secara otomatis.
