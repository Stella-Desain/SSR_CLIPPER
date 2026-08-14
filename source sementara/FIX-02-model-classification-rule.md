# FIX 02 — Filter Model Salah Kategori (Caption Maker Nampilin Model yang Gak Bisa Transkripsi)

## Context
Repo: `https://github.com/Stella-Desain/clip-v2/tree/feature/pywebview-desktop-integration`

Business rule dari owner project (WAJIB dipegang, ini bukan opsional):
> Tiap program (Highlight Finder, Caption Maker, Hook Maker, YT Title Maker) cuma boleh nampilin model di dropdown-nya yang BENERAN bisa jalanin fungsi program itu. Contoh: Hook Maker cuma boleh nampilin model yang punya kemampuan TTS.

Scope kamu **HANYA** file ini:
- `web/app.js`

Jangan sentuh file lain.

---

## BUG: Kategorisasi model Gemini terlalu longgar (broad substring match)

**Lokasi — `web/app.js`, function `validateAndLoad` (~line 582-608):**
```js
const isTTS = (m) => {
    const lower = m.toLowerCase();
    return lower.includes('tts') || lower.endsWith('-tts');
};

const isSTT = (m) => {
    const lower = m.toLowerCase();
    return lower.includes('whisper') || lower.includes('stt') || lower.endsWith('-audio') || lower.includes('gemini-3') || m.startsWith('[Local]');
};

const isChat = (m) => {
    if (m.startsWith('[Local]')) return false;
    const lower = m.toLowerCase();
    if (lower.includes('gemini-3')) return !isTTS(m);
    return !isTTS(m) && !isSTT(m);
};

const hfModels = allModels.filter(isChat);
const cmModels = allModels.filter(isSTT);
const hmModels = allModels.filter(isTTS);
const ytModels = allModels.filter(isChat);
```

**Root cause:** `isSTT` nge-match SEMUA string yang ngandung `"gemini-3"`, gak peduli model itu beneran punya kemampuan audio/STT atau engga. Bandingkan sama list model Gemini yang backend sendiri kasih tau di `app.py`, function `get_models` (~line 90-109):

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

Backend sendiri sudah bilang: `gemini-3.5-flash-lite` dan `gemini-3-flash-preview` itu CHAT-ONLY, bukan audio-capable. Tapi karena `isSTT` cuma cek substring `"gemini-3"`, dua model chat-only ini tetap lolos masuk ke `cmModels` (Caption Maker dropdown) — padahal mereka gak bisa transkripsi audio. User yang pilih model ini di Caption Maker bakal gagal pas processing, tanpa tau kenapa. Ini melanggar business rule di atas.

Bonus bug kecil di baris yang sama: `gemini-3.1-flash-tts-preview` juga ngandung `"gemini-3"`, jadi dia lolos `isSTT` DAN `isTTS` sekaligus — muncul dobel di Caption Maker maupun Hook Maker.

---

## Fix

Ganti seluruh 3 function classifier itu jadi whitelist eksplisit khusus untuk model Gemini (paling aman & efisien, gak perlu ubah backend):

```js
// Daftar model Gemini yang BENERAN audio-capable (sinkron dengan comment di app.py get_models())
const GEMINI_AUDIO_MODELS = ['gemini-3.6-flash', 'gemini-3.5-flash', 'gemini-3.1-pro-preview'];

const isTTS = (m) => {
    const lower = m.toLowerCase();
    return lower.includes('tts') || lower.endsWith('-tts');
};

const isSTT = (m) => {
    if (m.startsWith('[Local]')) return true;
    const lower = m.toLowerCase();
    if (lower.includes('whisper') || lower.includes('stt') || lower.endsWith('-audio')) return true;
    // Gemini: hanya model yang secara eksplisit audio-capable DAN bukan TTS
    const bareName = m.replace(/^\[[^\]]+\]\s*/, ''); // buang prefix "[Custom1] " dll
    if (GEMINI_AUDIO_MODELS.includes(bareName) && !isTTS(m)) return true;
    return false;
};

const isChat = (m) => {
    if (m.startsWith('[Local]')) return false;
    if (isTTS(m)) return false;
    // Gemini audio-capable model tetap bisa dipakai chat juga, tapi model non-gemini-3
    // yang sudah kena isSTT (whisper/stt/-audio) TIDAK boleh dianggap chat
    const lower = m.toLowerCase();
    if ((lower.includes('whisper') || lower.includes('stt') || lower.endsWith('-audio')) && !lower.includes('gemini')) {
        return false;
    }
    return true;
};
```

**Catatan penting buat kamu (Gemini):**
- Nama variable `bareName` harus buang prefix provider (`[OpenAI] `, `[Custom1] `, dst) sebelum dicocokkan ke `GEMINI_AUDIO_MODELS`, karena `allModels` isinya string kayak `[Gemini] gemini-3.5-flash`, bukan `gemini-3.5-flash` polos.
- Urutan filter TETAP: `hfModels = allModels.filter(isChat)`, `cmModels = allModels.filter(isSTT)`, `hmModels = allModels.filter(isTTS)`, `ytModels = allModels.filter(isChat)` — JANGAN diubah, cuma isi function classifier-nya yang diganti.
- Kalau nanti backend nambah model Gemini baru yang audio-capable, dia harus ditambah manual ke `GEMINI_AUDIO_MODELS` di sini DAN ke comment/list di `app.py`. Tambahkan komentar di kode buat ingetin ini.

---

## Dead code cleanup (opsional tapi disarankan, low risk)

**Lokasi — `web/app.js`, function `getProviders` (~line 641-648):**
```js
function getProviders() {
  return {
    openai: { url: aiView.fields.openaiUrl, key: aiView.fields.openaiKey, status: aiView.fields.openaiStatus },
    anthropic: { url: aiView.fields.anthropicUrl, key: aiView.fields.anthropicKey, status: aiView.fields.anthropicStatus },
    gemini: { url: aiView.fields.geminiUrl, key: aiView.fields.geminiKey, status: aiView.fields.geminiStatus },
    custom: { url: aiView.fields.cpUrl, key: aiView.fields.cpKey, status: aiView.fields.cpValidateStatus }
  };
}
```
Function ini gak pernah dipanggil di mana pun (cek pakai grep `getProviders(` di seluruh `web/`), dan dia reference field (`aiView.fields.openaiUrl`, `.anthropicUrl`, dst) yang **tidak ada** di object `fields` yang di-return `ai-settings.js`. Kalau ini kepanggil bakal error `Cannot read properties of undefined`.

**Fix:** hapus function ini seluruhnya. Sebelum hapus, jalankan `grep -rn "getProviders(" web/` buat mastiin bener-bener gak dipanggil di file lain (`dashboard.js`, `home.js`, dll). Kalau ternyata dipanggil di tempat lain, JANGAN dihapus — laporkan ke saya dulu.

---

## Acceptance Criteria
1. Simulasikan (via console log atau unit test manual) `allModels` array berisi: `['[Gemini] gemini-3.6-flash', '[Gemini] gemini-3.5-flash-lite', '[Gemini] gemini-3.1-flash-tts-preview', '[Gemini] gemini-3-flash-preview']`.
2. Pastikan hasilnya:
   - `hfModels` (Highlight Finder) berisi: `gemini-3.6-flash`, `gemini-3.5-flash-lite`, `gemini-3-flash-preview` (SEMUA kecuali yang TTS).
   - `cmModels` (Caption Maker) HANYA berisi: `gemini-3.6-flash` (yang lain TIDAK boleh muncul).
   - `hmModels` (Hook Maker) HANYA berisi: `gemini-3.1-flash-tts-preview`.
3. Model non-Gemini (OpenAI, Whisper API custom, dll) perilakunya tetap sama seperti sebelumnya — jangan sampai regresi di provider lain.
4. Laporkan hasil test manual di atas + diff code yang diubah.

## JANGAN
- Jangan ubah `get_models()` di `app.py` (backend).
- Jangan ubah urutan pemanggilan `.filter()`.
- Jangan hapus `validate_api_key()` di `app.py` — itu dead code juga tapi ditangani di file FIX-03, bukan di sini.
