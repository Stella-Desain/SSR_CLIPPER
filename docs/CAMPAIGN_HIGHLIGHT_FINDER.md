# Pencarian highlight per campaign

## Alur pengguna

1. Buat atau buka campaign. Isi brief dan lingkup audiens akun seperti biasa.
2. Isi **Profil audiens & pencarian highlight**: audiens yang dituju, pesan utama, topik, sudut pesan, pola pembuka, hal yang dihindari, dan konteks yang harus dipertahankan.
3. Opsional: tambahkan video pada **Referensi highlight**. Referensi membantu menjelaskan jenis potongan yang diinginkan; video tersebut bukan sisipan hasil editing.
4. Minta saran profil dari AI. Periksa usulan sebelum menerapkannya dan menyimpan campaign. Pengaturan dapat diisi manual tanpa menggunakan AI.
5. Pada Create Clip, masukkan sumber, campaign, jumlah clip, dan cookie. Profil pencarian dan pilihan template mengikuti campaign.
6. Saat review, periksa video final, alasan pemilihan, nilai kecocokan, dan kutipan bertimestamp dari sumber. Berikan penilaian bila diperlukan.
7. Gunakan penilaian review sebagai bahan usulan profil berikutnya. Perubahan baru berlaku setelah diterapkan dan campaign disimpan.

## Tanggung jawab profil dan template

Profil menentukan **apa yang layak dipotong**. Template menentukan **bagaimana potongan tersebut diedit**. Subtitle, musik, B-roll, warna, dan rasio template tidak boleh berubah menjadi syarat isi highlight hanya karena ada pada sebuah referensi.

Setiap campaign dapat memiliki beberapa pola highlight. Contohnya, dua referensi Timothy Ronald menunjukkan teguran tentang tanggung jawab pribadi dan dorongan ambisi menuju keberhasilan. Kesamaannya adalah tantangan langsung kepada penonton, pengembangan alasan/contoh/metafora, dan penekanan akhir. Ini hipotesis awal dari isi dua contoh, bukan bukti demografi penonton atau performa viral.

## Pemilihan kandidat

Kandidat dinilai untuk kecocokan audiens, kekuatan pesan, daya tarik pembuka, dan kelengkapan gagasan. Bobot dan batas nilai disimpan pada campaign. Nilai viral saja tidak menentukan urutan.

Sebelum diterima, kandidat harus sesuai audiens dan brief, mempertahankan konteks sumber, serta menyelesaikan gagasan. Kutipan dan rentang waktu yang dipakai sebagai bukti diperiksa terhadap transkrip sumber. Pemeriksaan akhir ucapan tetap berjalan sebelum rendering. Jika penyesuaian batas waktu mengubah materi potongan, penilaian harus diperiksa kembali.

Jumlah yang diminta merupakan target jumlah kandidat yang valid. Sistem dapat menghasilkan lebih sedikit ketika kandidat yang sesuai habis. Sistem tidak boleh menambahkan potongan yang tidak memenuhi aturan demi memenuhi kuota.

Penilaian makna tetap bergantung pada AI dan kualitas transkrip; nilai tinggi bukan jaminan konten akan viral. Alasan dan kutipan tersedia agar keputusan dapat diperiksa saat review.

## Referensi dan versi

- Referensi disimpan dengan peran `reference_highlight` dan identitas isi file. Referensi tidak termasuk aset wajib pada timeline.
- Analisis referensi mengikat identitas aset dan hash file. File berubah harus dianalisis kembali.
- Analisis ucapan memakai sidecar subtitle, model lokal yang sudah tersedia, atau layanan transkripsi yang dikonfigurasi melalui tindakan pengguna. Membuka halaman campaign tidak memulai analisis.
- Saran AI tidak otomatis menyimpan campaign dan tidak otomatis menimpa profil manual.
- Setiap pekerjaan membawa snapshot campaign beserta profilnya. Mengedit campaign tidak mengganti aturan pekerjaan yang sudah dibuat.
- Penilaian review tersimpan terpisah dari persetujuan upload. Merekam penilaian tidak mengubah video, caption, jadwal, atau persetujuan publikasi.

## Bukan pelatihan model

Sistem mengekstrak aturan dan contoh pola dari referensi lalu menggunakannya dalam prompt pencarian. Sistem ini tidak melakukan fine-tuning model dan tidak belajar diam-diam dari hasil publikasi. Perubahan profil selalu berupa usulan yang diperiksa pengguna.
