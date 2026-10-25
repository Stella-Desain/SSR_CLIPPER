# FIX 03 — Fitur "Test Model Readiness" + Perjelas Status

## Context
Repo: `https://github.com/Stella-Desain/clip-v2/tree/feature/pywebview-desktop-integration`

Ini bukan cuma bug fix, ini penambahan fitur yang diminta owner:
1. Tombol "Test" di sebelah tiap dropdown Select Model (Highlight Finder, Caption Maker, Hook Maker, YT Title Maker) buat mastiin model yang dipilih BENERAN ready dipakai — bukan cuma numpang muncul di daftar model.
2. Status text setelah test harus jelas, gak ambigu.

Scope kamu **HANYA** 3 file ini:
- `app.py`
- `web/components/ai-settings.js`
- `web/app.js`

Kerjain FIX-01 dan FIX-02 dulu (kalau ada), baru kerjain ini — supaya gak konflik dengan `check_dependencies`/`isSTT` yang mungkin berubah.

---

## PART A: Bug status misleading (kerjain dulu, ini lebih gampang)

**Lokasi — `web/app.js`, function `validateAndLoad` (~line 573-580):**
```js
if (!clickedValid && allModels.length === 0) {
    kind.status.textContent = '❌ Invalid key or no models found';
    kind.status.style.color = 'var(--error)';
    return;
}

kind.status.textContent = clickedValid ? `✓ Valid, models loaded` : '✓ (Other keys loaded)';
kind.status.style.color = 'var(--success)';
```

**Bug:** kalau user klik "Test" di field yang API key-nya KOSONG, tapi provider lain punya key valid, status tetap muncul warna hijau "✓ (Other keys loaded)" — kelihatan kayak field ini berhasil divalidasi, padahal field ini sendiri gak pernah dites (key-nya kosong).

**Fix:** tambahkan pengecekan field kosong SEBELUM baris di atas:
```js
const ownKeyEmpty = !apiKey;

if (ownKeyEmpty) {
    if (allModels.length > 0) {
        kind.status.textContent = 'ℹ Field ini kosong — pakai model dari provider lain';
        kind.status.style.color = 'var(--text-muted)';
    } else {
        kind.status.textContent = '❌ Isi API key dulu';
        kind.status.style.color = 'var(--error)';
    }
    // tetap lanjut supaya dropdown lain ke-update, tapi jangan return di sini,
    // biarkan proses kategorisasi model di bawah tetap jalan seperti biasa
} else if (!clickedValid && allModels.length === 0) {
    kind.status.textContent = '❌ Invalid key or no models found';
    kind.status.style.color = 'var(--error)';
    return;
} else {
    kind.status.textContent = clickedValid ? '✓ Valid, models loaded' : '✓ (Other keys loaded)';
    kind.status.style.color = 'var(--success)';
}
```
Sesuaikan penempatan biar gak double-declare variable yang udah ada di scope (`apiKey` sudah ada di baris atas function ini, tinggal pakai).

---

## PART B: Backend — tambah method `test_model`

**Lokasi — `app.py`, taruh method baru ini persis di bawah `get_models` (~line 134), sebelum `save_ai_settings`:**

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

    if not base_url or not api_key:
        return {"status": "error", "message": "Base URL atau API key kosong, gak bisa ditest."}
    if not model:
        return {"status": "error", "message": "Belum ada model yang dipilih."}

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
                return {"status": "ok", "message": "Model merespon normal, siap dipakai."}
            return {"status": "error", "message": f"HTTP {resp.status_code}: {resp.text[:200]}"}
        else:
            # stt / tts: gak ada format request ringan yang seragam antar provider.
            # Fallback: pastikan model masih ada di daftar model terbaru provider.
            models_resp = self.get_models(base_url, api_key)
            available = models_resp.get("models", [])
            if model in available:
                return {"status": "ok", "message": "Model terdaftar di provider (bukan full functional test, cuma verifikasi ketersediaan)."}
            return {"status": "error", "message": "Model tidak ditemukan lagi di daftar provider ini — mungkin sudah deprecated."}
    except requests.exceptions.Timeout:
        return {"status": "error", "message": "Timeout — provider tidak merespon dalam 15 detik."}
    except Exception as e:
        return {"status": "error", "message": str(e)}
```

**PENTING — jujur soal keterbatasan:** untuk `model_type` `'stt'`/`'tts'`, ini BUKAN full functional test (gak ada cara ringan & seragam buat beneran manggil STT/TTS API semua provider). Test cuma verifikasi model masih ada di daftar provider. Untuk `'chat'`, ini beneran manggil API dengan request minimal. Tulis ini di laporan akhir kamu, jangan diklaim sebagai full test kalau bukan.

---

## PART C: Frontend UI — tombol Test di tiap dropdown

**Lokasi — `web/components/ai-settings.js`, function `makeApiField` (~line 77-120).**

Sekarang branch `isSelect` cuma bikin `<select>` doang tanpa tombol test:
```js
if (isSelect) {
  const sel = document.createElement('select');
  sel.className = 'select';
  sel.style.cssText = `...`;
  sel.innerHTML = `<option>${placeholder || 'Select Model'}</option>`;
  group.appendChild(sel);
  return { element: group, input: sel };
}
```

**Ganti jadi** (bikin wrapper flex kayak branch text-input di bawahnya, tambah tombol Test + status span):
```js
if (isSelect) {
  const wrapper = document.createElement('div');
  wrapper.style.cssText = 'display:flex;gap:8px;align-items:stretch;';

  const sel = document.createElement('select');
  sel.className = 'select';
  sel.style.cssText = `background:${FIELD_BG};border:none;border-radius:6px;height:${INPUT_H};flex:1;font-size:14px;color:var(--text);padding:0 32px 0 12px;cursor:pointer;appearance:none;
    background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%236B7280' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E");
    background-repeat:no-repeat;background-position:right 12px center;`;
  sel.innerHTML = `<option>${placeholder || 'Select Model'}</option>`;

  const testBtn = document.createElement('button');
  testBtn.style.cssText = `background:${FIELD_BG};border:none;border-radius:6px;padding:0 18px;font-weight:500;font-size:13px;cursor:pointer;height:${INPUT_H};white-space:nowrap;color:var(--text);font-family:inherit;flex-shrink:0;`;
  testBtn.textContent = 'Test';

  wrapper.appendChild(sel);
  wrapper.appendChild(testBtn);
  group.appendChild(wrapper);

  const statusSpan = document.createElement('span');
  statusSpan.style.cssText = 'font-size:12px; margin-top:4px; min-height:16px; display:block;';
  group.appendChild(statusSpan);

  return { element: group, input: sel, testBtn, status: statusSpan };
}
```

**Lalu update return object di paling bawah `ai-settings.js` (~line 866-932)** — tambahkan `hfModelTestBtn`, `hfModelStatus`, `cmModelTestBtn`, `cmModelStatus`, `hmModelTestBtn`, `hmModelStatus`, `ytModelTestBtn`, `ytModelStatus` yang diambil dari `hfModel.testBtn`, `hfModel.status`, dst (ingat: variable `hfModel`, `cmModel`, `hmModel`, `ytTitle` sudah dibuat lebih atas di file ini lewat `makeApiField(..., true)`):

```js
      hfModel: hfModel.input,
      hfModelTestBtn: hfModel.testBtn,
      hfModelStatus: hfModel.status,
      cmModel: cmModel.input,
      cmModelTestBtn: cmModel.testBtn,
      cmModelStatus: cmModel.status,
      hmModel: hmModel.input,
      hmModelTestBtn: hmModel.testBtn,
      hmModelStatus: hmModel.status,
      ytModel: ytTitle.input,
      ytModelTestBtn: ytTitle.testBtn,
      ytModelStatus: ytTitle.status,
```
(field `hfModel`, `cmModel`, `hmModel`, `ytModel` yang sudah ada sebelumnya di return object jangan sampai didobel-deklarasi — cari baris lama punya nama sama dan REPLACE, bukan nambah baru).

---

## PART D: Frontend logic — wiring tombol Test ke backend

**Lokasi — `web/app.js`, taruh block baru ini persis di bawah block `reloadModelBtn` (~line 717), sebelum `loadReplizData()`:**

```js
// ── Test Model Readiness ──
function resolveModelPayloadForTest(modelField) {
  // Mirror logic dari getSmartPayload: prefix di value option nentuin base_url/key asli
  let model = modelField ? modelField.value.trim() : "";
  let targetUrl = "";
  let targetKey = "";
  let modelType = 'chat';

  if (model.startsWith("[OpenAI] ")) {
      model = model.replace("[OpenAI] ", "");
      targetUrl = aiView.fields.hfUrl ? aiView.fields.hfUrl.value.trim() : "";
      targetKey = aiView.fields.hfKey ? aiView.fields.hfKey.value.trim() : "";
  } else if (model.startsWith("[Gemini] ")) {
      model = model.replace("[Gemini] ", "");
      targetUrl = aiView.fields.hmUrl ? aiView.fields.hmUrl.value.trim() : "";
      targetKey = aiView.fields.hmKey ? aiView.fields.hmKey.value.trim() : "";
  } else if (model.startsWith("[Custom1] ")) {
      model = model.replace("[Custom1] ", "");
      targetUrl = aiView.fields.cmUrl ? aiView.fields.cmUrl.value.trim() : "";
      targetKey = aiView.fields.cmKey ? aiView.fields.cmKey.value.trim() : "";
  } else if (model.startsWith("[Custom2] ")) {
      model = model.replace("[Custom2] ", "");
      targetUrl = aiView.fields.cpUrl ? aiView.fields.cpUrl.value.trim() : "";
      targetKey = aiView.fields.cpKey ? aiView.fields.cpKey.value.trim() : "";
  } else if (model.startsWith("[Local] ")) {
      model = model.replace("[Local] ", "");
      modelType = 'local';
      return { base_url: "", api_key: "", model, model_type: modelType };
  }

  // tentuin model_type berdasarkan nama model (pakai pola sama kayak isTTS/isSTT di validateAndLoad)
  const lower = model.toLowerCase();
  if (lower.includes('tts') || lower.endsWith('-tts')) modelType = 'tts';
  else if (lower.includes('whisper') || lower.includes('stt') || lower.endsWith('-audio')) modelType = 'stt';
  else modelType = 'chat';

  return { base_url: targetUrl, api_key: targetKey, model, model_type: modelType };
}

async function testModelReadiness(modelField, testBtn, statusSpan) {
  if (!modelField || !modelField.value || modelField.value.startsWith('Select Model')) {
      statusSpan.textContent = '❌ Pilih model dulu';
      statusSpan.style.color = 'var(--error)';
      return;
  }
  testBtn.disabled = true;
  testBtn.textContent = '...';
  statusSpan.textContent = 'Testing...';
  statusSpan.style.color = 'var(--text-muted)';

  try {
      const payload = resolveModelPayloadForTest(modelField);
      const res = await window.pywebview.api.test_model(payload.base_url, payload.api_key, payload.model, payload.model_type);
      if (res && res.status === 'ok') {
          statusSpan.textContent = '✅ Ready — ' + res.message;
          statusSpan.style.color = 'var(--success)';
      } else {
          statusSpan.textContent = '❌ Not ready — ' + (res ? res.message : 'Unknown error');
          statusSpan.style.color = 'var(--error)';
      }
  } catch (e) {
      statusSpan.textContent = '❌ Error: ' + e;
      statusSpan.style.color = 'var(--error)';
  }

  testBtn.disabled = false;
  testBtn.textContent = 'Test';
}

if (aiView.fields.hfModelTestBtn) {
  aiView.fields.hfModelTestBtn.addEventListener('click', () =>
    testModelReadiness(aiView.fields.hfModel, aiView.fields.hfModelTestBtn, aiView.fields.hfModelStatus));
}
if (aiView.fields.cmModelTestBtn) {
  aiView.fields.cmModelTestBtn.addEventListener('click', () =>
    testModelReadiness(aiView.fields.cmModel, aiView.fields.cmModelTestBtn, aiView.fields.cmModelStatus));
}
if (aiView.fields.hmModelTestBtn) {
  aiView.fields.hmModelTestBtn.addEventListener('click', () =>
    testModelReadiness(aiView.fields.hmModel, aiView.fields.hmModelTestBtn, aiView.fields.hmModelStatus));
}
if (aiView.fields.ytModelTestBtn) {
  aiView.fields.ytModelTestBtn.addEventListener('click', () =>
    testModelReadiness(aiView.fields.ytModel, aiView.fields.ytModelTestBtn, aiView.fields.ytModelStatus));
}
```

---

## PART E (kecil, boleh sekalian): stub `reload_whisper_model` nipu user

**Lokasi — `app.py` (~line 272-277):**
```python
def reload_whisper_model(self):
    """Reloads the local whisper model."""
    try:
        return {"status": "success", "message": "Whisper model will be reloaded on the next clip generation run."}
    except Exception as e:
        return {"status": "error", "message": str(e)}
```
Ini selalu return success apapun kondisinya, gak ngapa-ngapain beneran. Ganti message-nya jadi jujur, minimal cek dulu lib whisper ada:
```python
def reload_whisper_model(self):
    """Reloads the local whisper model."""
    try:
        import faster_whisper  # noqa
        return {"status": "success", "message": "Library whisper terdeteksi. Model akan dipakai ulang di run berikutnya."}
    except ImportError:
        return {"status": "error", "message": "Library whisper belum terinstall. Klik 'Install All' dulu."}
    except Exception as e:
        return {"status": "error", "message": str(e)}
```

---

## Acceptance Criteria
1. Tiap dropdown Select Model (Highlight Finder, Caption Maker, Hook Maker, YT Title Maker) punya tombol "Test" di sampingnya + status text di bawahnya.
2. Klik Test pada model chat yang key-nya valid → status jadi "✅ Ready" dalam <15 detik.
3. Klik Test pada model dengan key salah/base_url salah → status jadi "❌ Not ready" dengan pesan error yang jelas (bukan generic).
4. Klik Test pada model `[Local]` di Caption Maker → cek library whisper, bukan network call.
5. Field API key kosong yang sebelumnya nampilin "✓ (Other keys loaded)" hijau sekarang nampilin status abu-abu "ℹ Field ini kosong...".
6. Laporkan hasil test manual tiap poin di atas (boleh screenshot console/network tab).

## JANGAN
- Jangan ubah `getSmartPayload` yang asli di `web/app.js` (dipakai pas Save Settings) — `resolveModelPayloadForTest` itu function BARU yang terpisah, cuma logikanya mirip.
- Jangan bikin test model jadi blocking/nge-freeze UI (pastiin `testBtn.disabled` di-toggle dengan benar).
- Jangan hapus tombol "Test" yang lama di field API key (openai/gemini/custom1/custom2) — itu beda fungsi, biarkan tetap ada.
