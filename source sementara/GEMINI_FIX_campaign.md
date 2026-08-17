# FIX INSTRUCTIONS — Campaign Feature (revisi hasil implementasi sebelumnya)

Ini BUKAN spec dari nol — ini daftar perbaikan atas kode yang sudah ada di
`web/components/campaign-edit.js`, `web/campaigns.js`, dan `app.py`. Backend
`app.py` (`get_campaigns`, `create_campaign`, `extract_campaign_brief`,
`get_campaign_stats`, `upload_campaign_banner`) sudah BENAR — **jangan ubah
apa pun di `app.py`** kecuali disebutkan eksplisit di §3 (bug status string).
Fokus perbaikan ada di frontend.

---

## 1. Bug kritis: argumen `extract_campaign_brief` tertukar

Di `web/campaigns.js`, semua pemanggilan `window.pywebview.api.extract_campaign_brief(...)`
salah urutan argumen. Backend butuh `(content_type, content)` di mana
`content_type` HARUS berupa string literal `"text"`, `"image"`, atau `"doc"`
— bukan isi teksnya.

**Ganti logic pemanggilannya jadi:**

```js
async function runExtraction({ text, filePath }) {
  campaignEditView.fields.extractBtn.disabled = true;
  campaignEditView.fields.extractBtn.textContent = 'Extracting...';
  try {
    let res;
    if (filePath) {
      const ext = filePath.split('.').pop().toLowerCase();
      if (['png', 'jpg', 'jpeg', 'webp'].includes(ext)) {
        // Baca file jadi base64 dulu lewat backend (bikin helper baru di app.py:
        // def read_file_as_base64(self, path): return base64.b64encode(open(path,'rb').read()).decode()
        const b64 = await window.pywebview.api.read_file_as_base64(filePath);
        res = await window.pywebview.api.extract_campaign_brief("image", b64);
      } else {
        // doc/docx/pdf — backend baca file langsung dari path
        res = await window.pywebview.api.extract_campaign_brief("doc", filePath);
      }
    } else {
      res = await window.pywebview.api.extract_campaign_brief("text", text);
    }
    applyExtractedBrief(res);
  } finally {
    campaignEditView.fields.extractBtn.disabled = false;
    campaignEditView.fields.extractBtn.textContent = 'Create brief';
  }
}
```

Tambahkan helper baru di `app.py`:
```python
def read_file_as_base64(self, path):
    import base64
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")
```

**Ganti semua pengecekan hasil** dari `res.status === 'success'` /
`res.brief` menjadi **`res.status === 'ok'`** / **`res.extracted`** (objek,
bukan string) — cocokkan dengan return value backend yang sebenarnya
(lihat `app.py` baris ~574: `return {"status": "ok", "extracted": json.loads(raw)}`).

## 2. Bug: status banner upload

Di `campaigns.js`, ganti `if (upRes && upRes.status === 'success')` menjadi
**`if (upRes && upRes.status === 'ok')`** — backend `upload_campaign_banner`
return `"status": "ok"`, bukan `"success"` (`app.py` baris ~510).

## 3. Bug: field stats salah nama

Di `campaigns.js` (fungsi `refreshCampaignList` dan `openCampaignEdit`),
ganti `stats.videos_count` / `stats.clips_count` menjadi
**`stats.account_count`** / **`stats.clip_in_stock`** (dan `stats.clip_uploaded`
kalau perlu ditampilkan terpisah) — sesuai return `get_campaign_stats()` yang
sebenarnya (`app.py` baris ~594).

---

## 4. Rebuild `campaign-edit.js` — form 2 kolom lengkap

Struktur `grid-template-columns:1.3fr 1fr` yang sudah ada **dipertahankan**,
tapi ISI kedua kolom perlu dilengkapi. Field baru semua opsional (boleh
kosong saat create).

### Kolom kiri — tambahkan setelah `nameInput` (durasi s/d persona langsung
di card yang sama, atau card baru — bebas asal masih di kolom kiri):

- `durasiMinInput` + `durasiMaxInput` (2 number input kecil, default 15/180)
- `hashtagsInput` (tag/chip input — Enter untuk nambah chip, simpan sebagai array)
- `taggedAccountsInput` (text input, comma-separated, simpan sebagai array)
- `hooksList` (container + tombol "+ tambah hook": tiap klik nambah 1
  `<textarea>` baru ke list, simpan value semuanya sebagai array saat save)
- `catatanArea` (textarea bebas — field `context` yang sudah ada BOLEH
  di-reuse buat ini, jangan bikin field duplikat)
- `anglesInput` (chip input sama seperti hashtags)
- `personaArea` (textarea)
- `tujuanInput` (text input)
- `ctaInput` (text input)

Field `hookArea` (readonly, AI output) yang sudah ada: **hapus** —
diganti populate langsung ke field-field di atas lewat `applyExtractedBrief()`
(§5), bukan didump jadi 1 blok teks.

Tambahkan card baru "Aturan dan larangan" di bawah card brief (masih kolom
kiri):
- **Do** list + **Don't** list — masing-masing container + tombol
  "+ tambah", tiap item = 1 baris teks dengan tombol hapus (×). Simpan
  sebagai `do_rules[]` / `dont_rules[]`.
- **Aturan umum** — list `{title, description}`: tombol "+ tambah aturan"
  nambah 2 input (title + description) sekaligus per item. Simpan sebagai
  `aturan_umum[]`.

Tambahkan **account picker** (boleh di card brief atau card terpisah, masih
kolom kiri): checklist dari `get_repliz_accounts()`, tiap item checkbox +
nama akun + icon platform, tampilkan counter "N/{total} akun dipilih" di
header-nya. Simpan id yang tercentang sebagai `account_ids[]`.

### Kolom kanan:

- **Banner**: ganti `aspect-ratio:16/9` (baris ~113) jadi
  **`aspect-ratio:3/2`**. Di bawah banner (bukan di `statsDiv` yang sekarang
  minim), tampilkan `"{account_count} akun terhubung"` dan
  `"{clip_uploaded} clip diupload · {clip_in_stock} di stok"`, lalu 2 tombol
  **"Stok"** dan **"Upload"** (behaviour sama seperti §5 di
  `GEMINI_INSTRUCTIONS_campaign.md` — navigasi ke Stock Clip ter-filter).
- **AI quick-fill card** (bg hijau muda, border dashed) — pindahkan
  `contextArea` (textarea paste teks) + `docFile` (drop/upload dokumen &
  gambar, ubah `accept` jadi `.txt,.pdf,.docx,.png,.jpg,.jpeg`) + tombol
  "Create brief" (rename dari "Extract AI Brief") ke sini, styling
  `background:#F2FCE2; border:1px dashed #8DC63F;` sesuai wireframe yang
  sudah di-ACC.

### `applyExtractedBrief(res)` — BARU

```js
function applyExtractedBrief(res) {
  if (!res || res.status !== 'ok') {
    alert('Ekstraksi gagal: ' + (res ? res.message : 'unknown error'));
    return;
  }
  const d = res.extracted;
  const f = campaignEditView.fields;
  if (d.name) f.nameInput.value = d.name;
  const b = d.brief || {};
  f.durasiMinInput.value = b.durasi_min || 15;
  f.durasiMaxInput.value = b.durasi_max || 180;
  setChips(f.hashtagsInput, b.hashtags || []);
  f.taggedAccountsInput.value = (b.tagged_accounts || []).join(', ');
  setHooksList(f.hooksList, b.hooks || []);
  f.catatanArea.value = b.catatan || '';
  setChips(f.anglesInput, b.angles || []);
  f.personaArea.value = b.persona || '';
  f.tujuanInput.value = b.tujuan || '';
  f.ctaInput.value = b.cta || '';
  setRuleList(f.doRulesList, d.do_rules || []);
  setRuleList(f.dontRulesList, d.dont_rules || []);
  setAturanUmumList(f.aturanUmumList, d.aturan_umum || []);
  // User tetap review manual sebelum klik "Simpan campaign" — TIDAK auto-save di sini.
}
```//
(`setChips`/`setHooksList`/`setRuleList`/`setAturanUmumList` — helper render
list ke DOM, implementasi bebas asal konsisten dengan struktur field di atas.)

---

## 5. Fix `saveCampaign()` — kirim payload lengkap

Ganti payload yang sekarang cuma `{name, status, context, extracted_hook}`
menjadi:

```js
const data = {
  name: fields.nameInput.value.trim(),
  status: fields.statusSelect.value,
  account_ids: getCheckedAccountIds(),
  brief: {
    durasi_min: parseInt(fields.durasiMinInput.value) || 15,
    durasi_max: parseInt(fields.durasiMaxInput.value) || 180,
    hashtags: getChipValues(fields.hashtagsInput),
    tagged_accounts: fields.taggedAccountsInput.value.split(',').map(s => s.trim()).filter(Boolean),
    hooks: getHooksListValues(fields.hooksList),
    catatan: fields.catatanArea.value.trim(),
    angles: getChipValues(fields.anglesInput),
    persona: fields.personaArea.value.trim(),
    tujuan: fields.tujuanInput.value.trim(),
    cta: fields.ctaInput.value.trim()
  },
  do_rules: getRuleListValues(fields.doRulesList),
  dont_rules: getRuleListValues(fields.dontRulesList),
  aturan_umum: getAturanUmumValues(fields.aturanUmumList)
};
```

`create_campaign`/`update_campaign` di backend TIDAK perlu diubah — dia
sudah `dict(payload)` apa adanya, jadi otomatis nyimpen struktur baru ini.

---

## 6. Fix card di `campaigns.js` (`refreshCampaignList`)

- Ganti banner strip `height:80px` jadi container `aspect-ratio:3/2` yang
  proper (banner full-width di atas card, bukan overlay opacity 0.6 di
  belakang teks).
- **Tambahkan 2 tombol** di bagian bawah tiap card: **"Stok"** (outline) dan
  **"Upload"** (lime, `#8DC63F`) — event listener terpisah dari klik card
  (pakai `e.stopPropagation()` di tombol supaya tidak ikut trigger
  `openCampaignEdit`). Card boleh tetap clickable untuk buka edit, tapi 2
  tombol ini WAJIB ada dan navigasi ke Stock Clip ter-filter
  `campaign_id` (detail behavior "Upload" langsung buka Distribution Panel
  ada di `GEMINI_INSTRUCTIONS_upload.md`, yang penting di sini navigasinya
  benar & filter ke-set).
- Ganti string stats jadi `` `${stats.account_count} akun · ${stats.clip_in_stock} clip` ``.

---

## 7. Checklist verifikasi setelah fix

- [ ] Tempel teks brief contoh (isi CSV/gambar yang dikasih user) → "Create
      brief" → field durasi/hashtag/hook/angle/persona/cta/Do/Don't/Aturan
      Umum di kolom kiri terisi sesuai, BUKAN dump 1 blok teks.
- [ ] Upload gambar screenshot brief → hasil sama seperti di atas.
- [ ] Centang beberapa akun → simpan → `get_campaigns()` return campaign
      dengan `account_ids` terisi benar.
- [ ] Banner ke-upload, tampil di preview (status check sudah benar, bukan
      selalu "Upload failed").
- [ ] Card di halaman Campaign List: banner 3:2, ada tombol "Stok" & "Upload"
      terpisah, angka stat bukan selalu "0".
