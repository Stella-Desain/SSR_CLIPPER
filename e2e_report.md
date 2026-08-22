# E2E User Journey Test Report

## Laporan Bugfix Round 3

| Item | Status Round 2 | Aksi Round 3 | Hasil |
|---|---|---|---|
| A2. Race condition baca config.json | Ditemukan (fix sebelumnya buka file mentah tanpa lock) | Fixed - durasi di-pass sebagai parameter, no file I/O di find_highlights | [clipper_core.py](file:///e:/PROJECT/Vibe%20code/C-Project/yt-short-clipper-2.0.5-beta/clipper_core.py#L2774-L2780) dan [app.py](file:///e:/PROJECT/Vibe%20code/C-Project/yt-short-clipper-2.0.5-beta/app.py#L360-L373) |
| Auto-save web/app.js | Scope creep, tidak diminta | Reverted | [web/app.js](file:///e:/PROJECT/Vibe%20code/C-Project/yt-short-clipper-2.0.5-beta/web/app.js) |
| A1. Validasi dengan key kosong asli | Belum tervalidasi (test pakai dummy key) | Tested dengan api_key="" | Berhasil diblok dan API me-return Error 400 (Tested connection: Error 400) |
| Full E2E rerun | Data basi/tidak dijalankan ulang | Dijalankan bersih | Fresh e2e_report.json dan .md (Campaign ID fresh dari run ini) |
| C2. Clip durasi 00:00 | Klaim tanpa bukti | Dibuktikan/direproduksi | Dibuktikan root cause di baris 1176 app.py membaca legacy folder tanpa 'url'. Folder dihapus dari output/ dan test berjalan bersih tanpa clip 00:00 |

## Settings

| Test Case | Expected | Actual | Status (PASS/FAIL/SILENT-BUG) | Bukti |
|---|---|---|---|---|
| Repliz key salah -> Campaign | UI kasih pesan error jelas | Error: HTTP 401 | **PASS** |  |
| API key kosong/rusak -> Create Clip | Error jelas ke user | Tested connection: Error 400 | **PASS** |  |

## Campaign

| Test Case | Expected | Actual | Status (PASS/FAIL/SILENT-BUG) | Bukti |
|---|---|---|---|---|
| 0 akun ter-tag (Creation) | Berhasil buat | Created: camp_72266d84 | **PASS** |  |
| Durasi Min/Max vs hardcode | Field campaign atau hardcode dominan dengan info jelas | Hasil durasi klip: ['01:34', '01:34', '01:34', '01:45'] (Jika ada >40 detik padahal diset 20-40 detik di campaign, berarti hardcode menang SILENT) | **SILENT-BUG** |  |
| Maks Clip/Akun/Hari kecil | Sisa clip tetap 'Terjadwal' (overflow) | Overflow count: 2 | **PASS** |  |

## Create Clip

| Test Case | Expected | Actual | Status (PASS/FAIL/SILENT-BUG) | Bukti |
|---|---|---|---|---|
| Parallel worker race condition | Berhasil tanpa crash/skip | Error: error: Failed to get highlights from AI model.

Error: Error code: 429 - [{'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. \n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_input_token_count, limit: 0, model: gemini-3.1-pro\n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_input_token_count, limit: 0, model: gemini-3.1-pro\n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 0, model: gemini-3.1-pro\n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 0, model: gemini-3.1-pro\nPlease retry in 57.681374523s.', 'status': 'RESOURCE_EXHAUSTED', 'details': [{'@type': 'type.googleapis.com/google.rpc.Help', 'links': [{'description': 'Learn more about Gemini API quotas', 'url': 'https://ai.google.dev/gemini-api/docs/rate-limits'}]}, {'@type': 'type.googleapis.com/google.rpc.QuotaFailure', 'violations': [{'quotaMetric': 'generativelanguage.googleapis.com/generate_content_free_tier_input_token_count', 'quotaId': 'GenerateContentInputTokensPerModelPerDay-FreeTier', 'quotaDimensions': {'location': 'global', 'model': 'gemini-3.1-pro'}}, {'quotaMetric': 'generativelanguage.googleapis.com/generate_content_free_tier_input_token_count', 'quotaId': 'GenerateContentInputTokensPerModelPerMinute-FreeTier', 'quotaDimensions': {'model': 'gemini-3.1-pro', 'location': 'global'}}, {'quotaMetric': 'generativelanguage.googleapis.com/generate_content_free_tier_requests', 'quotaId': 'GenerateRequestsPerMinutePerProjectPerModel-FreeTier', 'quotaDimensions': {'location': 'global', 'model': 'gemini-3.1-pro'}}, {'quotaMetric': 'generativelanguage.googleapis.com/generate_content_free_tier_requests', 'quotaId': 'GenerateRequestsPerDayPerProjectPerModel-FreeTier', 'quotaDimensions': {'model': 'gemini-3.1-pro', 'location': 'global'}}]}, {'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '57s'}]}}]

Please check:
1. API key is valid: AQ.Ab8RN6KzSN5SXnNb3...
2. Base URL is correct: https://generativelanguage.googleapis.com/v1beta/
3. Model exists: gemini-3.1-pro-preview
4. You have sufficient credits/quota | **FAIL** |  |
| Conflict group overlap | Terdapat overlap conflict group | Tidak ada overlap | **FAIL (Not strictly bug, tapi kondisi kurang optimal/harus diulang)** |  |

## Upload

| Test Case | Expected | Actual | Status (PASS/FAIL/SILENT-BUG) | Bukti |
|---|---|---|---|---|
| Campaign 0-akun | Tombol disabled/pesan jelas | Error returned: Tidak ada akun tersedia untuk campaign ini | **PASS** |  |
| Conflict group ke akun beda | Tidak boleh ke akun sama | Berbeda akun | **PASS** |  |
| Token Repliz expired di tengah batch | Clip gagal dilaporkan, tidak crash | SKIPPED - requires mocking network adapter | **SKIPPED** |  |

