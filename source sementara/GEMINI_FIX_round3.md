# FIX INSTRUCTIONS — Round 3 (gabungan: sisa fix Campaign + 2 bug baru di Upload)

Backend & frontend Upload distribution (`GEMINI_INSTRUCTIONS_upload.md`) sudah
diverifikasi BENAR secara keseluruhan — jangan diubah kecuali disebut
eksplisit di bawah. Ini 3 fix kecil terakhir.

---

## 1. Bug: tombol "Stok"/"Upload" di card Campaign bikin halaman blank

`allViews` di `web/app.js` cuma berisi: `dashboardView, campaignListView,
campaignEditView, homeView, stockClipView, aiView` — dataset.view yang valid
untuk Stock Clip adalah **`'stock-clip'`**, BUKAN `'distribution'`. Tidak ada
view bernama `'distribution'` — dia cuma modal yang dipanggil lewat
`window.Components.DistributionPanel(...)` dari DALAM halaman Stock Clip.

`stockClipView` juga **sudah punya** fungsi `refresh(campaignId, autoSelectUnuploaded)`
yang otomatis filter clip ke campaign tertentu, dan kalau
`autoSelectUnuploaded=true` otomatis select semua clip belum-upload lalu buka
Distribution Panel. Tinggal disambungkan.

### Fix di `web/campaigns.js`

Ganti DUA tempat (di `refreshCampaignList()`, tombol card list, dan di
`openCampaignEdit()`, tombol banner card) yang isinya:

```js
stokBtn.addEventListener('click', (e) => {
  e.stopPropagation();
  setActiveView('distribution');
  // Set filter to this campaign in distribution if possible
});

uploadBtn.addEventListener('click', (e) => {
  e.stopPropagation();
  setActiveView('distribution');
  // Trigger upload flow for this campaign
});
```

Menjadi:

```js
stokBtn.addEventListener('click', (e) => {
  e.stopPropagation();
  setActiveView('stock-clip');
  stockClipView.refresh(c.id, false);
});

uploadBtn.addEventListener('click', (e) => {
  e.stopPropagation();
  setActiveView('stock-clip');
  stockClipView.refresh(c.id, true);
});
```

(`c.id` = id campaign yang relevan di scope masing-masing — di
`refreshCampaignList()` itu `c` dari `campaigns.forEach(c => ...)`, di
`openCampaignEdit()` gunakan `id` yang sedang dibuka. Sesuaikan nama variabel
sesuai scope masing-masing fungsi, jangan asal copy-paste kalau nama
variabelnya beda.)

---

## 2. Bug: `scheduled_uploads` selalu nyimpen `campaign_id` kosong

Di `app.py`, method `preview_distribution()`, setiap dict yang di-`append()`
ke `assignments` (baris ~1380-1388) tidak menyertakan `campaign_id`, padahal
`confirm_distribution()` mengharapkan `asn.get("campaign_id", "")`.

### Fix

Tambahkan `"campaign_id": campaign_id` ke dict assignment:

```python
assignments.append({
    "clip_id": clip["id"],
    "clip_title": clip["title"],
    "account_id": candidate["_id"],
    "account_name": candidate["name"],
    "platform": candidate.get("type", "repliz"),
    "scheduled_at": scheduled_dt.isoformat(),
    "clip_path": clip["path"],
    "campaign_id": campaign_id  # BARU — supaya konsisten sampai ke scheduled_uploads
})
```

`campaign_id` di titik ini sudah pasti terisi benar (hasil auto-detect atau
manual pilih di baris-baris sebelumnya di method yang sama).

---

## 3. Fix `browse_brief_file` (belum dikerjakan dari instruksi sebelumnya)

Ini masih outstanding dari fix round sebelumnya — tolong dikerjakan juga.

Di `app.py`, tambah method baru (jangan ubah `browse_watermark_image()`):

```python
def browse_brief_file(self):
    """File dialog khusus brief campaign — terima gambar & dokumen, tanpa copy ke watermarks."""
    import webview
    try:
        if not webview.windows:
            return None
        result = webview.windows[0].create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=False,
            file_types=('Brief Files (*.png;*.jpg;*.jpeg;*.webp;*.pdf;*.docx)',)
        )
        if result and len(result) > 0:
            return {"status": "ok", "path": result[0]}
        return {"status": "cancelled"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
```

Di `web/campaigns.js`, pada handler `campaignEditView.fields.docFile.parentElement`
(bagian upload dokumen brief untuk AI Quick-fill — SEKITAR baris ~536, yang
ada komentar "Reuse browse_watermark_image (but ideally needs a specific file
picker in python backend)"), ganti:

```js
const res = await window.pywebview.api.browse_watermark_image();
```

menjadi:

```js
const res = await window.pywebview.api.browse_brief_file();
```

**Khusus di handler ini saja** — handler upload banner tetap pakai
`browse_watermark_image()`, tidak diubah.

---

## Checklist verifikasi

- [ ] Klik "Stok" di card Campaign → pindah ke halaman Stock Clip, ter-filter
      ke clip campaign itu saja.
- [ ] Klik "Upload" di card Campaign → pindah ke Stock Clip ter-filter, semua
      clip "belum diupload" ke-select otomatis, Distribution Panel langsung
      terbuka.
- [ ] Setelah konfirmasi distribusi, cek `data.json` clip terkait —
      `scheduled_uploads[].campaign_id` terisi id campaign yang benar, bukan
      string kosong.
- [ ] "Upload Document" di AI Quick-fill sekarang bisa pilih `.pdf`/`.docx`,
      bukan cuma gambar.
