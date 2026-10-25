# FIX 04 — Real Functional Test (bukan cuma cek listing) + Status Text-Only Format

## Context
Repo: `https://github.com/Stella-Desain/clip-v2/tree/feature/pywebview-desktop-integration`
Ini lanjutan dari FIX-03 yang udah di-merge. Owner nemu bug nyata dari hasil FIX-03: klik Test di `[Local] tiny` bilang "Ready" padahal model itu belum pernah didownload sama sekali. Root cause: `test_model` yang lama cuma cek apakah LIBRARY `faster_whisper` ke-import, bukan cek apakah MODEL SPESIFIK itu ada di disk.

Scope kamu **HANYA** 2 file ini:
- `app.py`
- `web/app.js`

Jangan sentuh file lain.

---

## PART A: Bug nyata — local model test gak cek model spesifik, cuma cek library

**Lokasi — `app.py`, method `test_model` (~line 136-147), bagian awal:**
```python
def test_model(self, base_url, api_key, model, model_type):
    """Test apakah model tertentu BENERAN bisa dipanggil, bukan cuma ada di daftar."""
    if model_type == 'local':
        try:
            import faster_whisper  # noqa
            return {"status": "ok", "message": "Local whisper library terpasang dan siap."}
        except ImportError:
            try:
                import whisper  # noqa
                return {"status": "ok", "message": "Local whisper library terpasang dan siap."}
            except ImportError:
                return {"status": "error", "message": "Library whisper belum terinstall. Klik 'Install All' dulu."}
```

**Root cause:** `import faster_whisper` cuma ngecek package Python-nya terinstall, BUKAN ngecek apakah file model (`tiny`, `large-v3-turbo`, dll) udah didownload ke disk. Model whisper didownload terpisah dari library-nya (lihat `clipper_core.py` line 2212-2255, function `_load_local_whisper` — dia manggil `WhisperModel(model_size, ...)` yang auto-download dari HuggingFace saat pertama kali dipakai). Jadi walau library-nya terinstall, model spesifik yang dipilih user bisa aja belum pernah didownload — tapi test lama selalu bilang "Ready".

**Fix — ganti block itu jadi ini:**
```python
    if model_type == 'local':
        try:
            from faster_whisper.utils import download_model
        except ImportError:
            return {"status": "error", "message": "Error: whisper library belum terinstall"}
        try:
            download_model(model, local_files_only=True)
            return {"status": "ok", "message": "Ready - Installed"}
        except Exception:
            return {"status": "error", "message": "Error: model belum di-download"}
```

**Penjelasan kenapa ini bener:** `download_model(model, local_files_only=True)` itu function INTERNAL dari `faster-whisper` yang dipanggil sama `WhisperModel.__init__` di baliknya. Kalau `local_files_only=True` dan model belum ada di cache HuggingFace lokal, dia raise exception (`LocalEntryNotFoundError`) TANPA nyoba download. Kalau model UDAH ada di cache, dia return path lokalnya tanpa error. Ini cara paling ringan buat ngecek "apakah model X udah didownload" tanpa harus load seluruh model ke memory (yang berat & lambat).

Sudah diverifikasi jalan: `download_model('tiny', local_files_only=True)` raise `LocalEntryNotFoundError` kalau belum ada, dan model key seperti `'tiny'`, `'large-v3-turbo'` itu valid (cocok dengan yang dipakai app ini di `web/app.js` line 563-568).

---

## PART B: Ganti STT/TTS dari "cek listing doang" jadi REAL functional test

**Lokasi — `app.py`, method `test_model`, bagian else (~line 168-175):**
```python
            else:
                # stt / tts: gak ada format request ringan yang seragam antar provider.
                # Fallback: pastikan model masih ada di daftar model terbaru provider.
                models_resp = self.get_models(base_url, api_key)
                available = models_resp.get("models", [])
                if model in available:
                    return {"status": "ok", "message": "Model terdaftar di provider (bukan full functional test, cuma verifikasi ketersediaan)."}
                return {"status": "error", "message": "Model tidak ditemukan lagi di daftar provider ini — mungkin sudah deprecated."}
```

Owner minta ini diganti jadi REAL test — beneran manggil endpoint TTS/STT-nya, bukan cuma cek nama model ada di daftar.

**Fix — ganti seluruh method `test_model` jadi versi ini (replace total dari `def test_model` sampai akhir method-nya):**

```python
    def test_model(self, base_url, api_key, model, model_type):
        """Test apakah model tertentu BENERAN bisa dipanggil (real call), bukan cuma ada di daftar."""
        if model_type == 'local':
            try:
                from faster_whisper.utils import download_model
            except ImportError:
                return {"status": "error", "message": "Error: whisper library belum terinstall"}
            try:
                download_model(model, local_files_only=True)
                return {"status": "ok", "message": "Ready - Installed"}
            except Exception:
                return {"status": "error", "message": "Error: model belum di-download"}

        if not base_url or not api_key:
            return {"status": "error", "message": "Empty"}
        if not model:
            return {"status": "error", "message": "Error: model belum dipilih"}

        headers = self._auth_headers(api_key)
        url = base_url.rstrip("/")

        try:
            if model_type == 'chat':
                endpoint = url if url.endswith("/chat/completions") else f"{url}/chat/completions"
                resp = requests.post(endpoint, headers=headers, json={
                    "model": model,
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 1
                }, timeout=15)
                if resp.status_code == 200:
                    return {"status": "ok", "message": "Ready - API tested"}
                return {"status": "error", "message": f"Error {resp.status_code}"}

            elif model_type == 'tts':
                endpoint = url if url.endswith("/audio/speech") else f"{url}/audio/speech"
                tts_headers = dict(headers)
                tts_headers["Content-Type"] = "application/json"
                resp = requests.post(endpoint, headers=tts_headers, json={
                    "model": model,
                    "input": "test",
                    "voice": "alloy"
                }, timeout=20)
                if resp.status_code == 200 and resp.content:
                    return {"status": "ok", "message": "Ready - API tested"}
                return {"status": "error", "message": f"Error {resp.status_code}"}

            elif model_type == 'stt':
                endpoint = url if url.endswith("/audio/transcriptions") else f"{url}/audio/transcriptions"
                wav_bytes = self._generate_silent_wav()
                files = {'file': ('test.wav', wav_bytes, 'audio/wav')}
                data = {'model': model}
                resp = requests.post(endpoint, headers=headers, files=files, data=data, timeout=20)
                if resp.status_code == 200:
                    return {"status": "ok", "message": "Ready - API tested"}
                return {"status": "error", "message": f"Error {resp.status_code}"}

            else:
                return {"status": "error", "message": "Error: tipe model tidak dikenal"}

        except requests.exceptions.Timeout:
            return {"status": "error", "message": "Error timeout"}
        except requests.exceptions.ConnectionError:
            return {"status": "error", "message": "Error connection failed"}
        except Exception as e:
            return {"status": "error", "message": f"Error {str(e)[:60]}"}

    def _generate_silent_wav(self, duration_sec=0.5, sample_rate=16000):
        """Bikin file WAV silent kecil di memory, dipakai buat test endpoint STT/transcription."""
        import io
        import wave
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(b'\x00\x00' * int(sample_rate * duration_sec))
        buf.seek(0)
        return buf.read()
```

**PENTING — batasan yang harus kamu tulis di laporan akhir (jangan diklaim sempurna):**
- Test TTS ngirim `"voice": "alloy"` (default OpenAI). Kalau provider custom butuh nama voice lain, test ini bisa false-negative (bilang error padahal model sebenernya oke, cuma parameter voice-nya yang gak cocok). Ini keterbatasan yang bisa diterima untuk sekarang.
- Test STT ngirim audio kosong (silent) 0.5 detik. Beberapa provider mungkin nolak audio yang isinya cuma silence. Kalau ternyata sering false-negative pas dites owner, laporkan biar dibahas lagi — jangan diakalin sendiri tanpa lapor.
- Import `io` dan `wave` taruh di dalam function `_generate_silent_wav` (bukan di top-level file), biar gak bentrok kalau nama itu udah dipakai di tempat lain di `app.py`. Cek dulu pakai grep `^import io\|^import wave` di `app.py` sebelum nambahin — kalau ternyata udah ada di top-level, boleh dipindah ke top, tapi WAJIB cek dulu.

---

## PART C: `get_models` harus ngasih tau kenapa gagal (buat status "Error 404")

**Lokasi — `app.py`, method `get_models` (~line 90-134), bagian try/except di akhir:**
```python
        url = self._get_models_url(base_url)
        try:
            resp = requests.get(url, headers=self._auth_headers(api_key), timeout=15)
            if resp.status_code != 200:
                return {"models": []}
            data = resp.json()
            items = data.get("data", [])
            models = []
            for item in items:
                mid = item.get("id")
                if mid:
                    models.append(mid)
            return {"models": models}
        except:
            return {"models": []}
```

**Fix — ganti jadi:**
```python
        url = self._get_models_url(base_url)
        try:
            resp = requests.get(url, headers=self._auth_headers(api_key), timeout=15)
            if resp.status_code != 200:
                return {"models": [], "error": str(resp.status_code)}
            data = resp.json()
            items = data.get("data", [])
            models = []
            for item in items:
                mid = item.get("id")
                if mid:
                    models.append(mid)
            return {"models": models}
        except requests.exceptions.Timeout:
            return {"models": [], "error": "timeout"}
        except requests.exceptions.ConnectionError:
            return {"models": [], "error": "connection failed"}
        except Exception as e:
            return {"models": [], "error": str(e)[:60]}
```

---

## PART D: Frontend — status text-only, no icon, format sesuai spesifikasi owner

Owner minta format status text PERSIS begini (tanpa icon/emoji sama sekali, warna teks aja yang beda buat sukses/error):
- Field kosong → `Empty`
- Key valid, model kelist → `Valid, 20 model loaded` (angkanya sesuai jumlah model asli dari provider itu)
- Key gagal/model gak ada → `Error 404` (atau kode/alasan singkat lain, JANGAN dump JSON mentah)
- Local model/library siap → `Ready - Installed`
- API model teruji beneran → `Ready - API tested`

**Lokasi — `web/app.js`, function `validateAndLoad` (~line 546-604). Ganti SELURUH bagian dari awal function sampai baris `// Categorize models based on strict rules` (JANGAN ubah bagian kategorisasi model di bawahnya, itu punya FIX-02, biarin tetap):**

```js
async function validateAndLoad(kind) {
  const baseUrl = kind.url ? kind.url.value.trim() : "";
  const apiKey = kind.key ? kind.key.value.trim() : "";
  kind.status.textContent = 'Testing...';
  kind.status.style.color = 'var(--text-muted)';

  try {
      // 1. Fetch models from ALL configured providers
      let allModels = [];
      const providers = [
          { name: 'OpenAI', url: aiView.fields.hfUrl, key: aiView.fields.hfKey },
          { name: 'Gemini', url: aiView.fields.hmUrl, key: aiView.fields.hmKey },
          { name: 'Custom1', url: aiView.fields.cmUrl, key: aiView.fields.cmKey },
          { name: 'Custom2', url: aiView.fields.cpUrl, key: aiView.fields.cpKey }
      ];

      // Add local models
      allModels.push('[Local] large-v3-turbo');
      allModels.push('[Local] large-v3');
      allModels.push('[Local] medium');
      allModels.push('[Local] small');
      allModels.push('[Local] base');
      allModels.push('[Local] tiny');

      let clickedValid = false;
      let ownModelCount = 0;
      let ownError = null;

      for (const p of providers) {
          if (p.url && p.url.value && p.key && p.key.value) {
              const isOwn = (baseUrl === p.url.value.trim() && apiKey === p.key.value.trim());
              try {
                  const pRes = await window.pywebview.api.get_models(p.url.value.trim(), p.key.value.trim());
                  if (pRes && pRes.models && pRes.models.length > 0) {
                      allModels = allModels.concat(pRes.models.map(m => `[${p.name}] ${m}`));
                      if (isOwn) {
                          clickedValid = true;
                          ownModelCount = pRes.models.length;
                      }
                  } else if (isOwn) {
                      ownError = (pRes && pRes.error) ? pRes.error : 'no models found';
                  }
              } catch (e) {
                  if (isOwn) ownError = String(e);
              }
          }
      }

      if (!apiKey) {
          kind.status.textContent = 'Empty';
          kind.status.style.color = 'var(--text-muted)';
      } else if (clickedValid) {
          kind.status.textContent = `Valid, ${ownModelCount} model loaded`;
          kind.status.style.color = 'var(--success)';
      } else if (ownError) {
          kind.status.textContent = `Error ${ownError}`;
          kind.status.style.color = 'var(--error)';
      } else if (allModels.length > 0) {
          kind.status.textContent = 'Other keys loaded';
          kind.status.style.color = 'var(--text-muted)';
      } else {
          kind.status.textContent = 'Error no models found';
          kind.status.style.color = 'var(--error)';
      }

      // Categorize models based on strict rules
      // ... (BAGIAN INI JANGAN DIUBAH, biarin persis kayak yang sekarang) ...
```

**Catatan:** function lanjut sama persis kayak sebelumnya mulai dari `const GEMINI_AUDIO_MODELS = ...` sampai akhir function — JANGAN diubah, cuma bagian di atas `// Categorize models` yang di-replace.

**Perhatikan perbedaan penting dari versi lama:**
- Gak ada lagi `return` di tengah function pas gagal — sekarang selalu lanjut ke kategorisasi model, biar dropdown tetep ke-refresh dari provider lain walau field ini sendiri gagal.
- Icon `❌ ✓ ℹ` semua dihapus, tinggal teks polos + warna (`var(--success)` / `var(--error)` / `var(--text-muted)`).

---

## PART E: Frontend — `testModelReadiness` juga text-only, no icon

**Lokasi — `web/app.js`, function `testModelReadiness` (dibuat di FIX-03, cari via `async function testModelReadiness`):**
```js
      const res = await window.pywebview.api.test_model(payload.base_url, payload.api_key, payload.model, payload.model_type);
      if (res && res.status === 'ok') {
          statusSpan.textContent = '✅ Ready — ' + res.message;
          statusSpan.style.color = 'var(--success)';
      } else {
          statusSpan.textContent = '❌ Not ready — ' + (res ? res.message : 'Unknown error');
          statusSpan.style.color = 'var(--error)';
      }
```

**Fix — ganti jadi (backend sekarang udah ngasih teks final di `res.message`, tinggal dipakai langsung tanpa nambahin prefix icon):**
```js
      const res = await window.pywebview.api.test_model(payload.base_url, payload.api_key, payload.model, payload.model_type);
      if (res && res.status === 'ok') {
          statusSpan.textContent = res.message;
          statusSpan.style.color = 'var(--success)';
      } else {
          statusSpan.textContent = res ? res.message : 'Error unknown';
          statusSpan.style.color = 'var(--error)';
      }
```

Juga cari bagian awal function yang ngecek model belum dipilih:
```js
  if (!modelField || !modelField.value || modelField.value.startsWith('Select Model')) {
      statusSpan.textContent = '❌ Pilih model dulu';
      statusSpan.style.color = 'var(--error)';
      return;
  }
```
Ganti textContent-nya jadi text-only juga:
```js
  if (!modelField || !modelField.value || modelField.value.startsWith('Select Model')) {
      statusSpan.textContent = 'Empty';
      statusSpan.style.color = 'var(--error)';
      return;
  }
```

Dan `testBtn.textContent = '...'` pas loading boleh diganti jadi `'Testing...'` biar lebih jelas (opsional, gak wajib).

---

## Acceptance Criteria (WAJIB dites manual, bukan cuma py_compile/node --check)
1. Pilih `[Local] tiny` di Caption Maker, klik Test — kalau model `tiny` BENERAN belum pernah didownload di komputer kamu, status HARUS jadi `Error: model belum di-download`, BUKAN `Ready - Installed`.
2. Pilih model whisper local yang UDAH pernah dipakai/didownload sebelumnya (misal `large-v3-turbo` kalau sebelumnya app ini udah pernah generate caption pakai itu), klik Test — harus `Ready - Installed`.
3. Klik Test di field API key yang kosong — status jadi `Empty`, warna abu-abu.
4. Klik Test di field API key dengan key salah — status jadi `Error <kode>` (misal `Error 401` atau `Error 404`), BUKAN dump JSON panjang.
5. Klik Test di field API key yang valid — status jadi `Valid, <N> model loaded` dengan N = jumlah model asli.
6. Klik Test di dropdown model chat yang valid — status jadi `Ready - API tested`.
7. Klik Test di dropdown model TTS/STT — pastikan itu BENERAN manggil endpoint `/audio/speech` atau `/audio/transcriptions` (cek network log/console, bukan cuma manggil `/models`).
8. Screenshot atau paste hasil test manual poin 1-7 di laporan akhir kamu. Kalau poin 1 gagal (masih bilang Ready padahal belum download), JANGAN dilaporin selesai — cari lagi kenapa.

## JANGAN
- Jangan ubah bagian kategorisasi model (`GEMINI_AUDIO_MODELS`, `isTTS`, `isSTT`, `isChat`) — itu udah bener dari FIX-02, biarin apa adanya.
- Jangan hapus `download_model` dari `faster_whisper.utils` dan ganti pakai cara lain tanpa lapor dulu — ini udah diverifikasi jalan.
- Jangan nambahin dependency baru di `requirements.txt`. `io` dan `wave` itu built-in Python, `faster_whisper.utils.download_model` udah ada dari dependency yang sudah terinstall.
