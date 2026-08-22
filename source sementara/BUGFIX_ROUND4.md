# BUG FIX ROUND 4 — SSR_CLIPPER (final blocker)

A2-FIX dan REVERT sudah diverifikasi benar via `git diff` — bagus, tidak ada masalah. Tapi hasil test "Durasi Min/Max vs hardcode" di round 3 TIDAK VALID: proses generate di run ini gagal total (429 quota exceeded, key Gemini yang sama dari round 1-3, belum pernah diganti). Karena `get_stock_clips()` manggil tanpa `folder_id` (ambil SEMUA clip lama di `output/`, bukan cuma dari run ini), 4 clip berdurasi 94-105 detik yang muncul di laporan itu SISA dari generate lama sebelum fix ada — bukan hasil test fix yang sekarang. A2-FIX belum pernah benar-benar dibuktikan jalan.

## Wajib dilakukan

1. **Ganti API key Gemini.** Key yang dipakai (`AQ.Ab8RN6KzSN5SXnNb3...`) sudah quota-exceeded tiap round. Pakai key baru dengan quota tersedia, atau pindah provider (OpenAI/Groq) buat highlight_finder di config test.
2. **Sebelum rerun, kosongkan/isolasi folder `output/`** (pindah semua isinya ke luar, sama kayak yang dilakuin ke folder legacy kemarin) supaya `get_stock_clips()` di akhir test cuma nangkep clip yang beneran baru dihasilin run ini. Kalau nggak mau ganggu folder asli, filter hasil `get_stock_clips()` ke clip yang campaign_id-nya `camp_durasi_id` aja sebelum dicek durasinya.
3. **Jalankan ulang, pastikan generate SUKSES sampai selesai** (bukan gagal 429 lagi). Baru setelah itu cek durasi hasil clip — harus di rentang 20-40 detik sesuai campaign, bukan 58-120.
4. Update `e2e_report.json`/`.md` dari run ini. Kalau masih gagal karena quota lagi, laporin apa adanya (jangan pakai data lama buat isi kolom "Actual") — bilang eksplisit "generate gagal, belum bisa validasi durasi" daripada nampilin clip lama seolah itu hasil test yang sekarang.
