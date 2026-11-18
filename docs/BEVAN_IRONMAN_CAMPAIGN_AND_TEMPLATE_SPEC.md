# BEVAN Ironman — brief baru dan spesifikasi referensi

Status: brief publik dan referensi lokal sudah diperiksa. Dua template berbasis
recipe native kini dipakai untuk tiga video uji; pilihan preset di editor visual
belum diintegrasikan. Campaign aplikasi baru: `camp_8d3c32dfe5b9`, terhubung ke
Anak.clipo. Lihat `IRONMAN_TEST_VIDEO_DELIVERY.md` dan `publication-result.json`
untuk hasil render dan status pengiriman yang terverifikasi.

## Campaign yang berlaku

- Nama: **BEVAN PRAMUDITO (Hanya Clip Bahasan Ironman Triathlon)**.
- Sumber: https://app.clippo.id/campaigns/cmu8mx81e0fwab826k9w6pug7
- Snapshot publik: `output/ironman-reference-20261013/campaign-public-data.json`.
- Durasi: 15–180 detik. Hook berada pada 5 detik pertama dan harus memuat kata
  **IRONMAN**. Fokus pada pencapaian Bevan dan wajahnya.
- Materi berasal dari tautan resmi campaign. Referensi hasil edit clipper digunakan
  untuk mengamati gaya, tidak dijadikan bahan mentah untuk render berikutnya.
- Tag TikTok/Instagram: **@bevanpramudt**.
- Hashtag: **#bevanpramudito #narrativelabs #ironman #ui #crypto**.
- Kolom CTA berisi **“-”**. Brief yang dibaca tidak mewajibkan footage GMGN,
  logo GMGN, link referral di bio, ataupun penutup 22,9 detik.
- Default penutup untuk campaign ini: payoff pencapaian. Infrastruktur template
  tetap dapat menerima CTA opsional sesuai campaign lain.
- Larangan yang mempengaruhi isi: flexing, klaim profit pasti, menyerang kreator
  atau brand lain, menjadikan kreator lain sebagai fokus, wajah anak yang tidak
  terkait, dan mengambil hasil edit sesama clipper.

Aturan pengajuan yang tercantum: views organik, minimal 1.000 views, like rate
minimal 0,5%, akun minimal 10 followers, dibuat selama periode campaign, dan
video/hashtag tetap tersedia selama 180 hari. Verifikasi kelayakan dilakukan
terpisah setelah publikasi; akun dan statistik belum diperiksa pada tahap ini.

## Referensi lokal dan koreksi terhadap Gemini

| Bagian | Video A | Video B |
| --- | --- | --- |
| File | `snaptik_7687763181590121735_v3.mp4` | File berawalan `AQPY63Oba4SD272...` |
| Video | 20,566667 detik, 576×1024, 30 fps | 33,4 detik, 720×1280, 25 fps |
| Kontainer | 20,566667 detik | 33,621088 detik; belum membuktikan panjang audio sama dengan video |
| Hook | Kartu putih, huruf hitam tebal kapital, garis merah di atas | Kartu putih, teks hitam regular rata kiri, IRONMAN merah |
| Waktu hook | Masuk pada awal video, masih melintasi cut pantai→gym, hilang sekitar 5,33 detik | Tampak selama opening kampus sekitar 0–5 detik |
| Letak kartu terukur | x 8,33%, y 65,53%, lebar 83,51%, tinggi 12,50% | x 2,22%, y 43,52%, lebar 95,28%, tinggi 27,03% |
| Konten utama | Pantai, gym, latihan beban, start renang, masuk laut, sepeda, lari, finish | Kampus, persiapan, renang kolam, gym, registrasi, makanan, lomba, finish |
| Framing | Mayoritas mengisi kanvas vertikal | Banyak bagian ditempatkan dalam bingkai abu-abu dengan viewport berbeda menurut aset |
| Foto akhir | Mulai sekitar 17,83 detik; ada pulse terang dan rotasi, bukan foto statis tanpa efek | Mulai sekitar 30,36 detik; pose penutup serupa dengan A |
| CTA referensi | Tidak tampak | Tidak tampak |

Kartu diukur dari frame 1,00 detik menggunakan komponen piksel putih; batas
sekitar 1–2 piksel dapat dipengaruhi kompresi. Waktu cut berasal dari deteksi
FFmpeg yang kemudian dicocokkan dengan frame lokal. Daftar kandidat cut tetap
disimpan karena flash, perubahan framing, dan gerak kamera dapat terbaca sebagai
cut; jumlah kandidat tidak sama dengan jumlah shot nyata.

Koreksi penting:

1. Hook A bukan hanya 0–2 detik. Ada animasi masuk dan perubahan posisi menjelang
   keluar. Hook B berlangsung sekitar 5 detik, bukan hanya 4 detik.
2. Kanvas B tetap 9:16. Bingkai abu-abu tidak membuktikan output 16:9. Inset pada
   contoh 5 detik sekitar 90% lebar dan tinggi, dengan margin sekitar 5%; bagian
   lain memiliki viewport berbeda. Mode fit perlu mengikuti tiap aset.
3. Foto akhir A memiliki perubahan rotasi dan luminans. Pengukuran pencocokan
   fitur relatif terhadap frame 18 detik menunjukkan rotasi sekitar −5,76° pada
   frame 20,33 detik dan luminans rata-rata naik dari sekitar 119,6 menjadi 165,9.
   Nilai relatif ini bukan parameter project asli. Pulse terdeteksi berulang
   sekitar 0,5 detik; interval tersebut belum membuktikan BPM lagu.
4. Timeline Gemini masih menyisakan rentang waktu kosong dan menggabungkan
   sejumlah perubahan visual. Penilaian pacing tidak cukup berdasarkan label
   EDM/anthem. Tabelnya tidak dipakai sebagai edit decision list final.
5. Font, identitas lagu, level audio, BPM, dan ada/tidaknya suara latar belum
   diverifikasi secara independen. Tidak ada alasan menerapkan font Bebas Neue,
   subtitle satu kata, atau vignette tebal dari template Ruang ke dua referensi ini.
6. Klaim “cuan 187 miliar” adalah teks referensi A, bukan fakta yang diverifikasi
   oleh frame. Hook produksi mengikuti fokus prestasi dalam brief baru.

## Satu keluarga montase, dua variasi

Keduanya membangun cerita lewat rangkaian visual, berbeda dari template podcast
Ruang. Jumlah talking head atau batas sisipan B-roll 10–12% tidak dipakai untuk
montase ini. Urutan footage ditentukan oleh perkembangan cerita dan bukti visual.

### Montase Prestasi · Dinamis

- Pembuka 5 detik dengan kartu putih, judul kapital tebal, aksen garis merah.
- Kartu boleh tetap melintasi pergantian footage opening.
- Urutan: tokoh → persiapan/latihan → renang → sepeda → lari → finish.
- Footage mayoritas memenuhi kanvas; crop harus mempertahankan tokoh dan aksi.
- Foto payoff 2–3 detik; pulse/rotasi menjadi parameter yang bisa disesuaikan.
- Contoh hook sesuai arah brief: **MAHASISWA UI INI TAKLUKKAN IRONMAN DI USIA 21 TAHUN**.

### Montase Prestasi · Editorial

- Pembuka 5 detik dengan foto/konteks UI dan kartu teks rata kiri.
- Kata IRONMAN diberi aksen merah; teks lain hitam regular.
- Urutan: konteks tokoh → persiapan → tahapan lomba → finish → foto pencapaian.
- Warna bingkai dan fit setiap aset dapat diubah, mengikuti karakter referensi B.
- Contoh hook: **Bikin Bangga! Bevan Menuntaskan IRONMAN Triathlon**.

Parameter bersama: teks, font, warna, kotak, posisi/ukuran, durasi hook, pilihan
footage, urutan adegan, rentang sumber, framing, musik, efek payoff, dan CTA.
Subtitle dialog/TTS tidak diaktifkan otomatis pada montase berbasis musik.
Output produksi yang direkomendasikan 1080×1920; FPS referensi tetap tercatat
sebagai metadata terpisah. Musik produksi perlu sumber dan izin penggunaan yang
jelas sebelum render siap dipublikasikan.

## Bahan dan pencegahan pengulangan

- Folder foto Ironman resmi menyediakan dua file HEIC. Identitas, ukuran,
  checksum lokal, dan turunan PNG dicatat terpisah pada `official-photo-assets.json`.
- Root B-roll yang dibaca kini memiliki 64 entri, termasuk folder dan shortcut.
  Shortcut bernama Ironman project, Running New, VLOG Bevan, dan Bevan Struggle
  perlu diselesaikan ke target sebelum dianggap sebagai koleksi siap dipakai.
- Connector metadata saat ini tidak mengembalikan `shortcutDetails` pada respons
  yang diperiksa. Target shortcut tidak ditebak; statusnya unresolved.
- Banyak folder lifestyle tidak cocok untuk kisah Ironman. Materi dipilih dari
  aksi persiapan dan lomba yang memperkuat alur, dengan Bevan sebagai fokus.
- Identitas raw asset, rentang adegan, kelompok visual mirip, batch/clip yang
  memakai, dan status review perlu dicatat. Opener dan payoff ikut rotasi.
- Scene yang serupa di A dan B (sepeda, lari jembatan, gerbang finish, foto bendera)
  menjadi petunjuk mencari bahan asli, bukan file sumber produksi.

## Bukti yang disimpan

Direktori `output/ironman-reference-20261013` berisi snapshot brief, input Gemini,
metadata/hash dua referensi, frame tiap detik, kandidat cut, audit transisi A,
pengukuran layout/rotasi, inventory Drive, dan foto resmi. Spesifikasi JSON
disimpan pada `verified-template-spec.json`. Tahap berikutnya adalah melengkapi
indeks bahan asli dan membangun renderer montase dari parameter tersebut.
