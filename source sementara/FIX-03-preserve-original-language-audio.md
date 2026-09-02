# INSTRUKSI FIX BUG #3 — SSR_CLIPPER
**Untuk: Opus 4.6 (thinking)**
**Dari: Senior Auditor**
**Status: SIAP EKSEKUSI**

---

## 0. KONTEKS — KENAPA ADA FIX #3 (baca dulu, penting)

FIX-01 (sebelumnya) mencoba menyelesaikan "audio dub Inggris" dengan cara memfilter audio track berdasarkan `self.subtitle_language` (mis. paksa cari track berbahasa `id`). **Itu premis yang salah**, karena user membuktikan dengan screenshot: video masih ke-dub Inggris SETELAH fix itu di-apply. Requirement yang benar dari owner project:

> Kalau video asli Indonesia → JANGAN diganti ke bahasa lain.
> Kalau video asli English → JANGAN diganti ke bahasa lain juga.
> **Intinya: selalu pakai bahasa ASLI video, apapun itu.** Jangan pernah menebak/memaksa bahasa target tertentu.

Filter `bestaudio[language^={self.subtitle_language}]` di FIX-01 itu menebak — bisa salah ke dua arah (video asli English tapi `subtitle_language` di-set "id" → bisa kejeblos ambil dub Indonesia-nya kalau ada; atau kalau tidak ketemu track sesuai tebakan, dia fallback ke `bestaudio` polos yang balik lagi ke masalah semula). Root cause aslinya BUKAN "butuh filter bahasa", tapi ada di tempat lain:

**yt-dlp sendiri (sejak PR resmi [#11803](https://github.com/yt-dlp/yt-dlp/commit/dc3c4fddcc653989dae71fc563d82a308fc898cc), "Prioritize original language over auto-dubbed audio") SUDAH otomatis mendeteksi mana track yang BENAR-BENAR ASLI** (apapun bahasanya — bukan berdasarkan kode bahasa, tapi berdasarkan flag `isOriginal` yang dikirim YouTube sendiri per track). yt-dlp mengekspos ini lewat field internal `language_preference`, di mana track asli dapat skor prioritas TERTINGGI, track dub dapat skor rendah:

```python
'language_preference': PREFERRED_LANG_VALUE if is_original else 5 if is_default else -10 if is_descriptive else -1,
```

Field ini otomatis ikut dipakai yt-dlp saat sorting format — **ASALKAN urutan sort tidak di-override**. Masalahnya, kode kita eksplisit set:

```python
'format_sort': ['res', 'br'],       # (module-based)
"--format-sort", "res,br",          # (subprocess/CLI-based)
```

Ini menaruh **resolusi & bitrate LEBIH PRIORITAS** daripada default `lang` milik yt-dlp. Untuk audio-only candidate, resolusi tidak relevan (selalu tie), jadi **bitrate jadi penentu utama** — kalau track dub Inggris kebetulan bitrate-nya sama/lebih tinggi dari track asli, dia menang duluan SEBELUM sempat sampai ke kriteria `lang`. Ini penjelasan yang konsisten kenapa bug masih muncul walau FIX-01 sudah jalan.

**Fix yang benar: taruh `lang` di URUTAN PALING DEPAN di `format_sort`, dan HAPUS logic tebak-bahasa di `_get_format_selector()`.** Dengan begitu yt-dlp pakai deteksi native-nya sendiri untuk video BAHASA APAPUN, tidak perlu kita tebak sama sekali.

---

## 1. ATURAN

1. Hanya edit `clipper_core.py`.
2. Exact string match untuk semua "KODE LAMA" → "KODE BARU" di bawah.
3. Kalau teks lama tidak ketemu persis, STOP dan laporkan — jangan improvisasi.
4. Jangan ubah bagian lain di luar yang diinstruksikan.

---

## 2. TASK 1 — Sederhanakan `_get_format_selector()`, hapus logic tebak-bahasa

**File:** `clipper_core.py`, method `_get_format_selector` (dekat awal class `AutoClipperCore`, sebelum `_download_video_module`).

**KODE LAMA (ganti seluruh body method ini):**
```python
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
```

**KODE BARU:**
```python
    def _get_format_selector(self) -> str:
        """Build the yt-dlp format selector used by every video/section download.

        NOTE: this does NOT filter by any specific language. Avoiding
        YouTube's auto-dubbed audio tracks is handled by format_sort
        (see the 'lang' key placed first — yt-dlp's own YouTube extractor
        already flags which track is the TRUE ORIGINAL via
        'language_preference'/is_original, regardless of what language
        that original happens to be). Guessing/forcing a specific
        language code here would be wrong: original-language video must
        stay in its original language, whatever that language is.
        """
        base_video = "bestvideo[height>=720][height<=2160]"
        return (
            f"{base_video}+bestaudio/"
            f"best[height>=720][height<=2160]/"
            f"bestvideo+bestaudio/best"
        )
```

---

## 3. TASK 2 — Taruh `lang` di depan `format_sort` (4 lokasi)

### 3a. Module-based (2 kemunculan, identik, TEXT SAMA di 2 fungsi berbeda)

**KODE LAMA (cari & ganti KE-2 kemunculannya):**
```python
            'format_sort': ['res', 'br'],
```

**KODE BARU:**
```python
            'format_sort': ['lang', 'res', 'br'],
```

### 3b. Subprocess/CLI-based (2 kemunculan, identik, TEXT SAMA di 2 fungsi berbeda)

**KODE LAMA (cari & ganti KE-2 kemunculannya):**
```python
                "--format-sort", "res,br",
```

**KODE BARU:**
```python
                "--format-sort", "lang,res,br",
```

> Catatan: perhatikan indentasi — baris CLI ini indentasi-nya 16 spasi (lebih dalam dari yang module-based, 12 spasi). Cocokkan persis, jangan sampai salah indent.

---

## 4. CHECKLIST VERIFIKASI

1. [ ] `grep -n "language\^=" clipper_core.py` → **0 hasil** (logic tebak-bahasa sudah bersih terhapus).
2. [ ] `grep -c "'format_sort': \['lang', 'res', 'br'\]," clipper_core.py` → **2**
3. [ ] `grep -c '"--format-sort", "lang,res,br",' clipper_core.py` → **2**
4. [ ] `python -c "import ast; ast.parse(open('clipper_core.py', encoding='utf-8').read())"` → tidak boleh error.
5. [ ] Tempel diff before/after lengkap di laporan balik.

---

## 5. YANG TIDAK BOLEH DILAKUKAN

- Jangan sentuh 4 baris `format_selector = self._get_format_selector()` (pemanggilnya) — itu sudah benar dari FIX-01, tidak perlu diubah lagi.
- Jangan sentuh bug `temp_captioned`/watermark (FIX-02) — sudah selesai & terpisah.
- Jangan tambah dependency baru atau update versi yt-dlp — fix ini murni pakai fitur yt-dlp yang sudah ada.
