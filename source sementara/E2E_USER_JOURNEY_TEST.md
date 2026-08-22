# END-TO-END USER JOURNEY TEST — SSR_CLIPPER

## Role
Kamu berperan sebagai USER ASLI yang baru pertama kali pakai aplikasi ini — bukan developer yang ngecek kode dari luar. Jalanin app dari nol: Settings → Campaign → Create Clip → Upload, sampai BERHASIL generate dan upload minimal 1 clip. Sambil jalan, kamu wajib nyoba titik-titik rawan (⚠) di bawah secara eksplisit, bukan cuma lewat pas jalur normal kebetulan mulus.

## Aturan Wajib
- JANGAN fix bug apapun selama testing ini. Laporkan dulu, tunggu instruksi lanjutan.
- Tiap test WAJIB ada bukti (screenshot state UI, log console, isi file output) — bukan klaim "sudah OK".
- Kalau nemu silent failure (app diem-diem gagal tanpa pesan/error ke user) → itu prioritas TINGGI walau app-nya nggak crash. Silent failure lebih bahaya dari crash karena user nggak sadar ada yang salah.
- Kalau ada langkah yang nggak bisa dites (resource nggak tersedia), tulis eksplisit "SKIPPED — alasan: ..." — jangan pura-pura sudah test.

---

## STEP 0 — Sebelum Mulai: Kumpulin Config dari User

JANGAN generate/asumsi/mock data apapun. Sebelum testing, tanya ke user (operator yang kasih instruksi ini ke kamu) hal-hal berikut satu per satu:

1. Link YouTube asli buat testing (disaranin video pendek, di bawah 10 menit, biar cepat dan hemat cost)
2. AI provider + API key buat Highlight Finder (OpenAI GPT-4 / Gemini / Groq / provider lain yang didukung)
3. Provider buat Caption/Whisper (kalau beda dari provider di atas)
4. Provider TTS buat Hook voice (kalau mau ikut test fitur Hook Generation)
5. Repliz Access/Secret Key — WAJIB kalau mau test tahap Upload, karena semua distribusi akun fan-out dari sini
6. Minimal 1 akun YouTube yang sudah di-OAuth dan terhubung ke Repliz sebagai tujuan upload
7. Info GPU environment testing (NVIDIA/AMD/Intel/Apple Silicon/tidak ada) — buat tau encoder yang bakal kepake
8. Konfirmasi eksplisit: boleh generate cost API real? (README nyebut estimasi $0.10-0.25/video untuk 5 clip)

Kalau salah satu nggak tersedia, bilang eksplisit tahap mana yang bakal di-skip dan kenapa. Jangan lanjut pakai asumsi.

---

## TAHAP 1 — SETTINGS

Checklist dasar:
- [ ] Isi API Keys (OpenAI/Gemini) buat Highlight Finder, Caption Maker, Hook Maker, YT Title Maker, Brief Extractor — cek tiap model picker bisa milih model yang bener
- [ ] GPU Detect & Face Tracking — toggle OpenCV vs MediaPipe, cek encoder yang kedetect sesuai environment
- [ ] Output Folder — set path lokal
- [ ] YouTube OAuth — connect akun (harus terpisah secara jelas dari akun distribusi Repliz)
- [ ] Repliz Access/Secret Key — connect, verify daftar akun berhasil ke-fetch

⚠ TEST WAJIB:
- **Repliz key salah → Campaign**: Connect Repliz dengan key valid dulu (biar tau baseline behavior-nya). Lalu ganti key jadi salah/random di Settings. Pindah ke Campaign, coba "Hubungkan Akun". Expected: UI kasih pesan error jelas. Bug kalau: daftar akun diam-diam jadi kosong tanpa pesan apapun, atau app crash.
- **API key kosong/rusak → Create Clip**: Kosongkan atau rusak API key yang dipakai Highlight Finder. Lanjut generate clip sampai ke step Highlight Detection. Expected: error jelas ke user. Bug kalau: silent fail (hasil highlight kosong tanpa pesan) atau crash generic tanpa konteks apa penyebabnya.

---

## TAHAP 2 — CAMPAIGN

Checklist dasar:
- [ ] Bikin Brief & Rules baru — name, goal, persona, CTA, angles, hashtags, do/don't
- [ ] Set Durasi Min/Max (detik)
- [ ] Set Maks Clip/Akun/Hari
- [ ] Hubungkan Akun — pilih dari daftar Repliz
- [ ] Toggle status aktif/nonaktif — campaign nonaktif nggak boleh muncul di dropdown Create Clip

⚠ TEST WAJIB:
- **KONFLIK POTENSIAL — Durasi Min/Max vs hardcode di kode**: `find_highlights()` di `clipper_core.py` punya validasi hardcode durasi 58-120 detik, terpisah dari field "Durasi Min/Max" di campaign. Set durasi campaign DI LUAR range itu (misal 20-40 detik). Generate clip pakai campaign ini. Expected: salah satu dari dua — field campaign yang menang (highlight difilter sesuai 20-40 detik) ATAU app kasih tau field ini nggak berlaku. Bug kalau: field durasi campaign diam-diam diabaikan, hasil clip tetap 58-120 detik tanpa user tau kenapa settingnya nggak ngaruh.
- **Maks Clip/Akun/Hari kecil**: Set limit sangat kecil (1/hari) padahal ada banyak clip siap upload. Expected: sisa clip tetap berstatus "Terjadwal", nunggu hari berikutnya. Bug kalau: sisa clip berstatus gagal atau hilang dari antrian.
- **0 akun ter-tag**: Bikin campaign tanpa hubungkan akun sama sekali. Nanti di Tahap 4, coba tombol "Distribusikan". Expected: tombol disabled atau pesan jelas "belum ada akun terhubung". Bug kalau: proses jalan ke "nowhere" — nggak ada error, nggak ada hasil, status ambigu.

---

## TAHAP 3 — CREATE CLIP

Checklist dasar:
- [ ] Masukin link YouTube asli, pilih campaign yang sudah dibuat di Tahap 2
- [ ] Subtitle-first → Whisper fallback
- [ ] Highlight Detection — test mode Fixed count dan mode AI-decides (min_score=6)
- [ ] Conflict Group + Download Heuristic
- [ ] Parallel Worker Pool (4-7 threads)
- [ ] Per-clip Metadata — cek `data.json` valid (campaign_id, virality_score, conflict_group_id)

⚠ TEST WAJIB:
- **Subtitle-first fallback**: Test pakai video yang PUNYA auto-subtitle YouTube, dan pisah, video yang TIDAK PUNYA subtitle sama sekali. Expected: yang kedua otomatis fallback ke Whisper transcribe tanpa perlu intervensi user. Bug kalau: app stuck atau error pas video nggak ada subtitle.
- **Conflict group overlap**: Pastikan generate menghasilkan minimal 2 highlight yang overlap timestamp-nya (masuk `conflict_group_id` sama). Simpan info ini buat divalidasi di Tahap 4 — jangan sampai dua clip yang overlap keupload ke akun yang SAMA.
- **Parallel worker race condition — TEST PALING KRITIS**: Generate dengan >15 highlight sekaligus, pakai video TANPA subtitle bawaan (biar Whisper fallback ikut kepake) + Portrait mode ON + MediaPipe ON (bukan OpenCV — MediaPipe 2-3x lebih lambat, window race condition lebih lebar). Ini kombinasi paling berat: banyak worker paralel + GPU-heavy face tracking + threading progress lock jalan bareng. Perhatiin: ada clip yang ke-skip diam-diam? Progress bar nyangkut? Output file 0 byte? `data.json` ke-overwrite/collision antar worker?

---

## TAHAP 4 — UPLOAD (Stock Clip)

Checklist dasar:
- [ ] Filter & Pilih Clip berdasar status (belum diupload/terjadwal/uploading/sukses/gagal)
- [ ] Distribusikan & Upload — `preview_distribution(clip_ids, campaign_id, max_per_akun_per_hari)`
- [ ] Per-akun Upload + Retry
- [ ] Status Sync real-time di UI

⚠ TEST WAJIB:
- **Token Repliz expired di tengah batch**: Upload batch berisi minimal 3-5 clip sekaligus. Di TENGAH proses, invalidate token Repliz (revoke dari sisi Repliz kalau bisa, atau ganti key salah di Settings kalau app re-read config secara live). Expected: clip yang sudah kepush tetap aman/sukses, sisanya dapat status "Gagal" dengan pesan jelas. Bug kalau: seluruh batch diam-diam berhenti tanpa status update yang jelas ke user.
- **Validasi ulang dependency dari tahap sebelumnya**:
  - Campaign 0-akun dari Tahap 2 → tombol Distribusikan harus disabled/kasih pesan, bukan proses ke nowhere.
  - Conflict group dari Tahap 3 → dua clip overlap boleh ke akun beda, TAPI TIDAK BOLEH keduanya ke akun sama (duplikat konten di 1 akun).

---

## KRITERIA SUKSES
Testing dianggap lulus tahap dasar kalau:
1. Berhasil generate minimal 1 clip lengkap dari link asli sampai keluar `master.mp4` + `data.json` valid, DAN berhasil upload ke minimal 1 akun.
2. Semua ⚠ TEST WAJIB di atas sudah dijalanin dan hasilnya dicatat — yang FAIL wajib dilaporin, bukan cuma yang PASS.
3. Setiap silent failure di-flag sebagai bug prioritas tinggi.

## FORMAT LAPORAN (WAJIB)

Per tahap, isi tabel ini:

| Test Case | Expected | Actual | Status (PASS/FAIL/SILENT-BUG) | Bukti |
|---|---|---|---|---|

Di akhir laporan, kasih ringkasan urutan prioritas fix: bug yang bikin app crash paling atas, lalu silent failure, baru bug kosmetik/UX minor. Jangan kasih solusi/fix di laporan ini — cukup temuan dan bukti.
