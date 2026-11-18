# Perpindahan framing yang stabil

## Masalah yang ditemukan

Pada hasil Podcast Kotak `job-202cb116a5c24bf7/clip-034`, frame 1016 (sekitar 33,87 detik) menampilkan seluruh sumber landscape dengan padding, sementara frame sebelumnya dan sesudahnya memakai crop. Kanvas MP4 tetap 720 × 720. Pergantian mode kamera selama satu frame menyebabkan kilatan yang terlihat penonton.

## Perbaikan

- Renderer menunggu konfirmasi mode selama sekitar 0,15 detik sebelum menerima perpindahan crop ↔ tampilan penuh.
- Gangguan deteksi yang singkat memakai crop stabil dari adegan yang sama. Frame dan audio tidak dibuang atau diperpanjang.
- Pada awal adegan, gangguan yang singkat dapat memakai crop dari deteksi berikutnya dalam adegan tersebut. Crop dan identitas pembicara tidak dibawa melewati pergantian adegan.
- Jika keraguan berlanjut, seluruh rentang tetap memakai tampilan penuh. Pilihan framing **fit** yang disengaja tetap berlaku langsung.
- Buffer dibatasi beberapa frame dan gambar yang ditunda tidak menyimpan piksel 4K melebihi kebutuhan hasil crop.
- `camera.json` mencatat frame yang distabilkan, mode yang diminta, dan setiap perpindahan mode. Identitas render memasukkan versi framing agar proses baru tidak mengambil render lama dari cache.

## Cakupan seluruh template dan jalur render

| Jalur | Perlindungan |
| --- | --- |
| Standar, Clean, Social, Bold, Podcast Kotak, Tegas 4:3, Sinematik 16:9, Ruang Founder/Witness | Pelacakan pembicara memakai renderer framing bersama dan konfirmasi perpindahan mode. |
| Pemanggilan portrait OpenCV/MediaPipe lama | Dialihkan ke renderer bersama, tanpa mengubah konfigurasi pelacakan milik worker lain. |
| Template native Editor | Layer sumber kontinu dan kanvas desain tetap; hasil diperiksa sebelum diterbitkan. Fit/center yang disengaja tetap mengikuti desain. |
| Template impor MLT | Kanvas manifest tetap; dimensi, durasi, dan audio diperiksa sebelum hasil menggantikan output. |
| Render baru, job campuran/acak, Render revisi, dan kelanjutan job | Pemeriksaan kanvas final berlaku setelah template, subtitle, musik, serta Additional selesai. Hasil dengan kanvas yang salah gagal sebelum finalisasi. |
| Versi TikTok/Instagram dan watermark | Ukuran hasil setiap versi harus sama dengan master sebelum dipilih atau dipakai kembali. |
| Preview campaign dan Uji render Editor | Preview campaign memeriksa kanvas, termasuk hasil tersimpan. Uji render memakai renderer native yang juga memeriksa kanvas. |

Komposisi, subtitle referensi/Podcast/Ruang, dan pencampuran musik turut memeriksa bahwa kanvas tidak berubah. Metadata baru menyimpan `render_validation` dengan ukuran kanvas yang lolos. Pemeriksaan ukuran ini melengkapi stabilisasi per frame; ukuran file saja tidak bisa mendeteksi kilatan konten pada kanvas yang ukurannya tetap.

Cache final dan preview memasukkan versi pemeriksaan render. Jalur penggunaan ulang portrait pada runner Bevan juga mensyaratkan versi framing baru. Hasil lama yang belum melewati perlindungan tidak dianggap sebagai render baru yang selesai.

## Verifikasi

`tests/test_framing_stability.py` menguji kehilangan deteksi satu–dua frame, awal/akhir video, adegan baru, ambiguitas berkepanjangan, dan crop sesaat di antara frame lebar. Tes FFmpeg memeriksa setiap frame output 1:1, 9:16, 4:3, dan 16:9, bingkai Podcast Kotak, jumlah frame, durasi, serta audio. Tes integrasi memastikan seluruh template bawaan menolak hasil dasar landscape yang tidak sesuai kanvas, dan versi sosmed yang salah rasio tidak menggantikan master.

Potongan 3,2 detik dari sumber asli di sekitar lokasi masalah menghasilkan 96 frame dengan crop 720 × 720 yang konsisten. Laporan lokal tersedia di `output/_render-diagnostics/real-excerpt/verification.json`.

Hasil lama tetap memerlukan render ulang untuk menerapkan perbaikan ini.
