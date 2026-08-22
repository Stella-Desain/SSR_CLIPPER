# BUG FIX — REPLIZ & DASHBOARD (Instruksi Eksekusi Persis)

Semua root cause sudah ketemu dari baca source code langsung. Kamu TINGGAL EKSEKUSI perubahan di bawah, per file per baris. Jangan improvisasi logic sendiri di luar yang ditulis di sini.

## Aturan Wajib
- Kerjain BUG 1 duluan, baru BUG 3 & 4 (mereka bergantung ke fix BUG 1).
- Tiap selesai satu bug: `git diff` buat file itu aja, cocokkan sama instruksi di bawah persis.
- JANGAN ubah baris/file yang nggak disebut di sini.

---

## BUG 1 — `web/app.js`: Repliz "Connected" tapi "Failed to load accounts"

**Root cause:** Fungsi `test_repliz_connection()` (dipanggil di `web/app.js` sekitar baris 1001) ngetes VALUE YANG DIKETIK USER LANGSUNG DI INPUT FIELD (`ak`, `sk` dari baris 996-997). Tapi `loadReplizData()` yang dipanggil setelahnya (baris 1005) manggil `get_account_stats()`/`get_repliz_accounts()` di `app.py`, yang baca key dari CONFIG YANG UDAH TERSIMPAN DI DISK (lewat `self._get_cfg()`), bukan dari input field. Kalau user belum klik tombol Save, config di disk masih key lama/kosong → gagal load.

**Perubahan di `web/app.js`:**

1. Cari blok ini (mulai baris 493):
```js
aiView.fields.saveBtn.addEventListener('click', async () => {
  // ...seluruh isi function...
});
```
Ubah jadi named function, bukan anonymous — ganti baris 493 dari:
```js
aiView.fields.saveBtn.addEventListener('click', async () => {
```
menjadi:
```js
async function persistAiSettings() {
```
Lalu di baris paling akhir dari function itu (baris penutup `});` yang nutup `addEventListener`), ganti jadi cuma `}` (nutup function biasa). Setelah itu, TAMBAHIN baris baru persis di bawahnya:
```js
aiView.fields.saveBtn.addEventListener('click', persistAiSettings);
```

2. Cari blok Test Connection (sekitar baris 1001-1005):
```js
const res = await window.pywebview.api.test_repliz_connection(ak, sk);
if (res.status === 'success') {
    aiView.fields.replizStatus.textContent = '✓ Connected successfully';
    aiView.fields.replizStatus.style.color = 'var(--success)';
    loadReplizData();
```
Tambahin `await persistAiSettings();` SEBELUM `loadReplizData();`, jadi:
```js
const res = await window.pywebview.api.test_repliz_connection(ak, sk);
if (res.status === 'success') {
    aiView.fields.replizStatus.textContent = '✓ Connected successfully';
    aiView.fields.replizStatus.style.color = 'var(--success)';
    await persistAiSettings();
    loadReplizData();
```

**Hasil yang diharapkan:** Test Connection sukses → settings otomatis ke-save ke disk → `loadReplizData()` baca config yang udah fresh → akun kebaca.

---

## BUG 2 — `web/components/campaign-edit.js`: upload banner buka 2 window file explorer

**Root cause:** Ada 2 click listener numpuk di elemen `bannerPreview`. Satu di `campaign-edit.js` baris 249 (buka `<input type=file>` browser), satu lagi di `web/campaigns.js` baris 513 (buka native file dialog Python lewat `browse_watermark_image()`). Dua-duanya kepicu bareng tiap sekali klik.

**Perubahan di `web/components/campaign-edit.js`:**

HAPUS baris ini (sekitar baris 249):
```js
bannerPreview.addEventListener('click', () => bannerInput.click());
```
Cukup dihapus, jangan diganti apapun. `bannerInput` (elemen `<input type=file>` yang dibikin baris 244-247) tetap boleh ada di kode, biarin aja — dia sudah nggak dipakai lagi, dan `web/campaigns.js` baris 537-538 memang sudah nge-remove elemen ini dari DOM.

**Hasil yang diharapkan:** Klik banner cuma munculin 1 dialog (dari `campaigns.js` — native picker via `browse_watermark_image()`).

---

## BUG 3 — `web/components/dashboard.js`: "undefined Campaign", harusnya jumlah campaign

**Root cause:** Baris 284 pakai `accStats.campaigns` — field ini isinya JUMLAH TOTAL AKUN REPLIZ (dari `app.py` fungsi `get_account_stats()` baris 466, `"campaigns": total` — nama field-nya menyesatkan, isinya akun bukan campaign), BUKAN jumlah campaign aplikasi ini. Selain itu, kalau `get_account_stats()` gagal (misal karena BUG 1 belum kefix), dia balikin `{"error": true, "message": ...}` yang nggak punya field `campaigns` — jadi `accStats.campaigns` = `undefined`, ke-render jadi teks "undefined Campaign".

**Perubahan di `web/components/dashboard.js`:**

1. Cari blok "Load Campaigns Tree" (sekitar baris 296-298):
```js
      // Load Campaigns Tree
      let campaigns = [];
      try { campaigns = await window.pywebview.api.get_campaigns(); } catch(e) {}
```
PINDAHIN 3 baris ini ke ATAS, taruh SEBELUM baris `// Load Account Stats` (sekitar baris 280), jadi urutannya: fetch campaigns dulu, baru account stats. Hapus 3 baris ini dari posisi lamanya (296-298).

2. Cari blok Account Stats (sekitar baris 280-294):
```js
      // Load Account Stats
      const accStats = await window.pywebview.api.get_account_stats();
      if (accStats) {
        const campCountEl = section.querySelector('#dash-campaigns-count');
        if (campCountEl) campCountEl.textContent = accStats.campaigns + ' Campaign';
        
        const tikCountEl = section.querySelector('#dash-tiktok-count');
        if (tikCountEl) tikCountEl.textContent = accStats.tiktok_count;
        
        const ytCountEl = section.querySelector('#dash-youtube-count');
        if (ytCountEl) ytCountEl.textContent = accStats.youtube_count;

        const igCountEl = section.querySelector('#dash-instagram-count');
        if (igCountEl) igCountEl.textContent = accStats.instagram_count;
      }
```
Ganti SELURUH blok itu jadi:
```js
      // Load Account Stats
      const campCountEl = section.querySelector('#dash-campaigns-count');
      if (campCountEl) campCountEl.textContent = campaigns.length + ' Campaign';

      const accStats = await window.pywebview.api.get_account_stats();
      const tikCountEl = section.querySelector('#dash-tiktok-count');
      const ytCountEl = section.querySelector('#dash-youtube-count');
      const igCountEl = section.querySelector('#dash-instagram-count');
      if (accStats && !accStats.error) {
        if (tikCountEl) tikCountEl.textContent = accStats.tiktok_count;
        if (ytCountEl) ytCountEl.textContent = accStats.youtube_count;
        if (igCountEl) igCountEl.textContent = accStats.instagram_count;
      } else {
        if (tikCountEl) tikCountEl.textContent = '0';
        if (ytCountEl) ytCountEl.textContent = '0';
        if (igCountEl) igCountEl.textContent = '0';
      }
```

Catatan: variabel `campaigns` yang dipakai di blok ini adalah yang udah dipindah ke atas di langkah 1 — pastikan urutannya bener (fetch campaigns dulu, baru pakai `campaigns.length` di sini).

---

## BUG 4 — Icon TikTok/YouTube/Instagram macet di angka "12"

**Root cause sama kayak BUG 3** — sudah kebenerin sama perubahan di BUG 3 langkah 2 (sekarang ada fallback `'0'` kalau `accStats.error`, dan angka asli kepasang kalau sukses). Logic hitung per-platform di backend (`app.py`, fungsi `get_account_stats()` baris 462-464) UDAH BENAR — dia beneran hitung dari data akun Repliz asli, nggak perlu diubah. Nggak ada perubahan tambahan di luar yang udah dilakuin di BUG 3.

**Hasil yang diharapkan:** setelah BUG 1 & 3 kefix, angka TikTok/YouTube/Instagram bakal nunjukin jumlah akun real per platform (bukan "12" statis lagi).

---

## BUG 5 — `app.py`: tombol "Repliz Dashboard" salah URL

**Perubahan di `app.py`, fungsi `get_repliz_dashboard_url` (baris 431-433):**

Dari:
```python
    def get_repliz_dashboard_url(self):
        """Returns the URL for Repliz Dashboard."""
        return "https://dashboard.repliz.com"
```
Jadi:
```python
    def get_repliz_dashboard_url(self):
        """Returns the URL for Repliz Dashboard."""
        return "https://repliz.com/user/dashboard"
```

---

## FORMAT LAPORAN

| Bug | File | Diff sesuai instruksi? | Bukti test |
|---|---|---|---|
| 1 | web/app.js | | |
| 2 | web/components/campaign-edit.js | | |
| 3 | web/components/dashboard.js | | |
| 4 | (sama seperti #3) | | |
| 5 | app.py | | |
