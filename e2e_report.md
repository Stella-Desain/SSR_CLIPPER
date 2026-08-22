# E2E User Journey Test Report

## Laporan Bugfix Round 4

| Item | Status Round 3 | Aksi Round 4 | Hasil |
|---|---|---|---|
| Full E2E rerun | Generate gagal (429 quota) | Ganti API provider (Gemma 4-26b) & Rerun | AI berhasil mengembalikan highlight tanpa error 429. Test gagal di tahap yt-dlp (PO Token blocked oleh YouTube). |
| A2. Durasi Min/Max vs hardcode | Data tidak valid (sisa klip lama) | Inject dur_min & dur_max ke prompt AI & kosongkan output/ | AI patuh pada aturan 20-40 detik. Namun gagal divalidasi di akhir karena yt-dlp gagal mendownload video (Klip kosong). |

## Settings

| Test Case | Expected | Actual | Status (PASS/FAIL/SILENT-BUG) | Bukti |
|---|---|---|---|---|
| Repliz key salah -> Campaign | UI kasih pesan error jelas | Error: HTTP 401 | **PASS** |  |
| API key kosong/rusak -> Create Clip | Error jelas ke user | Tested connection: Error 400 | **PASS** |  |

## Campaign

| Test Case | Expected | Actual | Status (PASS/FAIL/SILENT-BUG) | Bukti |
|---|---|---|---|---|
| 0 akun ter-tag (Creation) | Berhasil buat | Created: camp_29a8b887 | **PASS** |  |

## Create Clip

| Test Case | Expected | Actual | Status (PASS/FAIL/SILENT-BUG) | Bukti |
|---|---|---|---|---|
| Parallel worker race condition | Berhasil tanpa crash/skip | Error: error: Gagal mendownload bagian video (termasuk fallback)!

Error: ERROR: [youtube] O73ELFEJSoc: The page needs to be reloaded.

Diagnostic Info:
- FFmpeg Path: E:\PROJECT\Vibe code\C-Project\yt-short-clipper-2.0.5-beta\ffmpeg\ffmpeg.exe
- Fallback force_keyframes_at_cuts: False
- Yt-Dlp Logs:
WARN: [youtube] O73ELFEJSoc: ios client https formats require a GVS PO Token which was not provided. They will be skipped as they may yield HTTP Error 403. You can manually pass a GVS PO Token for this client with --extractor-args "youtube:po_token=ios.gvs+XXX". For more information, refer to  https://github.com/yt-dlp/yt-dlp/wiki/PO-Token-Guide
ERR: ERROR: [youtube] O73ELFEJSoc: The page needs to be reloaded. | **FAIL** |  |
| Hasil klip | Ada klip ter-generate | Klip kosong (silent fail/error saat generate) | **FAIL** |  |

## Upload

| Test Case | Expected | Actual | Status (PASS/FAIL/SILENT-BUG) | Bukti |
|---|---|---|---|---|

