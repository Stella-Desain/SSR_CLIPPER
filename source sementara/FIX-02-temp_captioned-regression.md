# INSTRUKSI FIX BUG #2 — SSR_CLIPPER
**Untuk: Gemini 3.1 Pro (junior executor)**
**Dari: Senior Auditor**
**Status: SIAP EKSEKUSI — jangan improvisasi di luar yang ditulis di sini.**

---

## 0. ATURAN KERAS (WAJIB DIPATUHI)

1. Hanya edit `clipper_core.py`, di method `process_clip`.
2. Hanya lakukan perubahan di TASK 1 di bawah. Jangan refactor bagian lain.
3. Exact string match — cari "KODE LAMA" persis, ganti persis dengan "KODE BARU".
4. Kalau "KODE LAMA" tidak ketemu persis (kemungkinan file sudah berubah lagi dari commit `cf71c69`), **STOP dan laporkan balik**, jangan menebak.
5. Setelah selesai, jalankan checklist verifikasi di bagian akhir dan laporkan hasilnya.

---

## 1. KONTEKS (baca dulu sebelum eksekusi)

Verifikasi commit `cf71c69` ("BUGFIX_NAMEERROR_WATERMARK") sudah dicek:

✅ **Bug lama (`audio_file` undefined di dekat akhir `process_clip`) SUDAH BENAR diperbaiki.** Kode mati yang menyebabkan `NameError` di setiap clip sudah dihapus dengan benar.

❌ **TAPI commit ini menambahkan blok baru untuk apply watermark yang punya bug baru sekelas:** blok watermark yang baru ditambahkan memakai variable `temp_captioned` secara **unconditional** (5 kali dipakai), padahal `temp_captioned` **hanya didefinisikan** di dalam cabang `if add_captions: ... if watermark_enabled:` (lihat baris ~3018-3019 di file saat ini).

**Akibatnya:** Kalau **Caption Maker di-OFF-kan** (`add_captions=False`) TAPI **Watermark atau Credit Watermark di-ON-kan**, kode akan crash `NameError: name 'temp_captioned' is not defined` — persis pola bug yang sama seperti sebelumnya (crash setelah video jadi, tapi sebelum cleanup & sebelum `data.json` metadata disimpan).

**Root cause:** blok watermark baru itu seharusnya beroperasi di atas `current_output` (variable yang SELALU konsisten melacak "file video terbaru saat ini" di sepanjang pipeline — sudah dipakai di Step 1/2/3/4 sebelumnya), bukan hardcode ke `temp_captioned` yang cuma ada di 1 skenario spesifik.

---

## 2. TASK 1 — Ganti `temp_captioned` → `current_output` di blok watermark

**File:** `clipper_core.py`, di dalam method `process_clip`, blok "Apply watermark / credit watermark if enabled" (persis setelah komentar `# Apply watermark / credit watermark if enabled`).

**KODE LAMA (cari persis, ini 1 blok utuh):**
```python
            if wm_on and credit_on:
                self.add_watermark_and_credit_with_progress(str(temp_captioned), str(final_file),
                    lambda p: clip_progress("Adding watermark...", current_step, p))
            elif wm_on:
                self.add_watermark_with_progress(str(temp_captioned), str(final_file),
                    lambda p: clip_progress("Adding watermark...", current_step, p))
            else:
                self.add_credit_watermark_with_progress(str(temp_captioned), str(final_file),
                    lambda p: clip_progress("Adding watermark...", current_step, p))

            if not final_file.exists():
                raise Exception(f"Failed to create final video with watermark: {final_file}")

            try:
                if temp_captioned.exists():
                    temp_captioned.unlink()
            except Exception as e:
                self.log(f"  Warning: Could not delete {temp_captioned.name}: {e}")
```

**KODE BARU:**
```python
            if wm_on and credit_on:
                self.add_watermark_and_credit_with_progress(str(current_output), str(final_file),
                    lambda p: clip_progress("Adding watermark...", current_step, p))
            elif wm_on:
                self.add_watermark_with_progress(str(current_output), str(final_file),
                    lambda p: clip_progress("Adding watermark...", current_step, p))
            else:
                self.add_credit_watermark_with_progress(str(current_output), str(final_file),
                    lambda p: clip_progress("Adding watermark...", current_step, p))

            if not final_file.exists():
                raise Exception(f"Failed to create final video with watermark: {final_file}")

            try:
                if current_output.exists() and current_output != final_file:
                    current_output.unlink()
            except Exception as e:
                self.log(f"  Warning: Could not delete {current_output.name}: {e}")
```

**Kenapa ini benar (tidak perlu diubah, cukup dipahami):** `current_output` sudah otomatis bernilai `temp_captioned` di skenario captions+watermark ON (di-assign di baris `current_output = temp_captioned` beberapa baris sebelumnya) — jadi behavior lama tetap identik di skenario itu. Yang berubah cuma: di skenario captions OFF + watermark ON, `current_output` akan berisi `hooked_file`/`portrait_file`/`landscape_file` (apapun yang valid saat itu) alih-alih crash.

---

## 3. CATATAN TAMBAHAN (FYI, TIDAK PERLU DIEKSEKUSI SEKARANG)

Ditemukan 1 bug lama yang **sudah ada sebelum commit `cf71c69`** (bukan regresi baru, jadi di luar scope task ini): kalau **Caption Maker OFF** dan **Watermark + Credit Watermark keduanya OFF**, `final_file` (`master.mp4`) **tidak pernah benar-benar dibuat** — file hasil (`current_output`, misal `hooked_file`) malah ikut terhapus di blok cleanup di bawahnya tanpa pernah di-rename/copy jadi `master.mp4`. Dulu ini "tertutupi" karena kode selalu crash duluan di bug `audio_file` sebelum sampai situ. Sekarang setelah bug itu fix, skenario ini jadi bisa benar-benar kejadian (silent data loss — clip selesai proses tapi `master.mp4` kosong/tidak ada). **Jangan fix ini sekarang** — tunggu instruksi terpisah kalau memang mau ditangani.

---

## 4. CHECKLIST VERIFIKASI SEBELUM LAPOR BALIK

1. [ ] `grep -n "temp_captioned" clipper_core.py` di dalam blok watermark (baris ~3040-3064) → harus **0 hasil** tersisa di blok ini (boleh masih ada di tempat lain, misal baris ~3019 tempat dia pertama didefinisikan — itu JANGAN diubah).
2. [ ] Baris `current_output = temp_captioned` di dalam `if add_captions:` (sekitar baris 3026) **TIDAK BOLEH dihapus/diubah** — itu bagian yang membuat fix ini bekerja.
3. [ ] `python -c "import ast; ast.parse(open('clipper_core.py', encoding='utf-8').read())"` → tidak boleh error.
4. [ ] Tempel diff before/after di laporan balik.

---

## 5. YANG TIDAK BOLEH DILAKUKAN

- Jangan fix catatan di bagian 3 (master.mp4 tidak pernah dibuat) — itu task terpisah.
- Jangan ubah logic `add_watermark_with_progress` / `add_credit_watermark_with_progress` / `add_watermark_and_credit_with_progress` itu sendiri.
- Jangan sentuh bug audio track (FIX-01) — itu file terpisah, kalau belum dikerjakan biarkan menunggu giliran.
