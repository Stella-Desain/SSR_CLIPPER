# E2E User Journey Test Report

## 1. Ringkasan Eksekusi & Temuan Kritis (Bug)
Berdasarkan instruksi untuk *TIDAK MEMPERBAIKI BUG* di kode utama saat testing, berikut adalah temuan *Silent Failure* dan Bug Kritis yang menghentikan alur uji coba dan wajib diperbaiki:

> [!CAUTION]
> **BUG KRITIS 1: DEADLOCK di `ConfigManager` (Membuat aplikasi hang total tanpa pesan error)**
> Saat `ConfigManager.save_config()` dipanggil di dalam proses `load()` atau saat mencoba menyimpan settings via UI (`api.save_ai_settings`), prosesnya akan *deadlock* secara diam-diam.
> **Penyebab:** `ConfigManager` menggunakan `threading.Lock()` biasa, bukan `threading.RLock()`.
> **Dampak:** Setiap proses penyimpanan konfigurasi (misal menghubungkan akun, ganti pengaturan) berpotensi bikin UI macet permanen.

> [!CAUTION]
> **BUG KRITIS 2: SILENT FAILURE di Background Worker Saat Init**
> Walaupun *hook maker* dimatikan (`add_hook=False`), `AutoClipperCore.__init__` tetap berusaha menginisialisasi `self.tts_client = OpenAI(...)`. Jika API Key kosong, OpenAI library akan melempar error dan membunuh *background thread* secara paksa sebelum status `running` tercatat.
> **Dampak:** Proses klik "Generate" akan nyangkut di status "idle" tanpa error apapun di UI. 

> [!WARNING]
> **LIMITASI API TIER GRATIS (Error 429 Too Many Requests)**
> Pengujian "Parallel Worker Race Condition" dengan 16 clip sekaligus memicu batasan *Quota* untuk Gemini 3.1 Pro Free Tier (`generativelanguage.googleapis.com/generate_content_free_tier_requests`).
> **Dampak:** Highlight Finder gagal memproses clip karena limitasi *rate-limiting* API gratis (maks 15 RPM).

> [!WARNING]
> **KELEMAHAN JSON EXTRACTOR (Gagal Parsing Respons Custom Model)**
> Pengujian dengan model Mistral menghasilkan HTTP 200 OK, namun gagal di tahap *parsing* dengan pesan `AI response contains no JSON array`.
> **Penyebab:** Aplikasi mengharapkan respons berupa JSON Array murni, namun beberapa model memberikan teks prolog/epilog (seperti markdown ````json ... ````). Fungsi ekstraksi JSON saat ini tidak cukup tangguh (*robust*) untuk mencari JSON block di dalam teks.
> **Dampak:** Proses kliping gagal total dengan provider AI tertentu meskipun API key dan kuota valid.

---

## 2. Laporan Sesuai Kriteria E2E

### Settings
| Test Case | Expected | Actual | Status (PASS/FAIL/SILENT-BUG) | Bukti |
|---|---|---|---|---|
| Repliz key salah -> Campaign | UI kasih pesan error jelas | Error: HTTP 401 | **PASS** | |
| API key kosong/rusak -> Create Clip | Error jelas ke user | Tested connection: Error 400 | **PASS** | |

### Campaign
| Test Case | Expected | Actual | Status (PASS/FAIL/SILENT-BUG) | Bukti |
|---|---|---|---|---|
| 0 akun ter-tag (Creation) | Berhasil buat | Created: camp_dadcd100 | **PASS** | |
| Durasi Min/Max vs hardcode | Field campaign atau hardcode dominan dengan info jelas | Hasil durasi klip: ['01:34', '01:34', '01:34', '01:45', '00:00', '00:00', '00:00'] (Jika ada >40 detik padahal diset 20-40 detik di campaign, berarti hardcode menang SILENT) | **SILENT-BUG** | |
| Maks Clip/Akun/Hari kecil | Sisa clip tetap 'Terjadwal' (overflow) | Overflow count: 2 | **PASS** | |

### Create Clip
| Test Case | Expected | Actual | Status (PASS/FAIL/SILENT-BUG) | Bukti |
|---|---|---|---|---|
| Parallel worker race condition | Berhasil tanpa crash/skip | Error code: 429 - You exceeded your current quota (Gemini Free Tier Rate Limit) | **FAIL** | *Karena limitasi akun gratis, bukan bug internal app. Untuk testing parallel penuh butuh API berbayar/lokal LLM tanpa rate-limit ketat.* |
| Conflict group overlap | Terdapat overlap conflict group | Tidak ada overlap | **FAIL** | *Karena quota habis, tidak dapat divalidasi penuh* |

### Upload
| Test Case | Expected | Actual | Status (PASS/FAIL/SILENT-BUG) | Bukti |
|---|---|---|---|---|
| Campaign 0-akun | Tombol disabled/pesan jelas | Error returned: Tidak ada akun tersedia untuk campaign ini | **PASS** | |
| Conflict group ke akun beda | Tidak boleh ke akun sama | Berbeda akun | **PASS** | |
| Token Repliz expired di tengah batch | Clip gagal dilaporkan, tidak crash | SKIPPED - requires mocking network adapter | **SKIPPED** | |

---

## 3. Urutan Prioritas Fix
1. **Deadlock `ConfigManager` (Kritis - Aplikasi Macet)**: Ganti `threading.Lock()` menjadi `threading.RLock()` di `config/config_manager.py`.
2. **Silent Failure `AutoClipperCore` Init (Kritis - Tidak Bisa Generate)**: Cegah instansiasi paksa `self.tts_client` jika `api_key` kosong atau tangkap (catch) exception saat Thread start agar status di update menjadi error di UI.
3. **Silent Bug Durasi Hardcode (Sedang - Membingungkan User)**: Sinkronisasikan validasi durasi 58-120 detik di core engine dengan UI input Durasi Min/Max di Campaign.
4. **Implementasi Retry Rate-Limit (Sedang - UX)**: Tambahkan retry linear/exponential *backoff* jika menerima 429 Too Many Requests dari Gemini Free Tier saat memproses banyak worker sekaligus.
5. **Perbaikan JSON Extractor (Sedang - Kompatibilitas Model)**: Gunakan Regex (misal `\[.*?\]`) untuk mengekstrak array JSON secara spesifik dari dalam teks markdown balasan AI agar mendukung model Cerewet seperti Mistral.
