# BUG FIX ROUND 3 — SSR_CLIPPER

Lanjutan dari commit `2c5d49e`. A1 sudah bagus dan diverifikasi benar. A2 logic-nya benar tapi implementasinya nyimpen risiko baru. Ada juga perubahan di luar scope yang harus di-revert atau dikonfirmasi dulu. Dan yang paling penting: laporan test yang di-submit kemarin itu BASI (data sama persis kayak round 1) — round ini WAJIB ada bukti eksekusi asli, bukan tabel yang ditulis tangan.

## Aturan Wajib
- Tiap klaim "sudah fix" WAJIB disertai `git diff` DAN bukti hasil test yang bener-bener dijalanin, bukan narasi.
- `e2e_report.json` dan `e2e_report.md` HARUS di-generate ulang dari eksekusi `e2e_runner.py` yang sebenarnya di round ini. Kalau isi kedua file itu identik sama upload sebelumnya, itu tanda belum ada rerun — jangan submit begitu.
- JANGAN nambahin perubahan apapun di luar yang diminta eksplisit di sini atau di round sebelumnya.

---

## TRACK A2-FIX — Hilangkan race condition di pembacaan durasi campaign

**Masalah dengan implementasi sekarang:** `find_highlights()` di `clipper_core.py` buka `config.json` langsung pakai `open()` + `json.load()` mentah, TANPA lewat `_file_lock` yang ada di `ConfigManager`. Ini bypass proteksi yang udah ada. Sekarang ditambah lagi ada auto-save di `web/app.js` yang trigger `save_config()` tiap user ngetik di form settings — kemungkinan file lagi ditulis di tengah proses baca ini jadi nggak nol. Kalau baca kena tengah-tengah tulis, `json.JSONDecodeError` ketangkep di `except`, terus diam-diam fallback ke default 58-120 lagi — pattern silent-override yang sama persis kayak bug asal, cuma pindah tempat.

**Fix yang benar:** jangan baca file sama sekali dari dalam `find_highlights()`. Data campaign udah ada di memory lebih awal — `app.py::_run()` line ~285 udah manggil `cfg = self._get_cfg()` sebelum `AutoClipperCore` dibikin. Lakuin ini:

1. Di `app.py::_run()`, setelah `cfg = self._get_cfg()`, lookup campaign dari `cfg.get("campaigns", [])` pakai `campaign_id` yang sudah ada sebagai parameter fungsi ini. Ambil `durasi_min`/`durasi_max` dari `brief`-nya kalau campaign ketemu.
2. Pass `durasi_min`/`durasi_max` itu sebagai parameter baru ke `core.process(...)`, lalu diteruskan ke `find_highlights(...)` sebagai `dur_min`/`dur_max` (bukan `campaign_id` yang dipakai buat baca file lagi).
3. Di `find_highlights()`, HAPUS blok `open(get_app_dir() / "config.json")` yang sekarang ada. Ganti jadi terima `dur_min: int = 58, dur_max: int = 120` langsung sebagai parameter, pakai default itu kalau caller nggak kasih nilai.

Hasil akhirnya: nol file I/O tambahan, nol race condition, logic durasinya tetap sama persis kayak sebelumnya (campaign menang kalau ada, default 58-120 kalau nggak).

**Bukti yang wajib disertain:** `git diff` buat `app.py` dan `clipper_core.py`, plus konfirmasi `find_highlights()` udah nggak ada baris `open(...)`/`json.load(...)` di dalamnya lagi.

---

## TRACK REVERT — Auto-save di web/app.js

Perubahan di `web/app.js` (auto-trigger klik save button 1 detik setelah user ngetik di form AI settings) itu nggak pernah diminta di Track A/B/C manapun sebelumnya. Ini juga yang bikin race condition di atas jadi lebih mungkin kejadian (makin sering `save_config()` ke-trigger tanpa user sadar).

**Yang harus dilakuin:** revert perubahan ini sepenuhnya, balikin `web/app.js` ke behavior sebelumnya (save cuma pas user klik tombol Save secara eksplisit). Kalau menurutmu auto-save ini beneran fitur yang berguna, jangan implementasi sendiri — tulis alasannya di laporan dan biarkan saya yang putusin, jangan diam-diam ditambahin ke commit fix bug.

---

## TRACK VERIFY — Rerun asli, wajib

Ini yang paling penting. Round sebelumnya kode-nya diubah tapi laporan test yang disubmit itu adalah file lama yang sama persis (campaign ID beda, isi identik ke laporan round 1) — artinya nggak ada rerun beneran yang terjadi.

1. **Jalanin `e2e_runner.py` end-to-end, satu kali, sampai selesai atau gagal.** Pastikan `GEMINI_API_KEY` (atau provider lain yang reliable, BUKAN proxy tunnel custom) ke-set beneran, bukan cuma dicek exist-nya doang.
2. **Test A1 dengan skenario yang sebenarnya bermasalah:** ganti `hook_maker.api_key` di test config jadi STRING KOSONG (`""`), BUKAN `"dummy_key_to_bypass_init_crash"`. Ini skenario asli yang katanya udah difix — kalau nggak dites dengan kondisi ini, fix-nya belum tervalidasi sama sekali. Jalankan `start_processing` dengan `add_hook=False` dan `hook_maker.api_key=""`, konfirmasi proses jalan sampai selesai (nggak crash diam-diam kayak sebelum fix).
3. **`e2e_report.json` dan `.md` HARUS keluar dari `generate_markdown_report()` yang baca file json dari run yang barusan ini juga** — bukan ditulis manual, bukan ditempel dari run lama. Campaign ID di kedua file harus identik karena dari run yang sama.
4. **C2 (clip durasi 00:00):** kalau klaim "folder legacy lama" itu benar, buktikan — kasih path folder yang dimaksud dan isi `data.json`-nya yang nggak punya field `"url"`, atau hapus folder itu dari environment test dan buktikan clip 00:00 nggak muncul lagi di run yang bersih.

---

## FORMAT LAPORAN

Update tabel Round di bagian atas `e2e_report.md`:

| Item | Status Round 2 | Aksi Round 3 | Hasil |
|---|---|---|---|
| A2. Race condition baca config.json | Ditemukan (fix sebelumnya buka file mentah tanpa lock) | Fixed — durasi di-pass sebagai parameter, no file I/O di find_highlights | (diff) |
| Auto-save web/app.js | Scope creep, tidak diminta | Reverted | (diff) |
| A1. Validasi dengan key kosong asli | Belum tervalidasi (test pakai dummy key) | Tested dengan api_key="" | (hasil run) |
| Full E2E rerun | Data basi/tidak dijalankan ulang | Dijalankan bersih | (json+md fresh, campaign ID konsisten) |
| C2. Clip durasi 00:00 | Klaim tanpa bukti | Dibuktikan/direproduksi | (path folder + isi data.json, atau hasil run bersih tanpa clip 00:00) |

Semua kolom "Hasil" harus punya bukti konkret (path file, isi log, atau diff) — bukan ringkasan kalimat tanpa data pendukung.
