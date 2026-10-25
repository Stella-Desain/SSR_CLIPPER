# FIX 06 — `GEMINI_BASE_URL is not defined` (ReferenceError)

## Context
Repo: `https://github.com/Stella-Desain/clip-v2/tree/feature/pywebview-desktop-integration`

Ini kesalahan kamu sendiri dari FIX-05 kemarin. Instruksi FIX-05 minta kamu bikin constant `GEMINI_BASE_URL` DULU sebelum dipakai di 4 tempat. Kamu udah bener ganti semua PEMAKAIAN-nya (`getSmartPayload`, `providers` array, tombol Test Gemini, `resolveModelPayloadForTest`), tapi LUPA nulis baris DEKLARASI constant-nya. Akibatnya semua tombol Test di halaman Settings crash `ReferenceError: GEMINI_BASE_URL is not defined`.

Scope kamu **HANYA** file ini:
- `web/app.js`

---

## Fix

**Lokasi — paling atas file `web/app.js` (baris 1-8):**
```js
/* ═══════════════════════════════════════
   Clipper - App Shell
   ═══════════════════════════════════════ */

const root = document.getElementById('app');
```

**Ganti jadi (tambahkan 1 baris declare persis sebelum `const root = ...`):**
```js
/* ═══════════════════════════════════════
   Clipper - App Shell
   ═══════════════════════════════════════ */

const GEMINI_BASE_URL = 'https://generativelanguage.googleapis.com/v1beta/openai/';

const root = document.getElementById('app');
```

**JANGAN ubah apapun selain nambah 1 baris ini.** Semua kode yang MEMAKAI `GEMINI_BASE_URL` di file ini (4 tempat: line ~428, ~557, ~715, ~765 — nomornya mungkin geser sedikit karena nambah 1 baris di atas) sudah BENAR dari FIX-05, tidak perlu disentuh lagi.

---

## Acceptance Criteria
1. Jalankan `node --check web/app.js` — harus lolos tanpa error.
2. Cari di seluruh file: `grep -n "GEMINI_BASE_URL" web/app.js` — baris PERTAMA yang muncul harus baris DEKLARASI (`const GEMINI_BASE_URL = ...`), bukan salah satu tempat pemakaian.
3. Restart app, buka Settings, klik tombol Test di keempat field (Open AI, Gemini, Custom Provider 1, Custom Provider 2) — TIDAK BOLEH ada lagi error `ReferenceError: GEMINI_BASE_URL is not defined` di status manapun.
4. Field Gemini yang key-nya valid harus balik nampilin `Valid, <N> model loaded` (bukan error).
5. Laporkan hasil test manual poin 1-4.

## JANGAN
- Jangan ubah logic apapun selain nambah 1 baris deklarasi ini.
- Jangan ganti value URL-nya — harus persis `https://generativelanguage.googleapis.com/v1beta/openai/`, sama kayak yang udah dipakai di tempat lain.
