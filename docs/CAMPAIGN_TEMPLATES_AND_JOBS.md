# Template campaign dan beberapa job

## Membuat clip

Create Clip memiliki empat kelompok input:

1. **Sumber video:** link YouTube atau file video lokal. Beberapa baris sumber
   menghasilkan beberapa job, satu job untuk setiap sumber.
2. **Campaign:** brief dan template editing yang digunakan untuk job tersebut.
3. **Jumlah clip:** jumlah per sumber, atau AI menentukan berdasarkan highlight
   yang memenuhi kriteria.
4. **Cookie:** file cookies.txt untuk sumber yang membutuhkan autentikasi.

Pengaturan fitur, model, bahasa subtitle, dan gaya subtitle tidak lagi berada
di Create Clip. Bahasa mengikuti campaign; konfigurasi penyedia AI berada di
Settings.

## Template editing di campaign

Daftar template bawaan berisi **Standar**, **Podcast Kotak**, **Tegas 4:3**, dan
**Sinematik 16:9**. Aktifkan template yang
boleh dipakai dan isi **Bobot peluang** (1–100). Sistem mengacak satu template
untuk setiap clip, sehingga clip dalam satu job bisa memakai template berbeda.

- Bobot 70 dan 30 berarti peluang 70% dan 30% untuk tiap clip, bukan jaminan
  tepat tujuh dan tiga hasil dalam satu batch sepuluh clip.
- Template nonaktif tidak ikut pengacakan. Minimal satu template harus aktif.
- Jika hanya satu template aktif, semua clip memakai template tersebut.
- Campaign baru mengaktifkan Standar dan Podcast Kotak dengan bobot 50:50.
  Tegas dan Sinematik mula-mula nonaktif. Campaign lama mula-mula
  hanya mengaktifkan pilihan sebelumnya ketika dibuka, sampai pengguna mengubahnya.
- Pilihan tersimpan pada highlight, rencana editing, dan metadata clip. Resume
  serta render revisi memakai pilihan yang sama. Perubahan campaign hanya
  berlaku untuk job berikutnya; antrean memakai snapshot saat dibuat.

Fitur di dalam masing-masing template tetap. **Standar** berisi:

| Fitur | Setelan |
| --- | --- |
| Highlight Finder | Aktif |
| Caption Maker | Aktif |
| Subtitle Style | Clean |
| Hook Maker | Nonaktif |
| YT Title Maker | Aktif |

**Podcast Kotak** memakai format 720×720, 30 fps, bingkai hitam dengan sudut
membulat, dan subtitle kapital satu kata setiap kemunculan. Highlight Finder,
Caption Maker, dan YT Title Maker aktif; Hook Maker nonaktif. Detail visual dan
batas kecocokan referensi ada di [catatan template kedua](TEMPLATE_PODCAST_KOTAK.md).

**Tegas 4:3** memakai subtitle kapital kanan atas dan vignette.
**Sinematik 16:9** memakai B-roll campaign, teks bertingkat, serta aksen oranye.
Keduanya memakai subtitle bertimestamp kata, dengan hook mati. Sinematik memerlukan
aset berperan B-roll sebelum produksi. Lihat [panduan kedua referensi](TEMPLATE_TIMOTHY_REFERENCES.md).

Simpan pengaturan peluang pada campaign. Musik, framing, aset penutup, serta aturan
produksi juga disimpan pada campaign. Tombol **Lihat template** menampilkan fitur
template tersebut; tombol contoh memutar render dengan teks contoh. Judul clip menggunakan hasil analisis highlight; fitur ini tidak
menambahkan panggilan model judul terpisah.

CTA/penutup mengikuti campaign, termasuk pada kedua template Ruang. Jika file
penutup dipilih atau tersedia sebagai aset berperan `endcard`, file tersebut
ditambahkan dengan durasi yang diatur campaign. Tanpa aset dan tanpa kewajiban,
clip selesai tanpa CTA; logo, teks, flash, SFX dan minimum durasi CTA ikut dilewati.
Centang **Penutup ini wajib** jika diwajibkan campaign. Aturan campaign atau
aset penutup bertanda wajib tetap harus dipenuhi; produksi berhenti bila asetnya
belum tersedia. Durasi minimum CTA diperiksa saat CTA dipakai. Durasi 22,9 detik
merupakan pilihan aset campaign BEVAN, bukan durasi bawaan semua template.

Backend menyimpan identitas dan versi template, lalu mengambil setelan fitur
untuk pekerjaan baru dari template tersebut. Parameter editing lama dari halaman
Create Clip tidak dapat menimpa template. Gaya Clean memakai renderer `minimal`.

Campaign lama tanpa identitas template memakai Standar. Pembacaan halaman tidak
menulis ulang konfigurasi. Pekerjaan yang sudah masuk
antrean tetap memakai snapshot campaign dan opsi lamanya. Video yang sudah
dirender tidak berubah. Render revisi atas clip dengan template Standar tetap
memakai fitur Standar; revisi clip lama tetap kompatibel dengan gaya lamanya.

## Job dan antrean

Form bisa dipakai lagi setelah permintaan pembuatan job diterima. Job baru masuk
antrean walaupun job sebelumnya sedang berjalan. Pilih job pada daftar untuk
melihat jumlah clip, progress, clip yang menunggu/diproses, dan error milik job itu.
Detail awalnya tertutup; klik job yang sama lagi untuk menutup detailnya.

Nama file digunakan untuk sumber lokal. Untuk link, judul video dimuat di latar
tanpa mengunduh video; kegagalan pembacaan judul tidak membatalkan job. Produksi
tetap memperbarui judul dari informasi sumber yang berhasil dibaca.

Job diproses berurutan. Clip di dalam satu job tetap mengikuti batas worker
campaign. Urutan job mengikuti waktu masuk antrean; pembaruan judul dan progress
tidak mengubah urutan tersebut. Antrean lokal memerlukan aplikasi/worker aktif.

## Cara mencoba

1. Buka ulang aplikasi setelah perubahan kode.
2. Buka campaign, aktifkan template yang boleh dipakai, atur bobot, lalu simpan.
3. Buat job dari sumber pertama.
4. Saat job tersebut berjalan, masukkan sumber kedua dan buat job lagi.
5. Pilih masing-masing job. Pastikan judul, clip, progress, antrean, dan error
   sesuai dengan sumber yang dipilih. Periksa template yang tercatat pada setiap clip.

Pengujian kode dilakukan dengan data sementara dan layanan tiruan. Uji GUI,
pengambilan judul dari link nyata, serta produksi AI nyata diserahkan kepada
pengguna sesuai permintaan.

## Jadwal upload, durasi, dan musik

- Di **Campaign → Hubungkan Akun**, pilih akun dan simpan campaign terlebih
  dahulu. Setiap akun hanya memiliki **Jadwal jam upload** dan **Maks upload per
  hari**. Tambahkan jam yang diperlukan, lalu tekan **Simpan jadwal akun**.
  Audiens dan bahasa akun mengikuti campaign yang sudah disimpan. Akun tidak
  dapat memakai campaign dengan lingkup audiens atau bahasa yang bertentangan.
- Jam bawaan: **09:00 AM** dan **02:30 PM**. Batas harian adalah maksimum;
  jika hanya ada dua slot jam, batas lima tidak membuat tiga slot tambahan.
  Kuota dihitung lintas campaign dan batch untuk akun yang sama.
- Semua jadwal memakai **WITA (Asia/Makassar)** dan format **AM/PM**. Zona hanya
  bisa diubah di **Settings → Zona waktu global**. Perubahan zona tidak menggeser
  waktu tayang publikasi yang sudah dijadwalkan; tampilan mengikuti zona baru.
  Buat preview distribusi baru setelah mengganti zona atau jadwal akun.
- Di **Review & Upload → Preview distribusi**, edit tanggal dan jam langsung
  pada kolom **Jadwal**, kemudian tekan **Simpan jadwal** pada baris tersebut.
  Upload tersedia setelah semua perubahan berhasil disimpan. Waktu lewat,
  bentrok pada akun yang sama, dan pelampauan kuota ditolak tanpa mengubah
  jadwal tersimpan. Edit ini berlaku sebelum paket dikirim ke provider.
- Rentang durasi merupakan batas, bukan target 30 detik. Pemilih highlight
  mencari konteks dan penyelesaian; perbaikan akhir ucapan boleh memakai sisa
  rentang untuk menyelesaikan jawaban. Clip lengkap yang berdurasi 30 detik
  tetap valid. Tanda baca/transkrip dan jeda audio membantu, tetapi kesinambungan
  cerita tetap perlu diperiksa pada Review.
- **Semua render baru wajib memakai musik**, baik file campaign maupun pilihan
  otomatis. Jika pemilihan/pencampuran gagal atau track hening, clip ditandai
  gagal dan tidak dinyatakan selesai. Resume dapat mencoba pemilihan otomatis
  lagi; untuk mengganti file/pengaturan campaign, simpan lalu buat job baru.
  Render revisi menyediakan penggantian musik untuk clip yang sudah tersedia.

Video hasil lama tidak berubah sendiri. Buat job baru atau gunakan **Render
revisi** agar perubahan akhir ucapan dan musik diterapkan.
