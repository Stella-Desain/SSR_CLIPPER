# Template Podcast Kotak dan akhir ucapan

Referensi: `snaptik_7685697240035265812_v3.mp4`, 720×720, 30 fps, 44,367 detik.
Analisis dilakukan dari frame file lokal; musik referensi tidak dimasukkan ke template.

## Tampilan yang diterapkan

- Kanvas 720×720, 30 fps. Framing pembicara mengikuti rasio kotak, tanpa melewati
  crop vertikal 9:16 terlebih dahulu. Sumber dengan rasio yang sama tetap utuh.
- Aperture pada x=10..709 dan y=5..712, radius sudut 50 piksel, bagian luar hitam.
- Subtitle putih kapital per kata, pusat sekitar (360,416). Contoh KESUKSESAN
  mempunyai ukuran tinta sekitar 201×26 piksel. Pergantian kata langsung,
  tanpa animasi pop yang tidak terlihat pada referensi.
- Semburat abu-abu biru tetap di bagian atas teks, outline/bayangan tipis.
- Montserrat Black dibundel dengan lisensi OFL, lalu proporsinya disesuaikan.
  Ini font yang paling dekat dari perbandingan yang dilakukan, bukan identifikasi
  font asli yang terkonfirmasi. **Kesamaan piksel 100% belum tercapai/dibuktikan.**
- Warna dan isi footage tetap berasal dari sumber. Template tidak menambahkan
  wajah, latar studio, atau grading gelap yang belum terbukti sebagai efek editing.

Subtitle memerlukan timestamp per kata dari Caption Maker. Jika penyedia hanya
menghasilkan waktu per kalimat, render memberi error yang menjelaskan kebutuhan
tersebut; sistem tidak membagi durasi kalimat secara rata seolah waktu kata diketahui.
Ukuran kata panjang menyesuaikan agar tetap muat. Jeda ucapan tetap tanpa subtitle.

Musik, footage wajib, penutup, dan review tetap mengikuti campaign. Penutup
dirender ke kanvas yang sama. Hasil akhir baru tersedia untuk review setelah
seluruh proses, termasuk pencampuran musik dan pemeriksaan audio, selesai.

## Ucapan yang terpotong

Pada **Bangkit Saat Dunia Hancurkanmu!**, rentang sumber lama adalah
03:13.799–03:42.000. Durasi hasil sesuai potongan, tetapi teks masih berlanjut.
Kalimat berikutnya selesai pada jeda audio 03:44.534–03:44.889. Pemilih batas
menghasilkan akhir 03:44.712 (durasi materi sumber 30,913 detik).

Sebelum render, akhir highlight kini dicocokkan dengan tanda akhir kalimat atau
jeda yang didukung transkrip. Subtitle YouTube yang bertumpang tindih memerlukan
jeda audio lokal agar waktu tampilan cue tidak keliru dianggap akhir ucapan.
Jika akhir terdekat tidak muat dalam durasi campaign, sistem memilih akhir utuh
sebelumnya atau melewati highlight yang tidak memenuhi syarat. Peringatan
ketidakpastian diteruskan ke Review; waktu permintaan dan hasil penyesuaian disimpan.

Video lama tidak ditimpa. Gunakan **Render revisi** pada clip tersebut atau buat
job baru untuk menerapkan perbaikan. Hasil AI dan kesinambungan makna tetap perlu
didengarkan pada review; jeda atau tanda baca bukan bukti sempurna bahwa satu
gagasan sudah lengkap.

## Verifikasi lokal

Tes memakai FFmpeg asli dengan media sementara: ukuran/bingkai, timestamp kata,
jeda, audio, durasi, penutup, preview campaign, dan dua format template dalam satu
job. Pemilihan bobot, snapshot, resume, dan revisi juga diuji. Tidak memakai GUI,
layanan AI berbayar, atau upload nyata.

Artefak pemeriksaan lokal berada di `output/_reference_analysis/template2/`:
`template-preview.mp4` (teks contoh pada latar netral), `caption-comparison.png`,
frame referensi, dan hasil tes. Folder output tidak disertakan dalam Git.
