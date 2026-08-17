# INSTRUKSI IMPLEMENTASI — Upload & Distribution (SSR_CLIPPER)

**Target:** dikerjakan oleh AI coding assistant (Gemini) di repo `SSR_CLIPPER`
(branch `Master`). Ini pasangan dari `GEMINI_INSTRUCTIONS_campaign.md` — **kerjakan
dokumen Campaign itu DULU**, karena dokumen ini bergantung pada `campaign_id`
yang sudah menempel di clip (lewat `get_video_folders()`/`get_stock_clips()`
yang sudah di-extend di sana). Scope dokumen ini: mulai dari perubahan UI
Stock Clip sampai clip benar-benar terdistribusi & terupload ke akun sosmed.

---

## 0. Fakta penting dari source code

1. `get_campaigns()`, data Campaign (`cfg["campaigns"]`), dan field
   `campaign_id` di video-level `data.json` **sudah ada** kalau
   `GEMINI_INSTRUCTIONS_campaign.md` sudah dikerjakan. Field
   `"campaigns"` di `get_account_stats()` **BUKAN** campaign asli — cuma
   jumlah total akun Repliz, jangan dipakai.
2. `get_repliz_accounts()` **sudah bekerja** — return akun asli dari Repliz
   (`_id`, `name`, `type`, `isConnected`).
3. `upload_clip(clip_path, platform, options)` **SYNCHRONOUS & BLOCKING** —
   upload langsung saat dipanggil, satu per satu, TIDAK ADA antrian/jadwal
   sama sekali. **JANGAN diubah** — dipakai lagi oleh scheduler baru (§3.4).
4. Clip **belum pernah punya field status upload** apa pun.
5. Di `web/components/stock-clip.js` baris ~39 & ~167, dropdown
   `id="stock-campaign-filter"` diberi label **"Campaign: All"** padahal
   isinya filter per **video/job folder** (`selectedFolderId`), bukan grup
   akun. **Rename jadi "Video: All"** supaya tidak bentrok istilah dengan
   Campaign (§4.1).
6. **Bug**: class `.select` di `web/css/components.css` (baris ~161) tidak
   punya `background-color` eksplisit → di dark mode render jadi kotak hitam
   pekat. Perbaiki sekalian (§4.6).

---

## 1. Scope

**Dikerjakan:**
- Field status upload per clip (`upload_status`, `scheduled_uploads`,
  `conflict_group_id` — disiapkan buat Upgrade #1 yang terpisah).
- Perubahan `stock-clip.js`: rename filter, checkbox multi-select, badge
  status, filter status, action bar.
- Component baru `distribution-panel.js` — modal distribusi, auto-detect
  Campaign dari clip yang dipilih.
- Backend: `preview_distribution`, `confirm_distribution`, scheduler
  background, extend `get_stock_clips()`.

**TIDAK dikerjakan (ada di `GEMINI_INSTRUCTIONS_campaign.md`, JANGAN dobel):**
- CRUD Campaign (`create_campaign`/`update_campaign`/`delete_campaign`),
  halaman Campaign List/Edit, brief AI-extract, upload banner.
- Dropdown pilih Campaign di halaman Create Clip / `home.js`.
- Logic generate clip / deteksi overlap (`clipper_core.py` inti) — Upgrade #1.

---

## 2. Data model — status upload per clip

Tambahkan field baru ke clip-level `data.json` (file di
`video_folder/<timestamp>/data.json`, dibaca `get_stock_clips()`). **Jangan
hapus/ubah field yang sudah ada** (`hook_text`, `duration_seconds`, dst).

```json
{
  "upload_status": "belum_diupload",
  "conflict_group_id": null,
  "scheduled_uploads": [
    {
      "id": "sched_x1y2z3",
      "campaign_id": "camp_a1b2c3d4",
      "account_id": "<repliz_account_id_1>",
      "platform": "repliz",
      "scheduled_at": "2026-08-18T09:00:00",
      "status": "terjadwal",
      "attempted_at": null,
      "error_message": null
    }
  ]
}
```

- `upload_status`: `belum_diupload | terjadwal | uploading | sukses | gagal`.
  Dipakai buat badge & filter di Stock Clip.
- `conflict_group_id`: selalu `null` untuk sekarang (Upgrade #1 belum
  jalan) — treat `null` sebagai "tidak overlap dengan clip manapun".
- `scheduled_uploads`: array, 1 clip bisa dikirim ke lebih dari 1 akun/waktu.
- `campaign_id`: **TIDAK disimpan di sini** — sudah ada di video-level
  `data.json` (dari `GEMINI_INSTRUCTIONS_campaign.md`), tinggal dibaca &
  di-propagate ke tiap clip lewat `get_stock_clips()` (§3.5), sama seperti
  `video_title` yang sudah diperlakukan begitu di kode sekarang.

---

## 3. Backend — `app.py`

### 3.1 `preview_distribution(clip_ids, campaign_id, max_per_account_per_day)` — BARU

**Inti fitur.** Tidak menyimpan apa pun — cuma menghitung rencana & return.

- `campaign_id` **opsional**:
  - Dikirim eksplisit (user pilih manual / "default") → pakai itu.
  - Kosong/`None` → auto-detect dari `clip_ids`: lihat `campaign_id` yang
    sudah menempel di tiap clip (§3.5). Semua clip share `campaign_id` sama
    & tidak kosong → pakai otomatis. Ada yang beda/`null` (mixed) → return
    `{"status": "mixed_or_missing_campaign", "message": "Clip yang dipilih
    berasal dari campaign berbeda / belum ada campaign. Pilih campaign
    secara manual."}` — frontend tampilkan dropdown manual (§4.2).
- Ambil daftar account unit: `campaign_id` merujuk campaign asli di
  `cfg["campaigns"]` → pakai `account_ids`-nya. `campaign_id == "default"` →
  pakai SEMUA akun dari `get_repliz_accounts()`.
- Jalankan algoritma §5.
- Return (normal):

```json
{
  "status": "ok",
  "campaign_id": "camp_a1b2c3d4",
  "campaign_name": "Campaign Clippo",
  "auto_detected": true,
  "assignments": [
    {"clip_id": "...", "clip_title": "...", "account_id": "...",
     "account_name": "...", "platform": "...", "scheduled_at": "2026-08-18T09:00:00"}
  ],
  "overflow_count": 2,
  "overflow_note": "2 clip lainnya otomatis dijadwalkan besok karena kapasitas akun penuh hari ini"
}
```

### 3.2 `confirm_distribution(assignments)` — BARU

Terima array `assignments` (hasil §3.1, mungkin sudah diedit manual di
frontend). Untuk tiap item: cari clip data.json via `clip_id`, tambahkan
entry baru ke `scheduled_uploads` dengan `status: "terjadwal"`, update
`upload_status` clip jadi `"terjadwal"`. **JANGAN panggil `upload_clip()`
di sini** — scheduler (§3.4) yang eksekusi sesuai waktunya.

### 3.3 `get_clip_upload_status_summary()` — BARU (disarankan)

Return `{"belum_diupload": N, "terjadwal": N, "uploading": N, "sukses": N,
"gagal": N}` — scan semua clip. Dipakai angka di filter tab Stock Clip
(§4.1) biar tidak dihitung manual di JS.

### 3.4 Scheduler background — BARU

`upload_clip()` sepenuhnya manual-trigger, jadi perlu thread polling
(`threading.Thread`, daemon=True, loop `while True: ... time.sleep(60)`).
Start sekali saat app mulai (cari baris `webview.start(...)`, start thread
ini SEBELUM baris itu). Tiap iterasi:
1. Scan clip dengan `scheduled_uploads` berstatus `"terjadwal"` dan
   `scheduled_at <= now`.
2. Set status entry jadi `"uploading"`, update `upload_status` clip.
3. Panggil `upload_clip(clip_path, entry["platform"], {"title": ...,
   "account_id": entry["account_id"]})` — fungsi yang SUDAH ADA, tidak diubah.
4. Update status entry jadi `"sukses"`/`"gagal"` (+ `error_message`,
   `attempted_at`).
5. Hitung ulang `upload_status` ringkasan clip: ada entry
   `terjadwal`/`uploading` → pakai itu; semua final → prioritaskan `gagal`
   di atas `sukses`.

### 3.5 Extend `get_video_folders()` & `get_stock_clips()`

- `get_video_folders()` (baris ~821): kalau belum ditambahkan oleh
  `GEMINI_INSTRUCTIONS_campaign.md`, pastikan `"campaign_id": data.get("campaign_id")`
  ikut di-return per folder.
- `get_stock_clips()` (baris ~856): tambahkan ke tiap dict clip yang
  di-`append()`:
  - `"upload_status": cdata.get("upload_status", "belum_diupload")`
  - `"conflict_group_id": cdata.get("conflict_group_id")`
  - `"campaign_id": vdata.get("campaign_id")` — pola sama seperti
    `video_title` yang sudah diturunkan dari `vdata` (data video-level) ke
    tiap clip di kode yang ada sekarang.

---

## 4. Frontend

### 4.1 `web/components/stock-clip.js`

- **Rename filter** — baris ~39 (`'Campaign: All'`) & ~167
  (`'Campaign: ' + ...`): ganti semua `'Campaign'` jadi `'Video'`.
- **Ganti header Clips panel** (baris ~75-88, `clipsHeader.innerHTML`): hapus
  `#upload-platform`, `#upload-account`, `#upload-all-btn`. Ganti:
  - `<select id="stock-status-filter">`: Semua / Belum diupload / Terjadwal
    / Uploading / Sukses / Gagal (pakai angka dari
    `get_clip_upload_status_summary()`, §3.3).
  - `<button id="distribute-btn">Distribusikan & upload</button>` — disabled
    (abu-abu) selama `selectedClipIds.size === 0`.
- State baru di scope `StockClipView`: `let selectedClipIds = new Set();`
- Tiap render clip (loop `clips.forEach`, baris ~262 dst):
  - Checkbox di kiri row (sebelum konten `FileItem.v3`). Kalau `file-item.js`
    v3 tidak gampang diubah, bikin wrapper `<div style="display:flex;align-items:center;">`
    manual berisi checkbox + hasil `FileItem.v3(...)` — dokumentasikan
    keputusan ini dengan komentar kode.
  - Badge status (warna sesuai tabel di bawah) pakai `c.upload_status`.
  - Toggle checkbox → update `selectedClipIds` → `updateActionBar()` (baru).

  | `upload_status` | bg | text |
  |---|---|---|
  | `belum_diupload` | `#F3F4F6` | `#374151` |
  | `terjadwal` | `#FEF3C7` | `#92400E` |
  | `uploading` | `#DBEAFE` | `#1E40AF` |
  | `sukses` | `#DCFCE7` | `#166534` |
  | `gagal` | `#FEE2E2` | `#991B1B` |

- Filter status: filter array `clips` client-side berdasar
  `#stock-status-filter` sebelum render (JS `.filter()`, tidak perlu endpoint
  baru).
- Action bar sticky di bawah list: muncul kalau `selectedClipIds.size > 0`,
  teks `"${n} clip dipilih"` + tombol "Distribusikan & upload" →
  `window.Components.DistributionPanel(...)` (§4.2).
- Tombol "Upload" individual di `FileItem.v3` (`onUpload`) **tetap ada**
  sebagai quick-action 1 klik ke 1 akun (behavior lama, tidak diubah).
- Dukung deep-link filter dari Campaign page (`GEMINI_INSTRUCTIONS_campaign.md`
  §4.2/§4.3, tombol "Stok"/"Upload"): terima query param atau state
  `campaign_id` saat halaman dibuka, otomatis filter clips yang
  `c.campaign_id === campaign_id`. Kalau datang dari tombol "Upload" (bukan
  "Stok"), setelah filter diterapkan, auto-select semua clip
  `upload_status === "belum_diupload"` di hasil filter itu dan langsung buka
  Distribution Panel.

### 4.2 Component baru — `web/components/distribution-panel.js`

```js
window.Components = window.Components || {};
window.Components.DistributionPanel = function (selectedClipIds, onDone) {
  // return { element, open, close }
};
```

Alur:
0. Saat dibuka, panggil `preview_distribution(selectedClipIds, null, maxPerAccount)`:
   - `status: "ok"` & `auto_detected: true` → **jangan tampilkan dropdown
     Campaign.** Tampilkan info read-only: `"✓ {campaign_name}  ·  {N} akun"`
     + ringkasan singkat 1 baris (misal CTA campaign itu, ambil dari brief
     kalau tersedia) + link kecil "Ganti campaign — kelola akun & brief
     campaign ini" (navigasi ke halaman Campaign edit, dari
     `GEMINI_INSTRUCTIONS_campaign.md`).
   - `status: "mixed_or_missing_campaign"` → tampilkan dropdown Campaign
     manual (isi dari `get_campaigns()`, + opsi fallback `"Semua akun
     (default)"` kalau list kosong) + pesan peringatan.
1. Input angka **"Maks clip per akun / hari"**, default `2`.
2. Tiap kali campaign/kapasitas berubah, panggil ulang `preview_distribution`,
   render hasil sebagai **list flat** (bukan kalender/grid): dot kecil warna
   (opsional, berdasar `conflict_group_id`), nama clip, ikon platform + nama
   akun, waktu terjadwal rata kanan.
3. `overflow_note` (kalau `overflow_count > 0`) tampil sebagai teks kecil di
   bawah list.
4. Tombol **Batal** / **Konfirmasi & jadwalkan** (panggil
   `confirm_distribution(assignments)` → tutup modal → panggil `onDone()` →
   `StockClipView.refresh()` supaya badge status ter-update).

Styling: token sama dengan `design-system.css` (`#8DC63F` tombol primary,
card putih radius 12px, border `#E5E7EB`, font Inter).

### 4.3 `web/index.html`

Tambahkan setelah `file-item.js`, sebelum `stock-clip.js`:
```html
<script src="components/distribution-panel.js"></script>
```

### 4.4 Extend `get_stock_clips()` — lihat §3.5 (backend)

### 4.5 Bug fix — `web/css/components.css`

Cari class `.select` (baris ~161), tambahkan:
```css
.select {
  background-color: #FFFFFF;
  color: #374151;
  appearance: none;
  /* ...baris lain yang sudah ada, jangan dihapus... */
}
```

---

## 5. Algoritma distribusi (dipakai `preview_distribution`, §3.1)

```
input: clips[] (id, title, conflict_group_id), account_units[], max_per_account_per_day

1. groups = group clips by conflict_group_id
   (conflict_group_id == null → tiap clip jadi grup sendiri)
2. sort groups by size DESC
3. load_map = {}  # (account_id, date) -> jumlah clip terisi
4. today = current_date(); assignments = []
5. for group in groups:
     used_today = set()
     for clip in group:
       day = today
       while True:
         candidate = account_unit dengan load_map[(acc, day)] terendah,
                     ACC NOT IN used_today
         if load_map[(candidate, day)] < max_per_account_per_day:
             assignments.append({clip, candidate, day, hour="09:00"})
             load_map[(candidate, day)] += 1
             used_today.add(candidate)
             break
         else:
             day = day + 1  # rollover ke hari berikutnya
6. overflow_count = jumlah clip yang jadwalnya mundur dari `today`
7. return assignments, overflow_count
```

Karena `conflict_group_id` sekarang selalu `null` (Upgrade #1 belum jalan),
tiap clip otomatis jadi grup sendiri — tidak ada overlap-avoidance yang
berlaku secara nyata untuk sekarang. Ini DISENGAJA — begitu Upgrade #1
mengisi field ini, algoritma otomatis mulai menghormati aturan overlap tanpa
perlu diubah lagi.

---

## 6. Checklist testing manual

- [ ] Dropdown Jobs panel di Stock Clip sekarang "Video: All", bukan
      "Campaign: All".
- [ ] Centang 2-3 clip → action bar bawah muncul dengan jumlah benar.
- [ ] Klik "Distribusikan & upload" pada clip yang campaign_id-nya seragam →
      Campaign otomatis ter-pre-select (read-only info, bukan dropdown).
- [ ] Pilih campuran clip dari 2 campaign berbeda → jatuh ke mode dropdown
      manual + pesan peringatan.
- [ ] Ubah angka kapasitas → preview list berubah sesuai.
- [ ] Klik "Konfirmasi & jadwalkan" → modal tertutup, badge status clip
      berubah jadi "Terjadwal" tanpa reload halaman.
- [ ] Set `scheduled_at` ke masa lalu (untuk testing) → status otomatis
      berubah Uploading → Sukses/Gagal tanpa interaksi user.
- [ ] Klik "Stok"/"Upload" dari card Campaign → Stock Clip ter-filter benar
      ke campaign itu (dan untuk "Upload", langsung buka Distribution Panel
      dengan clip belum-upload ter-select).
- [ ] Semua `<select>` di app tidak ada lagi yang render kotak hitam di dark
      mode.
- [ ] Tombol "Upload" individual per-clip lama masih berfungsi seperti
      sebelumnya.

---

## 7. Reminder — jangan scope creep

Jangan bangun ulang Campaign CRUD/halaman Campaign di sini — itu domain
`GEMINI_INSTRUCTIONS_campaign.md`. Jangan sentuh logic generate/highlight
clip di `clipper_core.py`. Kalau nemu isu di luar scope, catat `// TODO:`,
jangan diperbaiki di PR yang sama.
