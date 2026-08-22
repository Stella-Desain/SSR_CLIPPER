# BUG FIX ROUND 5 — AUTO-SAVE, BANNER, CAMPAIGN CARD BADGE

Root cause 3 bug ini sudah ketemu semua dari baca source code langsung. Eksekusi persis, jangan improvisasi.

## Aturan Wajib
- Prasyarat: BUG 1 di sini butuh fungsi `persistAiSettings()` yang seharusnya sudah dibikin dari instruksi round sebelumnya (BUGFIX_REPLIZ_DASHBOARD_V2.md, bagian BUG 1). Cek dulu fungsi itu ada di `web/app.js` — kalau belum ada, bikin dulu sesuai instruksi lama itu sebelum lanjut ke bug di bawah.
- Tiap fix WAJIB `git diff` + bukti test.

---

## BUG A — Settings page (API Configuration + Repliz) nggak auto-save

**Fix, tambahin di `web/app.js`, taruh SETELAH definisi function `persistAiSettings()`:**
```js
let aiAutoSaveTimeout = null;
aiView.element.addEventListener('input', (e) => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
    clearTimeout(aiAutoSaveTimeout);
    aiAutoSaveTimeout = setTimeout(() => { persistAiSettings(); }, 800);
  }
});
aiView.element.addEventListener('change', (e) => {
  if (e.target.tagName === 'SELECT' || e.target.type === 'checkbox' || e.target.type === 'radio') {
    persistAiSettings();
  }
});
```
Ini scoped ke `aiView.element` doang (satu section Settings), jadi nggak nyebar ke halaman lain. Jangan taruh di luar `aiView`.

---

## BUG B — Banner sudah diupload tapi nggak kesimpen/nggak muncul

**Root cause:** `upload_campaign_banner()` di `app.py` (baris 569-594) nyimpen path banner ke config dalam bentuk RELATIVE (`campaign_assets/{campaign_id}.ext`), tapi di frontend (`web/campaigns.js`, 3 tempat: baris 258-260, 424, 524-525) path itu langsung ditempel ke `file:///${bannerUrl}` — itu HARUS path absolute biar valid sebagai file URL. Karena path-nya relative, gambar gagal dimuat browser, KELIHATAN kayak "nggak kesimpen" padahal datanya sebenarnya sudah tersimpan bener di config, cuma gagal ditampilin.

**Fix — cukup 1 perubahan di `app.py`, fungsi `upload_campaign_banner` (baris 569-594):**

Cari baris ini (~582):
```python
            rel_path = f"campaign_assets/{campaign_id}{ext}"
```
Ganti jadi:
```python
            rel_path = str(dest_path)
```
Itu aja. Variabel `rel_path` tetap dipakai sama di 2 baris di bawahnya (`c["banner_path"] = rel_path` dan `return {"status": "ok", "banner_path": rel_path}`) — nggak perlu diubah, karena isinya sekarang jadi absolute path. Jangan ganti nama variabelnya, cukup isinya.

**Kenapa cukup satu baris:** 3 tempat di frontend yang render banner (`campaigns.js` baris 258, 424, 524) semuanya udah pakai pattern `file:///${path}` yang sama — begitu path yang disimpan di backend jadi absolute, otomatis ketiga tempat itu langsung bener tanpa disentuh sama sekali.

---

## BUG C — Badge "ACTIVE" di campaign card diganti icon trash (delete campaign)

**Lokasi:** `web/campaigns.js`, fungsi `refreshCampaignList`, baris 268-270:
```js
const status = document.createElement('span');
status.style.cssText = `font-size:12px;padding:4px 8px;border-radius:12px;align-self:flex-start;${c.status === 'active' ? 'background:#e6f4ea;color:#137333;' : 'background:#f1f3f4;color:#5f6368;'}`;
status.textContent = (c.status || 'active').toUpperCase();
```

**Ganti SELURUH 3 baris itu jadi:**
```js
const status = document.createElement('button');
status.title = 'Delete Campaign';
status.style.cssText = 'background:transparent;border:none;cursor:pointer;padding:4px;display:flex;align-items:center;align-self:flex-start;opacity:0.6;transition:opacity 150ms;';
status.onmouseover = () => status.style.opacity = '1';
status.onmouseout = () => status.style.opacity = '0.6';
status.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#EF4444" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4a1 1 0 011-1h4a1 1 0 011 1v2"/></svg>`;
status.addEventListener('click', async (e) => {
  e.stopPropagation();
  if (!confirm(`Hapus campaign "${c.name}"?`)) return;
  await window.pywebview.api.delete_campaign(c.id);
  refreshCampaignList();
});
```
SVG di atas persis sama kayak `ICON_TRASH` yang dipakai di `web/components/file-item.js` (baris 35) — konsisten sama icon delete yang udah ada di halaman Stock Clip. `e.stopPropagation()` WAJIB ada, karena card-nya sendiri punya click listener (`card.addEventListener('click', () => openCampaignEdit(c.id))`, baris ~320) yang bakal ke-trigger juga kalau nggak di-stop. Backend `delete_campaign(campaign_id)` sudah ada di `app.py` baris 562, tinggal dipanggil, nggak perlu bikin baru.

---

## FORMAT LAPORAN

| Bug | File | Diff sesuai instruksi? | Bukti test |
|---|---|---|---|
| A. Auto-save Settings | web/app.js | | |
| B. Banner tidak muncul | app.py | | |
| C. Badge Active → trash icon | web/campaigns.js | | |
