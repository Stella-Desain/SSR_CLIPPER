# Pengukuran audio final

Produksi dan render revisi sekarang mengukur audio dari file final setelah musik
selesai dicampur. Review menampilkan loudness terpadu (LUFS), true peak (dBTP),
dan rentang loudness (LU) pada bagian **Pengukuran audio final**.

Analisis memakai nilai `input_*` dari filter
[FFmpeg loudnorm](https://ffmpeg.org/ffmpeg-filters.html#loudnorm), sehingga angka
tersebut menggambarkan file yang akan diunggah. Hasil filter dibuang; analisis tidak
mengubah video atau mix. Pengukuran dibatasi durasi video final dan track audio
pertama, sesuai track utama yang dipakai renderer.

Sinyal hening, track audio tidak ada, puncak yang mencapai 0 dBTP, dan analisis yang
gagal menghasilkan peringatan review. Nilai tak terukur disimpan sebagai `null`,
bukan nol atau angka tanpa batas. Peringatan mengikuti mekanisme yang sudah ada
untuk mengembalikan produksi otomatis ke review manual. Tidak ada target loudness
universal yang dipaksakan; kualitas dialog, musik, dan emosi tetap dinilai dengan
mendengarkan preview.

Clip lama tetap dapat direview dan diunggah dengan alur yang ada. Pengukuran baru
tersedia pada clip yang baru diproduksi atau dirender ulang. Analisis tidak
memicu render ulang otomatis atas file yang telah disetujui.

Pengujian: `python -m unittest discover -s tests -p test_audio_analysis.py -v`
memakai audio sintetis. Pengujian membuktikan selisih level 6 dB, memastikan input
tidak berubah, membedakan hening dari 0 LUFS, dan menangani timeout serta respons
pengukuran tidak valid. Penilaian mix pada kumpulan referensi, preview musik
terpisah, dan sound native platform tetap merupakan pekerjaan lanjutan AUD-03–05.
