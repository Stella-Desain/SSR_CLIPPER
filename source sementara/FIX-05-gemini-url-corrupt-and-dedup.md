# FIX 05 — Gemini URL Ke-corrupt, Model Duplikat di Hook Maker, & Batasi Local Whisper

## Context
Repo: `https://github.com/Stella-Desain/clip-v2/tree/feature/pywebview-desktop-integration`

Scope kamu **HANYA** file ini:
- `web/app.js`

Jangan sentuh file lain.

---

## PART A (CRITICAL — bug fungsional, bukan cuma status text): `hmUrl` ke-corrupt jadi URL provider lain

**Root cause yang udah diverifikasi:** field tersembunyi `aiView.fields.hmUrl` (dibuat di `ai-settings.js` dengan value default `'https://generativelanguage.googleapis.com/v1beta/openai/'`) DITIMPA setiap kali settings di-load ulang, oleh baris ini di `web/app.js` (~line 913):

```js
if (aiView.fields.hmUrl) aiView.fields.hmUrl.value = (hm.base_url && hm.base_url !== 'https://api.openai.com/v1') ? hm.base_url : 'https://generativelanguage.googleapis.com/v1beta/openai/';
```

`hm.base_url` itu nilai TERAKHIR YANG DISIMPAN buat Hook Maker — dan itu berubah-ubah tergantung MODEL APA yang terakhir dipilih di dropdown Hook Maker (bisa model Gemini, bisa juga model dari Custom Provider 1/2, provider APAPUN). Kalau terakhir kali user pilih model non-Gemini di Hook Maker (misal `[Custom1] tts-1-hd`), maka `hm.base_url` yang ke-save adalah URL Custom1 — dan pas app di-reload, `hmUrl.value` jadi URL Custom1, BUKAN URL Gemini lagi.

Masalahnya, field `hmUrl` ini dipakai di 4 tempat berbeda buat ngambil "URL resmi Gemini", dan CUMA SATU dari 4 tempat itu yang pakai literal hardcoded (jadi konsisten), sisanya baca dari `hmUrl.value` yang bisa korup:

1. `validateAndLoad`'s `providers` array (~line 557) — pakai `aiView.fields.hmUrl` (BISA KORUP)
2. `getSmartPayload`'s Gemini branch (~line 426-428) — pakai `aiView.fields.hmUrl.value` (BISA KORUP)
3. `resolveModelPayloadForTest`'s Gemini branch (~line 761-763) — pakai `aiView.fields.hmUrl.value` (BISA KORUP)
4. Tombol Test Gemini punya `kind.url` literal hardcoded yang BENER (~line 714)

Karena #4 selalu bener tapi #1/#2/#3 bisa korup, klik Test di field "Gemini" bakal MISMATCH — dikira bukan provider yang sama (`isOwn = false`), makanya status jadi "Other keys loaded" walau key-nya valid. LEBIH PARAH: kalau user pilih model `[Gemini] ...` di dropdown Hook Maker terus klik tombol Test model (bukan test key), request BENERAN dikirim ke URL yang salah (karena #3 baca `hmUrl.value` yang korup) — generation Hook Maker beneran bisa gagal di production.

**Fix — ini WAJIB dikerjain di 4 titik biar konsisten semua:**

### 1. Tambah konstanta di paling atas `web/app.js` (sebelum baris `const root = document.getElementById('app');`):
```js
const GEMINI_BASE_URL = 'https://generativelanguage.googleapis.com/v1beta/openai/';
```

### 2. `validateAndLoad`, `providers` array (~line 557), ganti:
```js
{ name: 'Gemini', url: aiView.fields.hmUrl, key: aiView.fields.hmKey },
```
jadi:
```js
{ name: 'Gemini', url: { value: GEMINI_BASE_URL }, key: aiView.fields.hmKey },
```

### 3. `getSmartPayload`, cari block ini (~line 426-428):
```js
      } else if (model.startsWith("[Gemini] ")) {
          model = model.replace("[Gemini] ", "");
          targetUrl = aiView.fields.hmUrl ? aiView.fields.hmUrl.value.trim() : targetUrl;
          targetKey = aiView.fields.hmKey ? aiView.fields.hmKey.value.trim() : targetKey;
```
ganti jadi:
```js
      } else if (model.startsWith("[Gemini] ")) {
          model = model.replace("[Gemini] ", "");
          targetUrl = GEMINI_BASE_URL;
          targetKey = aiView.fields.hmKey ? aiView.fields.hmKey.value.trim() : targetKey;
```

### 4. `resolveModelPayloadForTest`, cari block ini (~line 761-763):
```js
  } else if (model.startsWith("[Gemini] ")) {
      model = model.replace("[Gemini] ", "");
      targetUrl = aiView.fields.hmUrl ? aiView.fields.hmUrl.value.trim() : "";
      targetKey = aiView.fields.hmKey ? aiView.fields.hmKey.value.trim() : "";
```
ganti jadi:
```js
  } else if (model.startsWith("[Gemini] ")) {
      model = model.replace("[Gemini] ", "");
      targetUrl = GEMINI_BASE_URL;
      targetKey = aiView.fields.hmKey ? aiView.fields.hmKey.value.trim() : "";
```

### 5. Tombol Test Gemini (`hmValidateBtn`, ~line 713-719), boleh sekalian dirapikan pakai konstanta yang sama (opsional tapi disaranin biar satu sumber kebenaran):
```js
aiView.fields.hmValidateBtn.addEventListener('click', () => validateAndLoad({
  url: { value: GEMINI_BASE_URL },
  key: aiView.fields.hmKey,
  modelSelect: aiView.fields.hmModel,
  homeSelect: homeView.fields.hookSub,
  status: aiView.fields.hmValidateStatus
}));
```

**Catatan:** JANGAN hapus/ubah field `aiView.fields.hmUrl` itu sendiri atau baris line 913/102 yang nulis ke situ — biarin aja, dia masih dipakai sebagai fallback buat model yang gak punya prefix dikenal. Yang penting SEMUA jalur khusus Gemini sekarang gak gantung ke field yang bisa korup itu lagi.

---

## PART B: Model tanpa prefix nongol di dropdown (defensive fix)

Owner nemu dropdown Hook Maker nampilin entry ganda: `[Custom1] tts-1-hd` DAN `tts-1-hd` polos tanpa prefix (juga `tts-1` polos). Setelah ditelusuri, gak ada kode yang SENGAJA nambahin entry tanpa prefix — kemungkinan besar ini SISA dari value lama yang ke-save sebelum sistem prefix `[Provider]` ini ada (tersimpan mentah tanpa bracket di `hm.model`), atau ada state browser yang belum ke-refresh bersih.

**Fix defensif (aman diterapkan terlepas dari akar masalah persisnya) — cuma boleh nampilin model yang punya prefix provider yang valid.**

**Lokasi — `web/app.js`, function `validateAndLoad`, tepat SETELAH block `for (const p of providers) { ... }` selesai (sebelum bagian `if (!apiKey) { ... }` status text), TAMBAHKAN baris ini:**

```js
      // Buang entry yang gak punya prefix provider valid (misal sisa data lama sebelum sistem prefix ada)
      const VALID_PREFIX_RE = /^\[(OpenAI|Gemini|Custom1|Custom2|Local)\]\s/;
      allModels = allModels.filter(m => VALID_PREFIX_RE.test(m));
```

Taruh persis sebelum baris `if (!apiKey) {`.

**PENTING — laporkan balik ke owner setelah fix ini:** karena Gemini (kamu) kemungkinan gak punya akses live ke provider Custom Provider 1 punya owner, kamu gak akan bisa reproduce bug ini 100% di environment kamu sendiri. Fix di atas itu DEFENSIF (aman & benar secara logika — model yang gak punya prefix jelas emang seharusnya gak ditampilkan), tapi kalau setelah dipasang owner masih lihat entry tanpa prefix pas dites langsung di app-nya, itu tandanya akar masalahnya beda dari dugaan kita dan perlu instrumentasi lebih lanjut (owner perlu buka DevTools console, klik Test, terus screenshot isi variable `allModels` SEBELUM di-filter). Tulis catatan ini di laporan akhir kamu.

---

## PART C: Batasi local whisper model di Caption Maker — cuma `large-v3-turbo` dan `medium`

Owner cuma mau 2 pilihan local model: `large-v3-turbo` dan `medium`. Sekarang ada 6 (`large-v3-turbo`, `large-v3`, `medium`, `small`, `base`, `tiny`).

**Lokasi 1 — `web/app.js`, `validateAndLoad` function (~line 563-568):**
```js
      allModels.push('[Local] large-v3-turbo');
      allModels.push('[Local] large-v3');
      allModels.push('[Local] medium');
      allModels.push('[Local] small');
      allModels.push('[Local] base');
      allModels.push('[Local] tiny');
```
Ganti jadi:
```js
      allModels.push('[Local] large-v3-turbo');
      allModels.push('[Local] medium');
```

**Lokasi 2 — `web/app.js`, dekat baris ~460, konsisten-kan array validasi ini juga:**
```js
  const localSizes = ['large-v3-turbo', 'large-v3', 'medium', 'small', 'base', 'tiny'];
```
Ganti jadi:
```js
  const localSizes = ['large-v3-turbo', 'medium'];
```

**Cek dulu (JANGAN diubah, cuma verifikasi):** file `web/components/ai-settings.js` bagian `whisperModelSelect` (dropdown pilihan buat DOWNLOAD/install model, di header kanan atas) — ini SUDAH cuma punya opsi `API`, `large-v3-turbo`, `medium` (udah bener dari awal, gak perlu diubah). Pastiin gak ada perubahan yang perlu di file itu.

---

## PART D: Sisa icon yang kelewatan dari fix status text-only sebelumnya

**Lokasi — `web/app.js`, function `validateAndLoad`, bagian paling akhir (catch block, ~line 671-674):**
```js
  } catch(e) {
      kind.status.textContent = '❌ Error: ' + e;
      kind.status.style.color = 'var(--error)';
  }
```
Ganti jadi text-only, konsisten sama format status lainnya:
```js
  } catch(e) {
      kind.status.textContent = 'Error: ' + e;
      kind.status.style.color = 'var(--error)';
  }
```

---

## Acceptance Criteria
1. Test model Gemini API key yang valid → status HARUS `Valid, <N> model loaded`, bukan lagi `Other keys loaded` — TERLEPAS dari model apa yang terakhir dipilih di Hook Maker sebelumnya.
2. Simulasikan: pilih model Custom1 di Hook Maker, save, reload app, BARU klik Test di field Gemini → tetep harus `Valid, <N> model loaded` (ini skenario yang sebelumnya bikin bug muncul).
3. Dropdown Hook Maker gak lagi nampilin entry tanpa prefix (`tts-1`, `tts-1-hd` polos) — semua entry harus punya format `[Provider] nama-model`.
4. Dropdown Caption Maker bagian `[Local]` cuma ada 2 opsi: `[Local] large-v3-turbo` dan `[Local] medium`.
5. Semua status text di seluruh field masih ikut format lama: `Empty`, `Valid, N model loaded`, `Error <kode>`, `Ready - Installed`, `Ready - API tested` — TANPA icon apapun.
6. Laporkan hasil test manual poin 1-5, dan WAJIB tulis apakah PART B (dedup filter) beneran ngilangin entry tanpa prefix pas dites di app owner, atau masih muncul (kalau masih muncul, ikuti instruksi "PENTING" di PART B).

## JANGAN
- Jangan hapus field `aiView.fields.hmUrl`, atau baris di line 102/913 yang nulis ke situ.
- Jangan ubah logic kategorisasi model (`isTTS`, `isSTT`, `isChat`, `GEMINI_AUDIO_MODELS`) dari fix sebelumnya.
- Jangan ubah `web/components/ai-settings.js` sama sekali di file ini — scope cuma `web/app.js`.
- Jangan sentuh backend (`app.py`) — bug ini murni di frontend.
