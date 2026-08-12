# REVIEW KRITIS #6 (FINAL) — Task 4-6 + Laporan Akhir

STATUS: A1-A3 DITERIMA PENUH. Task 4, 5, 6 diterima secara struktur — bagus, terutama investigasi mandiri di Task 4 (face tracking ternyata di `output_settings.py`) dan Task 6 (OAuth file-based, bukan manual key input, dan sengaja tidak mengarang form yang tidak ada). Tinggal 3 hal di bawah sebelum project migrasi ini bisa dianggap CLOSED.

## J1. `connect_youtube()` — potensi blocking UI thread
Laporan bilang: "Blocking call (pywebview menjalankannya di background thread)". Ini agak ambigu — dua kemungkinan:
- (a) `connect_youtube()` di Python berjalan di thread terpisah (non-blocking terhadap main thread pywebview), sehingga UI tetap responsif selagi user menyelesaikan OAuth di browser, ATAU
- (b) Call ini benar-benar blocking di thread utama, yang berarti seluruh app freeze sampai OAuth selesai/gagal/timeout di browser.
Kalau (b), ini masalah UX serius (app kelihatan hang, terutama kalau user lama di halaman consent Google atau menutup browser tanpa selesai).

Tunjukkan kode lengkap `connect_youtube()` di `app.py` — khususnya apakah dipanggil langsung atau dibungkus `threading.Thread`/`asyncio`/executor. Kalau ternyata blocking di main thread, perbaiki supaya jalan di background thread dan frontend dikasih loading state + kemungkinan timeout/cancel.

## J2. Wiring listener beberapa tombol baru — belum ditunjukkan kodenya
Baru dijelaskan prosa, belum ada snippet. Tunjukkan kode `addEventListener` untuk:
- `gaDetectBtn` (Detect GPU, Task 4)
- Browse & Open button di panel Output Folder (Task 5)
- `ytConnectBtn` & `ytDisconnectBtn` (Task 6)
Pastikan semuanya benar-benar terpasang ke handler yang memanggil endpoint API yang sesuai (bukan cuma didefinisikan tapi lupa di-attach — ini persis pola bug yang pernah ketemu sebelumnya di `#reload-model-btn`).

## K. Laporan akhir (poin C4) belum lengkap — cuma cover Task 1-6
Tabel 18 endpoint yang ditampilkan HANYA dari Watermark → YouTube (Task-task Settings terbaru). Instruksi awal (`11-MASTER-review-dan-lanjutan.md` poin C4) minta list SEMUA endpoint WebAPI baru **sepanjang seluruh project migrasi**, termasuk yang dari ronde-ronde sebelumnya (Dashboard, Create Clip, Stock Clip, Global Shell). Contoh yang harus juga masuk di tabel final:
- `upload_clip()` (Stock Clip, support TikTok/YouTube/Repliz)
- `delete_job()` (Stock Clip)
- `get_app_config()` (Global Shell — username dari config)
- `test_repliz_connection()` (revisi jadi TODO blocker)
- Endpoint/parameter baru di `start_processing()` (Create Clip: `portrait`, `highlight_finder`, `yt_title_maker`, `num_clips`, `subtitle_lang`)
- Perubahan `check_dependencies()` (deno/whisper jadi cek asli)
- Stub `restock_clip` (Dashboard, kalau ada endpoint-nya, atau catat kalau masih cuma alert TODO)
- `reload_whisper_model` / reload model endpoint (Settings)

Buat SATU tabel final gabungan (bukan cuma Task 1-6), urut dari awal project sampai sekarang, format sama seperti tabel yang sudah dibuat (Fungsi | Parameter | Kegunaan). Ini jadi dokumen serah-terima akhir project.

## Setelah J1, J2, K dijawab
Project migrasi ini bisa dianggap **CLOSED**. Tidak perlu ada task baru lagi setelah ini kecuali kalau audit final menemukan sesuatu yang baru.
