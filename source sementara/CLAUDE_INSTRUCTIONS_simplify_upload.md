# INSTRUKSI IMPLEMENTASI — Simplifikasi Upload Flow (SSR_CLIPPER)

**Repo:** https://github.com/Stella-Desain/SSR_CLIPPER
**Target pengerjaan:** kamu, sebagai coding assistant di dalam IDE, di repo ini juga (jangan buat repo/project baru).
**Stack:** Python (`pywebview`) di backend (`app.py`), vanilla JS tanpa framework/build-step di frontend (`web/*.js`, dipanggil langsung via `<script>` di `web/index.html`). **Jangan** memperkenalkan React/build tool/npm package baru — ikuti pola yang sudah ada (`document.createElement`, inline `style.cssText`, `window.Components.X`, `window.pywebview.api.xxx()`).

Sebelum mengubah apa pun: **buka & baca ulang tiap file yang disebut di bawah**, karena baris kode bisa saja sudah bergeser dari referensi di dokumen ini. Cari berdasarkan nama fungsi/selector/id yang disebut, bukan cuma nomor baris.

---

## 0. Fakta penting dari source code (sudah dicek, jangan cek ulang dari nol)

1. Panel "Clips" di screenshot = `web/components/stock-clip.js` (bagian `clipsPanel`). Row tiap clip dirender oleh `window.FileItem.v3` di `web/components/file-item.js`.
2. Tombol **"Distribusikan & upload"** di atas (`#distribute-btn`) membuka modal `window.Components.DistributionPanel` (`web/components/distribution-panel.js`) — modal ini punya 3 langkah manual: pilih campaign dari dropdown, isi input "maks clip per hari", lihat preview, baru klik "Konfirmasi & jadwalkan". Ini sumber "kebanyakan step".
3. Tiap row clip punya tombol **"Upload"** sendiri (`fi-btn-upload` di `file-item.js` v3) yang pakai `prompt()`/`confirm()` browser native, lalu langsung panggil `window.pywebview.api.upload_clip()` — jalur ini **beda total** dari jalur Distribution Panel (tidak lewat campaign, tidak lewat scheduler, tidak ada caption/hashtag). Ini sumber "kebanyakan tombol untuk fungsi sama".
4. Footer bawah (`actionBar`, id `#action-bar-text` + `#action-bar-btn`) di `stock-clip.js` adalah **duplikat 1:1** dari header (`#distribute-btn`) — cuma style beda (sticky bottom bar). Ini yang harus dihapus sesuai instruksi user.
5. `#stock-status-filter` (dropdown "Semua Status") murni filter client-side, **tidak perlu diubah**.
6. Backend punya 2 fungsi inti yang **JANGAN diubah signature-nya** (dipakai scheduler background `_upload_scheduler` tiap 60 detik):
   - `preview_distribution(clip_ids, campaign_id=None, max_per_account_per_day=2)` — auto-detect campaign kalau `campaign_id=None` dan semua clip 1 campaign yang sama; return `status: "mixed_or_missing_campaign"` kalau campaign beda-beda/kosong.
   - `confirm_distribution(assignments)` — tulis `scheduled_uploads[]` ke `data.json` tiap clip, set `upload_status: "terjadwal"`.
   - `upload_clip(clip_path, platform, options)` — **synchronous & blocking**, dipanggil scheduler saat `scheduled_at` sudah lewat.
7. **Gap yang sudah ada dan wajib ikut diperbaiki** (bukan scope-creep — ini penyebab caption/hashtag campaign TIDAK PERNAH kepakai saat upload):
   - `_upload_scheduler()` (baris ~1613 `app.py`) cuma kirim `{"title": ..., "account_id": ...}` ke `upload_clip()` — **tidak ada `description`**. Jadi hashtag/CTA campaign selama ini percuma, tidak pernah sampai ke sosmed.
   - Campaign (`web/components/campaign-edit.js` + `web/campaigns.js`, struktur `data.brief{...}`) **belum punya field "max clip per hari"** — nilai itu selama ini cuma input manual di modal Distribution Panel, default `2`.
8. Struktur `data.brief` campaign yang sudah ada (lihat `saveCampaign()` di `web/campaigns.js` baris ~452-471): `durasi_min, durasi_max, hashtags[], tagged_accounts[], hooks[], catatan, angles[], persona, tujuan, cta`.
9. Judul clip disimpan di `data.json` per-clip sebagai `hook_text` (format baru) atau `title` (format lama) — dibaca di `get_stock_clips()` (`app.py` ~1130-1163). Belum ada cara edit dari UI.

---

## 1. Tujuan akhir (behavior spec — ini yang WAJIB tercapai)

**Header panel Clips** cuma berisi 2 kontrol:
- Dropdown status = filter saja (sudah benar, tidak diubah).
- 1 tombol, logic:
  - Tidak ada clip yang dicentang → teks tombol **"Upload Semua"**. Klik = upload semua clip di list yang sedang tampil (sesuai filter aktif) yang statusnya `belum_diupload`. Kalau tidak ada clip berstatus itu, tombol disabled.
  - Ada ≥1 clip dicentang → teks tombol otomatis berubah **"Upload (N)"** (N = jumlah dicentang). Klik = upload cuma clip yang dicentang, terlepas dari status filter-nya.
  - **1x klik = langsung terupload/terjadwal.** Tidak ada modal, tidak ada dropdown pilih campaign manual, tidak ada input angka manual. Semua metadata (judul, caption, hashtag, maks clip/hari) diambil otomatis dari campaign yang sudah terpasang di clip/folder project itu.

**Row per-clip**: hapus tombol "Upload" individual (source #3). Sisakan Play + Delete. Selection tetap lewat checkbox → memicu tombol header di atas.

**Edit judul inline**: double-click di teks judul → jadi text input siap edit di tempat. Enter/blur = simpan otomatis ke `data.json` (tidak ada tombol "Save" terpisah). Escape = batal.

**Footer bawah**: hapus total — elemen `actionBar` (teks "X clip dipilih" + tombol duplikat) dihapus dari DOM sepenuhnya. Info "Clips: 7 · Size: 0.7 GB" di **subheader atas** (bukan footer) tetap ada, tidak disentuh.

---

## 2. Scope

**Dikerjakan:**
- `web/components/stock-clip.js` — rombak header button jadi 1 tombol dinamis, hapus action bar footer, ganti semua pemicu upload (termasuk dari `campaign-edit.js` → "Upload" button → `refresh(id, true)`) supaya lewat jalur baru.
- `web/components/file-item.js` (fungsi `v3`) — hapus tombol Upload, tambah edit-judul-inline via dblclick.
- `web/components/campaign-edit.js` + `web/campaigns.js` — tambah field "Maks Clip per Akun / Hari" di form campaign.
- `app.py` — fungsi baru `quick_upload(clip_ids)`, fungsi baru `update_clip_title(clip_path, new_title)`, tambah komposisi caption di `confirm_distribution`, tambah `description` di `_upload_scheduler`.
- `web/components/distribution-panel.js` + `web/index.html` — file & `<script>` tag dihapus (sudah tidak dipanggil dari mana pun setelah perubahan ini).

**TIDAK dikerjakan (jangan disentuh):**
- Logic inti `preview_distribution` / `confirm_distribution` (signature & algoritma distribusi antar akun) — dipanggil ulang, bukan ditulis ulang.
- `upload_clip()`, `tiktok_uploader.py`, `youtube_uploader.py`, `_upload_scheduler` loop utamanya (cuma tambah 1 key `description` di dict `options`).
- Halaman Campaign List, AI Quick-fill Brief, banner upload — tidak berkaitan dengan flow ini.

---

## 3. Perubahan detail per file

### 3.1 `app.py` — backend

**a) Fungsi baru `quick_upload`** (taruh dekat `preview_distribution`/`confirm_distribution`):

```python
def quick_upload(self, clip_ids):
    """Upload/jadwalkan clip langsung tanpa modal — auto-resolve campaign per clip,
    auto-split kalau clip yang dipilih berasal dari campaign berbeda-beda."""
    if not clip_ids:
        return {"status": "error", "message": "Tidak ada clip dipilih"}

    from collections import defaultdict
    all_clips = self.get_stock_clips()
    selected = [c for c in all_clips if c["id"] in clip_ids]
    if not selected:
        return {"status": "error", "message": "Clip tidak ditemukan"}

    groups = defaultdict(list)
    for c in selected:
        groups[c.get("campaign_id") or "default"].append(c["id"])

    cfg = self._get_cfg()
    campaigns_by_id = {c["id"]: c for c in cfg.get("campaigns", [])}

    total_scheduled = 0
    results = []
    for camp_id, ids in groups.items():
        max_per_day = 2
        camp = campaigns_by_id.get(camp_id)
        if camp:
            max_per_day = camp.get("brief", {}).get("max_clips_per_day", 2)

        preview = self.preview_distribution(ids, camp_id if camp_id != "default" else None, max_per_day)
        if preview.get("status") != "ok":
            results.append({"campaign_id": camp_id, "status": preview.get("status"), "message": preview.get("message")})
            continue

        confirm = self.confirm_distribution(preview["assignments"])
        scheduled_count = len(preview["assignments"])
        total_scheduled += scheduled_count
        results.append({
            "campaign_id": preview.get("campaign_id"),
            "campaign_name": preview.get("campaign_name"),
            "scheduled": scheduled_count
        })

    if total_scheduled == 0:
        return {"status": "error", "message": "Tidak ada clip yang berhasil dijadwalkan", "results": results}

    return {"status": "ok", "total_scheduled": total_scheduled, "results": results}
```

Catatan: karena tiap `ids` di dalam loop sudah pasti 1 campaign yang sama, panggilan `preview_distribution(ids, camp_id, ...)` tidak akan pernah kena cabang `mixed_or_missing_campaign` — jadi tidak perlu UI tambahan untuk kasus itu.

**b) Fungsi baru `update_clip_title`** (taruh dekat `delete_clip`):

```python
def update_clip_title(self, clip_path, new_title):
    """Update judul clip (hook_text / title) dan simpan langsung ke data.json-nya."""
    try:
        new_title = (new_title or "").strip()
        if not new_title:
            return {"status": "error", "message": "Judul tidak boleh kosong"}

        p = Path(clip_path)
        data_json_path = p.parent / "data.json"
        if not data_json_path.exists():
            return {"status": "error", "message": "data.json tidak ditemukan"}

        with open(data_json_path, 'r', encoding='utf-8') as f:
            cdata = json.load(f)

        if "hook_text" in cdata:
            cdata["hook_text"] = new_title
        else:
            cdata["title"] = new_title

        with open(data_json_path, 'w', encoding='utf-8') as f:
            json.dump(cdata, f, indent=2, ensure_ascii=False)

        return {"status": "ok", "title": new_title}
    except Exception as e:
        return {"status": "error", "message": str(e)}
```

**c) Tambah komposisi caption di `confirm_distribution`** — sisipkan helper, lalu simpan hasilnya sebagai key `"caption"` di tiap entry `scheduled_uploads` yang sudah ada (jangan hapus key lain yang sudah ada: `id, campaign_id, account_id, platform, scheduled_at, status, attempted_at, error_message`):

```python
def _build_caption(self, campaign_id):
    if not campaign_id or campaign_id == "default":
        return ""
    cfg = self._get_cfg()
    camp = next((c for c in cfg.get("campaigns", []) if c.get("id") == campaign_id), None)
    if not camp:
        return ""
    brief = camp.get("brief", {})
    parts = []
    if brief.get("cta"):
        parts.append(brief["cta"].strip())
    if brief.get("tagged_accounts"):
        parts.append(" ".join(brief["tagged_accounts"]))
    if brief.get("hashtags"):
        parts.append(" ".join(brief["hashtags"]))
    return "\n\n".join(p for p in parts if p)
```

Di dalam loop `confirm_distribution`, sebelum `cdata["scheduled_uploads"].append({...})`, tambahkan:
```python
caption = self._build_caption(asn.get("campaign_id"))
```
lalu tambahkan `"caption": caption` ke dict yang di-append.

**d) `_upload_scheduler`** — ubah dict `options` (baris sekitar 1613) dari:
```python
options = {
    "title": clip["title"],
    "account_id": entry.get("account_id")
}
```
menjadi:
```python
options = {
    "title": clip["title"],
    "description": entry.get("caption", ""),
    "account_id": entry.get("account_id")
}
```

### 3.2 `web/components/file-item.js` — fungsi `v3`

- **Hapus** parameter `onUpload` dan tombol `<button class="fi-btn-upload">...` dari `innerHTML` beserta baris `if (onUpload) el.querySelector('.fi-btn-upload')...`.
- **Tambah** parameter `onTitleChange` di signature `v3({ title, info1, info2, onDelete, onPlay, onTitleChange } = {})`.
- Setelah `el.innerHTML = ...`, ambil `const titleEl = el.querySelector('.fi-title');` lalu pasang double-click-to-edit:

```js
titleEl.style.cursor = 'text';
titleEl.title = 'Double-click untuk edit judul';
titleEl.addEventListener('dblclick', () => {
  const currentText = titleEl.textContent;
  const input = document.createElement('input');
  input.type = 'text';
  input.value = currentText;
  input.style.cssText = 'font-size:14px;font-weight:600;color:#111827;width:100%;border:1px solid #8DC63F;border-radius:4px;padding:2px 6px;outline:none;box-sizing:border-box;font-family:inherit;';
  titleEl.replaceWith(input);
  input.focus();
  input.select();

  let committed = false;
  const commit = async () => {
    if (committed) return;
    committed = true;
    const newVal = input.value.trim();
    if (!newVal || newVal === currentText) {
      input.replaceWith(titleEl);
      return;
    }
    titleEl.textContent = newVal;
    input.replaceWith(titleEl);
    if (onTitleChange) await onTitleChange(newVal, currentText);
  };
  input.addEventListener('blur', commit);
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') input.blur();
    if (e.key === 'Escape') { input.value = currentText; committed = true; input.replaceWith(titleEl); }
  });
});
```

- Update komentar dokumentasi di atas file (baris 8, 13) supaya sesuai signature baru.

### 3.3 `web/components/stock-clip.js`

- **Hapus total** elemen `actionBar` (deklarasi + `innerHTML` + `appendChild(actionBar)` + listener `actionBar.querySelector('#action-bar-btn').onclick = ...`).
- Tambah variabel closure `let currentVisibleClips = [];` di scope yang sama dengan `selectedClipIds`.
- Di dalam `refresh()`, tepat setelah blok filtering (`if (currentStatusFilter !== 'all') {...}` dan `if (currentCampaignFilter) {...}`), tambahkan: `currentVisibleClips = clips;`
- Ganti fungsi `updateActionBar()` jadi `updateDistributeButton()`:

```js
function updateDistributeButton() {
    const btn = section.querySelector('#distribute-btn');
    if (selectedClipIds.size > 0) {
        btn.textContent = `Upload (${selectedClipIds.size})`;
        btn.disabled = false;
        btn.style.opacity = '1';
    } else {
        const eligible = currentVisibleClips.filter(c => c.upload_status === 'belum_diupload');
        btn.textContent = 'Upload Semua';
        btn.disabled = eligible.length === 0;
        btn.style.opacity = eligible.length === 0 ? '0.5' : '1';
    }
}
```
Ganti **semua** pemanggilan `updateActionBar()` (checkbox change handler, akhir `refresh()`) jadi `updateDistributeButton()`.

- Ganti isi `section.querySelector('#distribute-btn').onclick`:

```js
section.querySelector('#distribute-btn').onclick = async () => {
    const distributeBtn = section.querySelector('#distribute-btn');
    const idsToUpload = selectedClipIds.size > 0
        ? Array.from(selectedClipIds)
        : currentVisibleClips.filter(c => c.upload_status === 'belum_diupload').map(c => c.id);

    if (idsToUpload.length === 0) return;

    const originalText = distributeBtn.textContent;
    distributeBtn.disabled = true;
    distributeBtn.textContent = 'Mengupload...';

    try {
        const res = await window.pywebview.api.quick_upload(idsToUpload);
        if (res && res.status === 'ok') {
            selectedClipIds.clear();
            await refresh();
        } else {
            alert('Gagal upload: ' + (res?.message || 'Unknown error'));
            distributeBtn.disabled = false;
            distributeBtn.textContent = originalText;
        }
    } catch (e) {
        alert('Terjadi error saat upload');
        distributeBtn.disabled = false;
        distributeBtn.textContent = originalText;
    }
};
```

- Blok `if (autoSelectUnuploaded) { ... }` (dipicu dari tombol "Upload" di halaman Campaign Edit) — ganti isinya, buang pemanggilan `DistributionPanel`:

```js
if (autoSelectUnuploaded) {
    const idsToUpload = clips.filter(c => c.upload_status === 'belum_diupload').map(c => c.id);
    if (idsToUpload.length > 0) {
        await window.pywebview.api.quick_upload(idsToUpload);
        await refresh();
        return;
    }
}
```

- Di dalam `clips.forEach(c => {...})`, saat memanggil `window.FileItem.v3({...})`: **hapus** properti `onUpload: async () => {...}` (seluruh blok `prompt()`/`confirm()`), **tambah**:

```js
onTitleChange: async (newTitle) => {
    const res = await window.pywebview.api.update_clip_title(c.path, newTitle);
    if (!res || res.status !== 'ok') {
        alert('Gagal menyimpan judul: ' + (res?.message || 'Unknown error'));
        refresh();
    } else {
        c.title = newTitle;
    }
}
```

### 3.4 `web/components/campaign-edit.js`

Tambahkan field baru persis di sebelah grup `durasiGroup` (field number, konsisten style dengan Durasi Min/Max):

```js
const maxClipsPerDayGroup = document.createElement('div');
maxClipsPerDayGroup.innerHTML = `<label class="field-label" style="display:block;margin-bottom:6px;">Maks Clip per Akun / Hari</label>
  <input type="number" id="campaignMaxClipsPerDay" class="input" value="2" min="1">`;
briefCard.appendChild(maxClipsPerDayGroup);
```
Taruh setelah `briefCard.appendChild(durasiGroup);` dan sebelum `briefCard.appendChild(hashtagsGroup);`.

Di `return { ..., fields: {...} }`, tambahkan:
```js
maxClipsPerDayInput: maxClipsPerDayGroup.querySelector('#campaignMaxClipsPerDay'),
```

### 3.5 `web/campaigns.js`

- Di `saveCampaign()`, dalam object `data.brief = {...}`, tambahkan:
  ```js
  max_clips_per_day: parseInt(f.maxClipsPerDayInput.value) || 2,
  ```
- Di **kedua** tempat yang men-populate form dari data existing (fungsi load-untuk-edit ~baris 186-187, dan `applyExtractedBrief` ~baris 403-404 — cari pola `f.durasiMinInput.value = b.durasi_min || 15;`), tambahkan baris setelahnya:
  ```js
  f.maxClipsPerDayInput.value = b.max_clips_per_day || 2;
  ```

### 3.6 `web/components/distribution-panel.js` + `web/index.html`

- Hapus file `web/components/distribution-panel.js`.
- Hapus baris `<script src="components/distribution-panel.js"></script>` di `web/index.html`.
- Pastikan tidak ada lagi referensi `window.Components.DistributionPanel` di seluruh `web/` (grep untuk memastikan).

---

## 4. Acceptance checklist (jalankan/pikirkan satu-satu sebelum lapor selesai)

- [ ] Panel Clips: hanya ada 1 dropdown + 1 tombol di header, tidak ada footer/action bar lagi.
- [ ] Tombol berubah teks "Upload Semua" ⇄ "Upload (N)" secara real-time saat checkbox dicentang/dilepas.
- [ ] Klik tombol saat tidak ada checkbox = hanya proses clip berstatus `belum_diupload` di list yang sedang difilter, tanpa modal apa pun.
- [ ] Klik tombol saat ada checkbox dicentang = hanya proses clip yang dicentang.
- [ ] Row clip: tidak ada lagi tombol "Upload" per-baris. Hanya Delete + Play tersisa.
- [ ] Double-click judul → jadi input siap ketik, Enter/klik-keluar = tersimpan (cek `data.json` clip itu berubah `hook_text`/`title`-nya), Escape = batal tanpa berubah.
- [ ] Campaign Edit punya field baru "Maks Clip per Akun / Hari", tersimpan & terbaca balik saat reopen campaign yang sama.
- [ ] `data.json` clip yang baru dijadwalkan (`scheduled_uploads[-1]`) punya key `"caption"` berisi gabungan CTA + tagged accounts + hashtags dari campaign terkait (kosong string kalau `campaign_id` = `default`/`None`).
- [ ] Tidak ada lagi referensi ke `distribution-panel.js`/`DistributionPanel` di repo.
- [ ] Tombol "Upload" di halaman Campaign Edit (yang manggil `stockClipView.refresh(id, true)`) tetap berfungsi (langsung upload clip belum-terupload campaign itu, tanpa modal).
- [ ] Platform lain (`tiktok`, `youtube`) tidak rusak — `upload_clip()` masih bisa dipanggil scheduler seperti biasa, cuma nambah `description`.

---

## 5. Format laporan balik yang saya butuhkan

Setelah selesai, kasih saya:
1. Daftar file yang diubah/dihapus/ditambah (path saja, satu baris tiap file).
2. Untuk tiap file: ringkas 2-3 kalimat apa yang berubah (bukan full diff, kecuali saya minta).
3. Asumsi/keputusan yang kamu ambil sendiri di luar spesifikasi di atas (kalau ada) — tandai jelas sebagai **ASUMSI**.
4. Kalau ada bagian dari instruksi ini yang bertabrakan dengan kode aktual saat kamu baca ulang filenya (nama fungsi beda, struktur data beda, dll), **jangan dipaksakan mengikuti dokumen ini** — sesuaikan ke kode nyata, lalu laporkan penyesuaian itu.
5. Langkah manual testing yang kamu sarankan saya jalankan untuk verifikasi (kalau app-nya jalan via pywebview, jelasin cara run singkatnya).
