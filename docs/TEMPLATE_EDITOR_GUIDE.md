# Editor template SSR_CLIPPER

Halaman **Editor** membuat desain yang bisa dipakai berulang pada campaign. Video yang diimpor di sini adalah contoh untuk desain; video produksi tetap berasal dari highlight setiap job.

## Alur pemakaian

1. Buka **Editor → Buat template**, isi nama, lalu pilih 9:16, 1:1, atau 16:9.
2. Pilih layer video, lalu impor video contoh. Atur posisi, ukuran dan isi/pasangkan video ke area desain.
3. Tambahkan **Subtitle**, **Teks**, **Gambar**, atau **Bingkai**. Klik objek di kanvas atau nama layer untuk mengatur propertinya.
4. Teks dapat berisi tulisan tetap atau **judul clip**. Subtitle produksi diisi dari ucapan clip; SRT/VTT/JSON contoh hanya digunakan untuk preview.
5. Geser objek dan ubah ukurannya melalui handle. Panel properti menyediakan font, warna, outline, perataan dan geometri. Gambar dapat ditambahkan lebih dari satu.
6. Atur urutan layer, kunci, sembunyikan atau hapus. Video utama wajib tersedia sepanjang clip.
7. Pilih aturan tampil: **sepanjang clip**, **dari awal**, **menjelang akhir**, atau **persentase durasi**. Aturan menjelang akhir mengikuti akhir highlight, bukan akhir video contoh.
8. Impor musik contoh bila perlu dan atur mixing. Sumber musik produksi tetap dipilih campaign, sesuai kebijakan musik wajib yang sudah ada. **Gunakan mixing khusus campaign** mengizinkan campaign mengganti volume, ducking, dan fade template; matikan untuk mengikuti template. Setelan eksplisit campaign lama tetap dipertahankan.
9. Putar preview dan gunakan panduan area aman TikTok/Instagram. Panduan tidak ikut masuk video final.
10. Klik **Uji render** untuk memeriksa MP4 dengan renderer produksi. Status, progress, pembatalan, dan hasil video tersedia di workspace.
11. Klik **Terbitkan**, lalu aktifkan versi tersebut pada **Campaign → Template editing** dan atur bobot pemilihan.

Draft tersimpan otomatis. Simpan manual, Undo/Redo, duplikat, arsip/pulihkan, dan impor/ekspor paket tersedia. Konflik penyimpanan menahan perubahan lama agar tidak menimpa draft yang lebih baru.

## Template dan versi

- Draft disimpan di `template_projects/`; revisi draft tidak mengubah versi terbit.
- Terbitkan menghasilkan `.ssrtemplate` dengan desain, gambar, dan font yang diperlukan, lalu memasangnya ke `template_library/`.
- Paket tidak memuat video contoh, musik contoh, transkrip contoh, atau URL preview.
- Campaign/job menyimpan identitas versi dan checksum. Versi lama tetap bisa dirender tanpa membuka Editor atau menyimpan folder draft asal.
- Arsip menyembunyikan template untuk pemilihan baru; file versi yang sudah dipakai job tetap tersedia.
- Paket MLT dari Kdenlive tetap didukung untuk produksi. Timeline MLT arbitrer belum dapat dibuka sebagai desain native yang dapat diedit.

## Preview dan hasil final

Preview kanvas membantu mengatur layout dengan cepat. MP4 **Uji render** adalah acuan untuk font, pemenggalan teks, warna kata aktif, ducking, dan fade audio. Waktu kata dari SRT/VTT dibagi dari rentang kalimat; JSON dengan waktu kata dapat dipakai bila diperlukan ketepatan contoh yang lebih tinggi.

Durasi output mengikuti sumber yang sebenarnya. Video contoh 30 detik tidak membatasi highlight 70 detik. Frame akhir dan audio sumber diperiksa setelah render.

Versi awal menyediakan komposisi video, teks, subtitle, gambar, bingkai dan aturan waktu. Animasi/keyframe, scene/B-roll adaptif, revisi clip individual, dan impor XML Alight Motion/After Effects belum tersedia pada Editor ini. Framing native menggunakan fit/center; pelacakan pembicara pada preset Clipper yang sudah ada tetap tersedia.

## Pengujian tanpa GUI

Tes memakai project, library, dan media sementara. Jalur draft → uji render → paket → consumer diverifikasi memakai FFmpeg sungguhan, termasuk sumber yang lebih panjang dari 30 detik serta folder authoring yang sudah dihapus. Tes frontend menggunakan DOM tanpa membuka aplikasi desktop.

Library Konva dibundel di `web/vendor/` dengan lisensi MIT. Native template dirender melalui FFmpeg; paket MLT tetap melalui runtime MLT. Tidak ada API AI yang diperlukan untuk membuat desain dan menjalankan Uji render. Caption Maker pada produksi tetap mengikuti pengaturan Clipper.
