# Benchmark framing lokal

Tanggal: 18 September 2026. Renderer akhir: versi 3, OpenCV untuk deteksi wajah, FFmpeg untuk pembacaan timestamp dan encoding.

## Hasil

**12 dari 12 potongan berhasil dirender** menjadi 1080×1920. Audio tetap tersedia pada semua hasil. Durasi stream video hasil sama dengan input potongan berdasarkan ffprobe. Hash empat file sumber asli tidak berubah.

| Sumber lokal | Resolusi asal | Sampel | Hasil teknis |
| --- | --- | --- | --- |
| Borong Bitcoin Episode 40 — September 2026 | 1920×1080 | Awal, tengah, akhir; sekitar 4 detik | 3/3 lulus |
| Buat Lu Yang Ngerasa Ketinggalan Jauh Dalam Hidup | 1920×1080 | Awal, tengah, akhir; 4 detik | 3/3 lulus |
| Dari Tukang Parkir Sampai Pengusaha Sukses, Kisah Calvin Outlet 23 | 1920×1080 | Awal, tengah, akhir; sekitar 4 detik | 3/3 lulus |
| Borong Bitcoin Episode 32 — Januari 2026 | 3840×2160 | Awal, tengah, akhir; sekitar 3 detik | 3/3 lulus |

Di antara 1.080 frame yang dianalisis, 8 memakai fallback seluruh frame. Angka tersebut adalah keputusan renderer, bukan ukuran akurasi pemilihan pembicara. Semua sampel didominasi satu wajah; korpus ini belum mewakili dialog beberapa orang atau trailer.

Pemeriksaan gambar pembanding pada empat contoh menunjukkan wajah tetap berada di dalam crop, termasuk wajah yang menoleh. Pada adegan satu pembicara, crop lama dan baru umumnya mirip. Hasil ini belum membuktikan renderer baru unggul secara visual untuk semua jenis konten atau mengukur getaran kamera secara menyeluruh.

## Masalah yang ditemukan dan diperbaiki

1. **Frame rate variabel:** salah satu sumber 4K memiliki nominal 24 fps, rata-rata sekitar 21,07 fps. Membaca setiap frame seolah intervalnya sama dapat menggeser momen visual terhadap dialog. Decoder baru menormalisasi memakai timestamp, dengan pengujian sintetis khusus yang memeriksa warna gambar pada detik 0,8 dan 1,3.
2. **Durasi audio melebihi gambar:** container sumber 4K sekitar 59,28 detik, tetapi stream videonya sekitar 53,58 detik. Perencanaan kini memakai durasi video, dan framing membatasi hasil sesuai durasi tersebut.
3. **Perebutan sumber daya:** pengambilan sampel 4K pada percobaan awal melewati timeout 120 detik saat thread FFmpeg tidak dibatasi. Setelah batas decoder/encoder/filter diterapkan, ketiga sampel 4K dan pengujian ulang selesai. Ini bukan pengukuran performa terkontrol karena beban komputer berubah selama sesi.

## Artefak

Data lengkap, path sumber, hash, keputusan kamera, waktu proses, video baru, dan gambar pembanding tersedia di:

- `output/_benchmarks/framing-20260916-verified/report.json` — hasil akhir 12 sampel.
- `output/_benchmarks/framing-20260916-verified/<id>/new.mp4` — hasil renderer versi 3.
- `output/_benchmarks/framing-20260916-verified/<id>/camera.json` — keputusan kamera dan timebase.
- `output/_benchmarks/framing-20260916-verified/<id>/comparison.jpg` — sumber, crop lama, crop baru pada titik tengah.
- `output/_benchmarks/framing-20260916/` — baseline sembilan sampel 1080p; percobaan awal berhenti ketika mengambil sampel 4K.
- `output/_benchmarks/framing-20260916-4k/` — tiga sampel 4K sesudah perbaikan.

Video dan gambar benchmark tetap lokal serta diabaikan Git.

## Menjalankan ulang

Gunakan direktori output baru agar laporan sebelumnya tetap tersedia:

```powershell
python tests/benchmark_framing.py --source 'path/video.mp4' --output 'output/_benchmarks/percobaan-baru'
```

Untuk memakai sampel yang sama dengan renderer saat ini:

```powershell
python tests/benchmark_framing.py --recheck 'output/_benchmarks/framing-20260916/report.json' --recheck 'output/_benchmarks/framing-20260916-4k/report.json' --output 'output/_benchmarks/verifikasi-baru'
```

Skrip tidak memanggil AI atau layanan publikasi. Pembandingan berikutnya perlu menambahkan banyak pembicara, perpindahan scene tajam, wajah tertutup, adegan tanpa wajah, dan pengujian MediaPipe pada lingkungan yang kompatibel.
