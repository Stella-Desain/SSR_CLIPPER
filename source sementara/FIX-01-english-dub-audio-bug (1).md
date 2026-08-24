# INSTRUKSI FIX BUG — SSR_CLIPPER
**Untuk: Gemini 3.1 Pro (junior executor)**
**Dari: Senior Auditor**
**Status: SIAP EKSEKUSI — jangan improvisasi di luar yang ditulis di sini.**

---

## 0. ATURAN KERAS (WAJIB DIPATUHI)

1. Hanya edit `clipper_core.py`. Jangan sentuh file lain.
2. Hanya lakukan perubahan yang diinstruksikan di TASK 1 dan TASK 2 di bawah. Jangan refactor, jangan "rapikan" kode lain, jangan hapus komentar yang tidak disebutkan.
3. Gunakan **exact string match** (cari teks lama persis seperti yang ditulis di "KODE LAMA", ganti persis dengan "KODE BARU"). Jangan menulis ulang dari ingatan/interpretasi sendiri.
4. Jika teks "KODE LAMA" tidak ditemukan persis (misalnya sudah berubah), **STOP dan laporkan** — jangan menebak atau memaksakan perubahan lain.
5. Setelah selesai, jalankan checklist verifikasi di bagian akhir file ini dan laporkan hasilnya.

---

## 1. RINGKASAN BUG (konteks, tidak perlu dieksekusi, cukup dibaca)

**Gejala:** Video sumber berbahasa Indonesia, tapi hasil clip punya suara robot berbahasa Inggris DAN subtitle bahasa Inggris, sementara suara asli orang di video hilang total.

**Root cause:** YouTube sekarang punya fitur multi-audio-track ("Aloud"/auto-dub) — satu video bisa punya beberapa track audio: track asli (Indonesia) + track dub AI (Inggris, sering terdengar robotic). Fungsi download di `clipper_core.py` memakai format selector yt-dlp:

```
bestvideo[height>=720][height<=2160]+bestaudio/best[height>=720][height<=2160]/bestvideo+bestaudio/best
```

`bestaudio` di sini **tidak punya filter bahasa sama sekali** — yt-dlp akan asal pilih track "terbaik" secara bitrate/kualitas, yang bisa jadi itu track dub bahasa Inggris, bukan track asli. Akibatnya:
- Video yang di-download = video + **audio dub Inggris (robot)**, audio asli Indonesia tidak pernah ikut ter-download.
- Local Whisper (Caption Maker) men-transkrip audio yang benar-benar didengarnya (audio dub Inggris) → caption jadi bahasa Inggris. Ini BUKAN bug di Whisper atau di setting "Subtitle Language" — settingnya sudah benar, cuma audio sumbernya yang salah dari awal.

Baris format selector ini **diduplikasi identik 4x** di 4 fungsi download berbeda (module-based & subprocess-based, untuk full video & untuk section/segment). Semua 4 harus diperbaiki, tidak cukup 1.

Fix-nya: prioritaskan track audio yang bahasanya cocok dengan `self.subtitle_language` (setting "Subtitle Language" yang sudah ada di UI, misal "id"), baru fallback ke `bestaudio` polos kalau video cuma punya 1 track (kasus mayoritas, tidak terpengaruh).

---

## 2. TASK 1 — Fix audio track bahasa salah (PRIORITAS UTAMA)

### 2a. Tambah method baru

**File:** `clipper_core.py`
**Lokasi:** Di dalam class `AutoClipperCore`, tepat SEBELUM method `_download_video_module`.

Cari blok ini (akhir dari method `download_video`):

```python
    def download_video(self, url: str) -> tuple:
        """Download video and subtitle with progress using yt-dlp module or executable"""
        self.log("[1/4] Downloading video & subtitle...")
        
        # Check if using yt-dlp module
        use_module = YTDLP_MODULE_AVAILABLE and self.ytdlp_path == "yt_dlp_module"
        
        if use_module:
            return self._download_video_module(url)
        else:
            return self._download_video_subprocess(url)
    
    def _download_video_module(self, url: str) -> tuple:
```

Sisipkan method baru **di antara** `return self._download_video_subprocess(url)` dan `def _download_video_module`, sehingga jadi:

```python
    def download_video(self, url: str) -> tuple:
        """Download video and subtitle with progress using yt-dlp module or executable"""
        self.log("[1/4] Downloading video & subtitle...")
        
        # Check if using yt-dlp module
        use_module = YTDLP_MODULE_AVAILABLE and self.ytdlp_path == "yt_dlp_module"
        
        if use_module:
            return self._download_video_module(url)
        else:
            return self._download_video_subprocess(url)
    
    def _get_format_selector(self) -> str:
        """Build the yt-dlp format selector used by every video/section download.

        YouTube can serve MULTIPLE audio tracks per video (the official
        "Aloud" auto-dub feature) — e.g. original Indonesian + an
        AI-generated English dub. Plain "bestaudio" has no language
        awareness and can silently grab the dubbed (robotic) track instead
        of the original, which is why clips have come out with English
        dubbed audio + English captions even with Subtitle Language set to
        Indonesian. Fix: prefer the audio track matching self.subtitle_language
        first, then fall back to plain bestaudio (single-track videos are
        unaffected).
        """
        base_video = "bestvideo[height>=720][height<=2160]"
        lang = self.subtitle_language
        if lang and lang != "none":
            return (
                f"{base_video}+bestaudio[language^={lang}]/"
                f"{base_video}+bestaudio/"
                f"best[height>=720][height<=2160]/"
                f"bestvideo+bestaudio[language^={lang}]/"
                f"bestvideo+bestaudio/best"
            )
        return (
            f"{base_video}+bestaudio/"
            f"best[height>=720][height<=2160]/"
            f"bestvideo+bestaudio/best"
        )
    
    def _download_video_module(self, url: str) -> tuple:
```

### 2b. Ganti SEMUA (4) pemanggilan format_selector lama

Cari baris berikut — **muncul persis 4 kali** di file ini, di 4 fungsi berbeda (`_download_video_module`, `_download_video_subprocess`, `_download_section_module`, `_download_section_subprocess`):

**KODE LAMA (cari, ganti ke-4 kemunculannya):**
```python
        format_selector = "bestvideo[height>=720][height<=2160]+bestaudio/best[height>=720][height<=2160]/bestvideo+bestaudio/best"
```

**KODE BARU (pakai baris ini di ke-4 lokasi tsb):**
```python
        format_selector = self._get_format_selector()
```

Jangan ubah baris lain di sekitarnya (misal `ydl_opts['format_sort']` atau `--format-sort` di versi subprocess/CLI — itu tetap, tidak diubah).

---

## 3. TASK 2 — Hapus dead code yang bikin crash (PRIORITAS KEDUA)

**Masalah:** Di method `process_clip`, ada sisa kode lama yang mereferensikan variable `audio_file` yang **tidak pernah didefinisikan** di scope method ini (`NameError` — 100% selalu crash, di SETIAP clip, terlepas dari setting apapun). Crash ini terjadi SETELAH `master.mp4` sudah jadi tapi SEBELUM cleanup temp file & SEBELUM `data.json` metadata clip disimpan. Efeknya: setiap clip yang diproses kehilangan `data.json`-nya dan menyisakan file temp yang harusnya dihapus, walau video hasil akhirnya sebenarnya sudah terbentuk.

**File:** `clipper_core.py`, di dalam method `process_clip`.

**KODE LAMA (cari persis, hanya ada 1 kemunculan — identifikasi lewat baris `clip_progress("Done", total_steps, 0)` yang unik):**
```python
        # Get total audio duration
        probe_cmd = [self.ffmpeg_path, "-i", audio_file]
        probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, creationflags=SUBPROCESS_FLAGS)
        duration_match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", probe_result.stderr)
        # Mark complete
        clip_progress("Done", total_steps, 0)
```

**KODE BARU:**
```python
        # Mark complete
        clip_progress("Done", total_steps, 0)
```

(Cukup hapus 3 baris "Get total audio duration" / `probe_cmd` / `probe_result` / `duration_match` — variable-variable ini tidak dipakai di baris manapun setelahnya, aman dihapus total.)

---

## 4. CHECKLIST VERIFIKASI SEBELUM LAPOR BALIK

Jawab semua poin ini di laporan kamu ke Senior:

1. [ ] Method baru `_get_format_selector` sudah ditambahkan persis 1x, di lokasi yang benar (sebelum `_download_video_module`).
2. [ ] `grep -n "self._get_format_selector()" clipper_core.py` → harus muncul **persis 4 kali**.
3. [ ] `grep -n 'format_selector = "bestvideo\[height>=720\]'` (baris lama hardcoded) → harus **0 hasil** (semua sudah diganti).
4. [ ] `grep -n "audio_file" clipper_core.py` di sekitar method `process_clip` → variable `audio_file` yang tidak terdefinisi sudah tidak ada lagi di method ini.
5. [ ] File `clipper_core.py` masih valid Python — jalankan `python -c "import ast; ast.parse(open('clipper_core.py', encoding='utf-8').read())"` dan pastikan tidak ada `SyntaxError`.
6. [ ] Tempel HASIL DIFF (before/after) dari kedua task di laporan balik, jangan cuma bilang "sudah selesai".

---

## 5. YANG TIDAK BOLEH DILAKUKAN

- Jangan ubah `subtitle_language` default atau logic di tempat lain.
- Jangan sentuh `add_hook_with_progress`, Hook Maker, atau TTS — bug ini TIDAK ada hubungannya dengan Hook Maker.
- Jangan tambah dependency baru.
- Jangan ubah UI (`web/`).
