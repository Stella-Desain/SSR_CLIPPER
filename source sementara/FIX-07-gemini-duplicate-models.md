# FIX 07 — Model Gemini Ke-load 2x di Dropdown

## Context
Repo: `https://github.com/Stella-Desain/clip-v2/tree/feature/pywebview-desktop-integration`

Bug lama (bukan dari FIX-01 s/d FIX-06), baru ketauan sekarang: dropdown Highlight Finder/Caption Maker nampilin beberapa model Gemini 2x (`gemini-3.6-flash`, `gemini-3.5-flash`, `gemini-3.1-pro-preview` masing-masing muncul dobel).

Scope kamu **2 file ini**:
- `app.py` (root cause utama)
- `web/app.js` (defensive fix, biar kelas bug ini gak balik lagi walau providernya beda)

---

## PART A (ROOT CAUSE): List model Gemini di backend emang literally ada duplikat

**Lokasi — `app.py`, method `get_models` (~line 96-109):**
```python
        if "generativelanguage.googleapis.com" in base_url:
            return {"models": [
                # Chat / Highlight Finder models
                "gemini-3.6-flash",
                "gemini-3.5-flash",
                "gemini-3.5-flash-lite",
                "gemini-3.1-pro-preview",
                "gemini-3-flash-preview",
                # Audio / STT-capable models (multimodal, can transcribe audio)
                "gemini-3.6-flash",
                "gemini-3.5-flash",
                "gemini-3.1-pro-preview",
                # TTS models (Text-to-Speech)
                "gemini-3.1-flash-tts-preview"
            ]}
```

**Root cause:** 3 model (`gemini-3.6-flash`, `gemini-3.5-flash`, `gemini-3.1-pro-preview`) ditulis 2x di list Python ini — sekali di bagian "Chat", sekali lagi di bagian "Audio/STT-capable" (dulu kayaknya dimaksudkan buat dokumentasi doang, tapi karena ini list Python beneran bukan komentar, isinya kekirim 2x ke frontend). Sejak FIX-02, penentuan model mana yang audio-capable udah dihandle sama whitelist `GEMINI_AUDIO_MODELS` di `web/app.js` — jadi pengulangan di sini udah gak perlu lagi.

**Fix — ganti block itu jadi:**
```python
        if "generativelanguage.googleapis.com" in base_url:
            return {"models": [
                "gemini-3.6-flash",
                "gemini-3.5-flash",
                "gemini-3.5-flash-lite",
                "gemini-3.1-pro-preview",
                "gemini-3-flash-preview",
                "gemini-3.1-flash-tts-preview"
                # Info audio/STT-capable model mana aja sekarang ada di
                # GEMINI_AUDIO_MODELS (web/app.js), gak perlu diulang di sini.
            ]}
```

---

## PART B (DEFENSIVE): Dedup umum di frontend, biar provider lain gak bisa bikin bug yang sama

Backend Custom Provider 1/2 itu endpoint MILIK ORANG LAIN (litellm proxy dsb) — kita gak kontrol datanya. Kalau suatu saat providernya sendiri yang ngirim model ID kembar, kita harus tetep aman.

**Lokasi — `web/app.js`, function `validateAndLoad`, tepat SETELAH baris filter prefix yang udah ada dari FIX-05 (~line 590):**
```js
      // Buang entry yang gak punya prefix provider valid (misal sisa data lama sebelum sistem prefix ada)
      const VALID_PREFIX_RE = /^\[(OpenAI|Gemini|Custom1|Custom2|Local)\]\s/;
      allModels = allModels.filter(m => VALID_PREFIX_RE.test(m));
```

**Tambahkan 1 baris PERSIS SETELAH baris filter itu:**
```js
      // Buang duplikat exact-string (misal provider ngirim model ID yang sama 2x)
      allModels = [...new Set(allModels)];
```

Urutannya harus: filter prefix DULU, baru dedup pakai `Set`. Jangan dibalik.

---

## Acceptance Criteria
1. Test API key Gemini yang valid → hitung total model di dropdown Highlight Finder, harus ada TEPAT 5 model unik (`gemini-3.6-flash`, `gemini-3.5-flash`, `gemini-3.5-flash-lite`, `gemini-3.1-pro-preview`, `gemini-3-flash-preview`), TIDAK ADA yang dobel.
2. Dropdown Caption Maker (STT) harus tetep cuma nampilin `gemini-3.6-flash`, `gemini-3.5-flash`, `gemini-3.1-pro-preview` — MASING-MASING SEKALI, gak dobel juga (whitelist `GEMINI_AUDIO_MODELS` jangan sampai ikut ke-filter atau berubah).
3. Status "Valid, N model loaded" buat Gemini sekarang harus nunjukin angka yang BENERAN (6 model unik dari backend, bukan 9 kayak sebelumnya).
4. Test provider lain (Custom1/Custom2) — pastiin count model-nya TETEP SAMA kayak sebelum fix ini (dedup gak boleh ngilangin model yang emang beda-beda).
5. Screenshot dropdown Highlight Finder setelah fix, buktiin gak ada lagi entry dobel.

## JANGAN
- Jangan hapus/ubah `GEMINI_AUDIO_MODELS` whitelist di `web/app.js` (punya FIX-02) — itu tetep sumber kebenaran buat kategorisasi STT, gak boleh disamain sama urutan list backend.
- Jangan sentuh model list buat provider selain Gemini (`api.anthropic.com` dst) di `get_models`.
- Jangan taruh `[...new Set(...)]` SEBELUM filter prefix — urutan penting biar kerja bareng dengan benar.
