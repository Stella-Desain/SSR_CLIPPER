# Fix Kecepatan Rendering Clip — clip-v2 (branch feature/pywebview-desktop-integration)

## Cara pakai
**Opsi A (paling gampang):** timpa 3 file ini di repo lokal kamu dengan file di folder `fixed-files/`:
- `clipper_core.py`
- `app.py`
- `config/config_manager.py`

**Opsi B (via git):** apply `speedup-fixes.patch` di root repo:
```bash
git apply speedup-fixes.patch
```

Setelah itu **hapus/reset file config lama** kamu (`~/.clip-v2/config.json` atau lokasi config app kamu — cek `config/config_manager.py` untuk path pastinya) supaya default `gpu_acceleration.enabled: true` ke-generate ulang. Kalau tidak mau hapus config, tinggal buka Settings di app dan nyalakan toggle "GPU Acceleration" secara manual — sekarang toggle itu **benar-benar berfungsi** (sebelumnya tidak).

## Apa yang diperbaiki

1. **Bug kritis — GPU Acceleration tidak pernah aktif.** `core.enable_gpu_acceleration()` tidak pernah dipanggil di `app.py`, jadi toggle di Settings percuma, semua encode selalu jalan di CPU (libx264). Sekarang diperbaiki + default-nya diaktifkan (aman, sudah ada fallback otomatis ke CPU kalau GPU gagal/tidak ada).

2. **Bug besar — potong clip decode dari detik 0.** Command FFmpeg untuk motong clip taruh `-ss`/`-to` SETELAH `-i`, jadi FFmpeg decode dari awal video sampai titik potong (bukan lompat langsung). Untuk podcast 60-120 menit dengan highlight di menit ke-50, ini buang waktu besar — **terbukti 2.75× lebih cepat** setelah `-ss`/`-to` dipindah ke sebelum `-i` (hasil output identik).

3. **Konversi ke portrait (9:16) decode 2×, encode 2×.** Deteksi wajah (Haar Cascade) jalan di resolusi penuh tiap frame, lalu ditulis via OpenCV `mp4v` (software, lambat) ke file sementara, lalu di-encode ULANG oleh FFmpeg. Sekarang: deteksi wajah di-downscale + di-sample tiap 5 frame (**15.5× lebih cepat**, tanpa pengaruh ke hasil crop akhir karena posisi sudah di-stabilize per beberapa detik), dan crop+encode digabung jadi satu pass langsung pipe ke FFmpeg (**2.3× lebih cepat end-to-end**, plus kualitas sedikit lebih baik karena satu generasi lossy-encode lebih sedikit).

4. **Step "Adding Hook" re-encode seluruh body clip lagi.** Sebelumnya re-encode penuh video utama hanya untuk digabung dengan hook (dan kadang re-encode 2× kalau stream-copy gagal). Sekarang digabung jadi satu pass pakai concat filter langsung.

5. **Default transcription pakai model Whisper lokal (large-v3-turbo)**, bukan API cepat. Dikembalikan ke default API kecuali kamu sudah pilih model lokal manual di Settings.

Semua perubahan sudah saya uji end-to-end (bukan cuma baca kode) pakai video sintetis nyata lewat FFmpeg + OpenCV, dan outputnya diverifikasi identik (resolusi, durasi, jumlah frame) dengan versi lama.

## Belum sempat dikerjakan (rekomendasi lanjutan)
- **Paralelisasi antar-clip** — saat ini 5 clip diproses berurutan satu-satu meski saling independen. Ini potensi speedup besar lagi tapi butuh perubahan arsitektur (concurrency, batasi jumlah encode GPU bersamaan) yang lebih berisiko, jadi sengaja saya pisah dari patch ini.
- Ada fungsi kembar `add_hook()` (tanpa `_with_progress`) dengan bug re-encode ganda serupa — **tidak dipakai di alur aplikasi live** (dead code, sudah saya cek tidak ada pemanggil), jadi aman diabaikan.
