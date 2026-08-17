# INSTRUKSI IMPLEMENTASI — Campaign Feature (SSR_CLIPPER)

**Target:** dikerjakan oleh AI coding assistant (Gemini) di repo `SSR_CLIPPER`
(branch `Master`). Ini 1 dari 2 dokumen implementasi — pasangannya adalah
`GEMINI_INSTRUCTIONS_upload.md` (Stock Clip → distribusi). Dokumen ini
fokus ke Campaign: halaman list, halaman create/edit, brief AI-extract, dan
hook campaign ke proses generate clip. **Kerjakan dokumen ini duluan** —
`GEMINI_INSTRUCTIONS_upload.md` bergantung pada `campaign_id` yang dihasilkan
di sini.

---

## 0. Fakta penting dari source code

1. **Belum ada apa pun terkait Campaign** di frontend selain 1 komponen mati
   di `dashboard.js` ("Campaign Distribution" tree) yang selalu kosong karena
   `get_campaigns()` di `app.py` (baris ~435) cuma stub `return []`.
2. **Pola AI provider yang SUDAH ADA** (ikuti pola ini, jangan bikin baru):
   `cfg["ai_providers"]` adalah dict dengan key `"highlight_finder"`,
   `"caption_maker"`, `"hook_maker"` — masing-masing `{api_key, base_url, model}`.
   Semua pakai `from openai import OpenAI` (OpenAI-compatible client, bisa
   dipointing ke OpenAI/Anthropic/Gemini lewat `base_url` beda). Diatur di
   halaman Settings (`ai-settings.js`) dan `save_ai_settings()`/`get_ai_settings()`
   di `app.py` (baris ~43-46).
3. Nav sidebar sekarang cuma: Dashboard, Create Clip, Stock Clip, Settings
   (`web/components/header.js`). **Belum ada nav item "Campaign".**
4. `self.output_dir` (folder hasil generate clip) beda dengan tempat yang akan
   dipakai untuk aset campaign (banner) — pakai `get_app_dir()` (fungsi yang
   sudah ada di `app.py`) sebagai base path, JANGAN taruh banner di dalam
   `output_dir`.
5. "Create Clip" adalah component `home.js`, dipicu tombol nav
   `data-view="create-clip"`. Fungsi start ada di `app.js`
   (`async function start()`), manggil `window.pywebview.api.start_processing(
   url, num_clips, add_captions, add_hook, subtitle_lang, portrait,
   highlight_finder, yt_title_maker)`. Backend-nya `start_processing()` di
   `app.py` baris ~192.

---

## 1. Scope

**Dikerjakan:**
- Data model Campaign lengkap (brief terstruktur + Do/Don't + Aturan Umum +
  banner + account mapping).
- Backend CRUD Campaign + upload banner + AI brief-extraction.
- Halaman **Campaign List** (grid card + banner + stat + tombol Stok/Upload).
- Halaman **Campaign Create/Edit** (2 kolom sesuai wireframe yang sudah di-ACC).
- Nav item baru "Campaign" di sidebar.
- Hook `campaign_id` ke `start_processing()`/`home.js` (dropdown pilih
  Campaign sebelum generate) supaya clip yang lahir otomatis terikat campaign.

**TIDAK dikerjakan (ada di `GEMINI_INSTRUCTIONS_upload.md`, JANGAN dobel):**
- Perubahan `stock-clip.js` (checkbox, badge status, filter, action bar).
- Distribution Panel, `preview_distribution`, `confirm_distribution`, scheduler.
- Field `upload_status`/`scheduled_uploads`/`conflict_group_id` di clip.
- Logic generate clip / deteksi overlap (`clipper_core.py` inti) — itu
  Upgrade #1, proyek terpisah, JANGAN disentuh.

**Catatan dependency 2 arah:** stat "N clip diupload" & "N di stok" di
Campaign List/Edit (§4) butuh field `upload_status` yang baru ADA setelah
`GEMINI_INSTRUCTIONS_upload.md` dikerjakan. Selama itu belum jalan, method
`get_campaign_stats()` di sini WAJIB tetap aman (return 0/"-", jangan crash)
— lihat §3.5.

---

## 2. Data model Campaign

Tambahkan key baru `cfg["campaigns"]`:

```json
[
  {
    "id": "camp_a1b2c3d4",
    "name": "Campaign Clippo",
    "banner_path": "campaign_assets/camp_a1b2c3d4.jpg",
    "account_ids": ["<repliz_account_id_1>", "<repliz_account_id_2>"],
    "brief": {
      "durasi_min": 15,
      "durasi_max": 180,
      "hashtags": ["#clippo", "#clipperclippo"],
      "tagged_accounts": ["@clippo.id", "@erlyanieownerberl"],
      "hooks": [
        "2 orang ini berhasil tembus penghasilan double digit dari Clippo. Kok bisa?",
        "Masih ragu jadi clipper? Lihat hasil yang didapat 2 orang ini dari clippo."
      ],
      "catatan": "Deskripsi personal branding, latar belakang, dan value...",
      "angles": ["Highlight pencapaian clipper", "Highlight benefit clipper"],
      "persona": "Owner sukses yang membangun bisnis dari nol...",
      "tujuan": "Mengajak penonton join live",
      "cta": "0% Potongan untuk clipper"
    },
    "do_rules": ["Hanya clip untuk join live", "Wajib tag akun official"],
    "dont_rules": ["Dilarang reupload full video", "Dilarang gunakan bot"],
    "aturan_umum": [
      {"title": "Dilarang bot, view boosting, dan ads boosting",
       "description": "Submission bisa ditolak dan akun diblokir."},
      {"title": "Video harus tersedia selama 180 hari",
       "description": "Dihapus sebelum itu, pendapatan dibekukan."}
    ]
  }
]
```

Semua field di `brief`/`do_rules`/`dont_rules`/`aturan_umum` **opsional** saat
create (boleh kosong array/string), supaya campaign tetap bisa disimpan
walau brief belum lengkap.

---

## 3. Backend — `app.py`

### 3.1 Ganti `get_campaigns()` (baris ~435)

```python
def get_campaigns(self):
    cfg = self._get_cfg()
    campaigns = cfg.get("campaigns", [])
    try:
        accounts_res = self.get_repliz_accounts()
        accounts_by_id = {a["_id"]: a for a in accounts_res.get("accounts", [])} \
            if accounts_res.get("status") == "ok" else {}
    except Exception:
        accounts_by_id = {}
    result = []
    for camp in campaigns:
        acc_ids = camp.get("account_ids", [])
        camp_out = dict(camp)
        camp_out["account_names"] = [accounts_by_id[a]["name"] for a in acc_ids if a in accounts_by_id]
        stats = self.get_campaign_stats(camp.get("id"))
        camp_out["stats"] = stats
        result.append(camp_out)
    return result
```

### 3.2 `create_campaign(payload)` / `update_campaign(campaign_id, payload)` / `delete_campaign(campaign_id)` — BARU

`payload` = dict berisi `name`, `account_ids`, `brief`, `do_rules`, `dont_rules`,
`aturan_umum` (semua field §2, boleh partial). Pola sama seperti
`save_watermark_settings` (`cfg = self._get_cfg()` → mutasi `cfg["campaigns"]`
→ `self._get_cfg_manager().save(cfg)`). `create_campaign` generate id
`"camp_" + uuid.uuid4().hex[:8]`. Return `{"status":"ok","campaign":{...}}`
atau `{"status":"error","message":"..."}`.

### 3.3 `upload_campaign_banner(campaign_id, file_path)` — BARU

- Validasi ekstensi (`.jpg .jpeg .png .webp`), tolak kalau bukan.
- Copy file ke `get_app_dir() / "campaign_assets" / f"{campaign_id}{ext}"`
  (bikin folder `campaign_assets` kalau belum ada).
- Update `banner_path` (relatif terhadap `get_app_dir()`) di campaign terkait,
  simpan lewat pola §3.2.
- Return `{"status":"ok","banner_path": "..."}`.

### 3.4 `extract_campaign_brief(content_type, content)` — BARU (AI brief-extract)

- `content_type`: `"text" | "image" | "doc"`.
- `content`: string teks mentah (untuk `text`), base64 data (untuk `image`),
  atau path file sementara (untuk `doc`).
- Tambahkan slot AI provider baru `cfg["ai_providers"]["brief_extractor"]`
  (ikuti persis pola `highlight_finder`/`caption_maker`/`hook_maker`, tambahkan
  section-nya juga di `ai-settings.js`, §4.4).
- Alur:
  1. Kalau `content_type == "doc"`: extract teks dulu — `.docx` pakai
     `python-docx`, `.pdf` pakai `pypdf` (tambahkan ke `requirements.txt`
     kalau belum ada). Kalau ekstraksi gagal, return
     `{"status":"error","message":"Gagal membaca dokumen, coba tempel teks manual"}`.
     Hasil teks lanjut diproses sama seperti `content_type == "text"`.
  2. Kalau `content_type == "image"`: kirim ke model VISION-capable (client
     `brief_extractor`) sebagai image content block format OpenAI
     (`{"type":"image_url","image_url":{"url": f"data:image/png;base64,{content}"}}`).
  3. Kalau `content_type == "text"`: kirim langsung sebagai teks di user message.
  4. System prompt (WAJIB, sama untuk ketiga jalur): instruksikan model
     mengembalikan **HANYA JSON valid** (tanpa markdown/backtick) sesuai
     schema `brief` + `do_rules` + `dont_rules` + `aturan_umum` persis seperti
     §2. Contoh system prompt:
     ```
     Kamu membaca brief campaign dari brand. Ekstrak informasinya ke JSON
     dengan schema berikut, HANYA output JSON, tanpa teks lain:
     {"name": "...", "brief": {"durasi_min": int, "durasi_max": int,
     "hashtags": [...], "tagged_accounts": [...], "hooks": [...],
     "catatan": "...", "angles": [...], "persona": "...", "tujuan": "...",
     "cta": "..."}, "do_rules": [...], "dont_rules": [...],
     "aturan_umum": [{"title":"...","description":"..."}]}
     Kalau suatu field tidak ditemukan di brief, isi string kosong "" atau
     array kosong [], JANGAN mengarang.
     ```
  5. Parse response (strip ```json fences kalau ada), `json.loads(...)`.
     Kalau gagal parse, return `{"status":"error","message":"AI gagal
     memproses, coba lagi atau isi manual"}` — JANGAN crash.
  6. Return `{"status":"ok","extracted": {...hasil json...}}`. **Method ini
     TIDAK menyimpan apa pun** — cuma return data buat mengisi form di
     frontend, user tetap harus klik "Simpan campaign" manual (§4.3).

### 3.5 `get_campaign_stats(campaign_id)` — BARU

```python
def get_campaign_stats(self, campaign_id):
    """Return {'account_count', 'clip_uploaded', 'clip_in_stock'}.
    NOTE: clip_uploaded/clip_in_stock butuh field 'upload_status' &
    'campaign_id' di clip data.json — field ini ditambahkan oleh
    GEMINI_INSTRUCTIONS_upload.md. Kalau field itu belum ada, tetap return
    angka aman (0), JANGAN error."""
    cfg = self._get_cfg()
    camp = next((c for c in cfg.get("campaigns", []) if c.get("id") == campaign_id), None)
    account_count = len(camp.get("account_ids", [])) if camp else 0
    clip_uploaded = 0
    clip_in_stock = 0
    try:
        for folder in self.get_video_folders():
            if folder.get("campaign_id") != campaign_id:
                continue
            for clip in self.get_stock_clips(folder.get("id")):
                clip_in_stock += 1
                if clip.get("upload_status") == "sukses":
                    clip_uploaded += 1
    except Exception:
        pass
    return {"account_count": account_count, "clip_uploaded": clip_uploaded, "clip_in_stock": clip_in_stock}
```

### 3.6 Hook `campaign_id` ke proses generate (prasyarat, dipakai `GEMINI_INSTRUCTIONS_upload.md`)

1. **`start_processing()` (baris ~192)**: tambah parameter `campaign_id=None`
   di akhir signature. Simpan ke `self.current_job["campaign_id"] = campaign_id`,
   teruskan ke `self._run(...)` (tambahkan ke `args=(...)`).
2. **Titik penulisan `data.json` level video**: cari di `_run()`/`clipper_core.py`
   bagian yang menulis dict berisi key `"url"` ke file `data.json` (dibaca
   `get_video_folders()`). Tambahkan `"campaign_id": campaign_id` ke dict itu.
   **Jangan ubah logic lain di fungsi itu.**
3. **`get_video_folders()` (baris ~821)**: tambahkan
   `"campaign_id": data.get("campaign_id")` ke tiap dict folder yang di-return.

---

## 4. Frontend

### 4.1 Nav item baru — `web/components/header.js`

Tambahkan 1 nav item baru "Campaign" (icon `ti-speakerphone` atau serupa,
`data-view="campaign"`), taruh setelah "Dashboard", sebelum "Create Clip".

### 4.2 Component baru — `web/components/campaign-list.js`

Halaman grid card, ikuti wireframe yang sudah di-ACC:
- Header: judul "Campaign" + tombol "+ Buat campaign baru" (lime,
  `#8DC63F`) → buka `campaign-edit.js` mode create.
- Grid card per campaign (`get_campaigns()`): banner (aspect-ratio 3/2, dari
  `banner_path`, fallback gradient/placeholder icon kalau kosong), nama
  campaign, badge "Aktif", baris stat (`ti-users` + `account_count`,
  `ti-movie` + `clip_in_stock`), 2 tombol footer **"Stok"** (buka Stock Clip
  ter-filter ke `campaign_id` ini — reuse filter dropdown yang sudah ada di
  `stock-clip.js`, prefill dengan campaign ini kalau memungkinkan, TIDAK
  reset filter existing) dan **"Upload"** (lime — buka Stock Clip dengan
  filter yang sama LALU langsung trigger Distribution Panel, atau minimal
  buka Stock Clip ter-filter; detail exact trigger ada di
  `GEMINI_INSTRUCTIONS_upload.md`, di sini cukup navigasi + filter).
- **Tidak ada teks deskripsi** di card (sudah direvisi, dihapus).
- 1 card terakhir dashed "+ Buat campaign baru dari brief brand" (shortcut
  sama seperti tombol header).

### 4.3 Component baru — `web/components/campaign-edit.js`

Halaman create/edit, layout **2 kolom** (`display:grid; grid-template-columns:1.3fr 1fr; gap:14px;`),
sesuai wireframe yang sudah di-ACC:

**Kolom kiri (2 card ditumpuk):**
1. Card "Brief campaign" — field: Durasi konten (2 number input min-max),
   Hashtag wajib (tag input, multi chip, tambah dengan Enter), Akun wajib
   di-tag (text input, bisa multi dipisah koma), Hook atau script (list
   textarea, tombol "+ tambah hook"), Catatan (textarea), Angle konten wajib
   (chip list + tambah), Persona yang wajib dibangun (textarea).
2. Card "Aturan dan larangan" — 2 kolom Do (hijau, `#8DC63F` border-left,
   icon `ti-circle-check` hijau `#166534`) & Don't (merah, `#EF4444`
   border-left, icon `ti-circle-x` merah `#991B1B`), tiap bullet punya tombol
   hapus (×) saat hover, plus "+ tambah" di bawah tiap kolom. Di bawahnya,
   sub-card "Aturan umum" — list `{title, description}` dengan icon generik
   (`ti-alert-triangle` untuk larangan keras, `ti-clock`/`ti-heart`/`ti-eye`
   untuk lainnya — icon boleh fixed per index, tidak perlu disimpan di data),
   link "Selengkapnya" collapse/expand kalau item > 3.

**Kolom kanan (2 card ditumpuk):**
1. Card banner+stats: banner 3:2 (upload via klik, `upload_campaign_banner()`),
   di bawahnya `"{account_count} akun terhubung"`, baris
   `"{clip_uploaded} clip diupload  ·  {clip_in_stock} di stok"`, lalu 2
   tombol **"Stok"** & **"Upload"** (sama seperti di card list, §4.2).
2. Card "Isi cepat dengan AI" (bg `#F2FCE2`, border dashed `#8DC63F`):
   textarea paste teks + drop-zone file (`.doc/.docx/.pdf/.png/.jpg`) + tombol
   "Create brief" (lime, full width) → panggil `extract_campaign_brief()`
   sesuai `content_type` yang sesuai dengan input yang diisi user (textarea
   ada isi → `"text"`; file di-drop → `"doc"` atau `"image"` sesuai
   ekstensi) → hasil `extracted` dipakai buat **overwrite field-field di
   kolom kiri** (user tetap bisa edit manual sebelum klik "Simpan campaign"
   di header — TIDAK auto-save).

**Header halaman:** nama campaign (editable inline atau input di dalam card
kiri paling atas), tombol "Batal" & "Simpan campaign" (panggil
`create_campaign()`/`update_campaign()` dengan payload gabungan semua field
di kolom kiri + `account_ids` dari account picker, §4.3b).

### 4.3b Account picker

Di dalam card "Brief campaign" atau card terpisah kecil di kolom kiri bawah
(boleh nempel di card mana saja yang masuk akal secara UI — keputusan detail
di tangan implementor): checklist akun dari `get_repliz_accounts()`,
menampilkan jumlah terpilih ("8/24 akun dipilih"), grouped per platform
(chip dengan icon `ti-brand-tiktok`/`ti-brand-instagram`/`ti-brand-youtube`).

### 4.4 `web/components/ai-settings.js` — tambah section provider ke-4

Duplikasi section "Hook Maker" yang sudah ada, ganti jadi "Brief Extractor"
(field api_key/base_url/model + tombol test, identik strukturnya), simpan ke
`cfg["ai_providers"]["brief_extractor"]` lewat `save_ai_settings()` yang
sudah ada (tidak perlu backend baru untuk save, cukup pastikan key
`brief_extractor` ikut ter-include di payload yang dikirim).

### 4.5 `web/components/home.js` + `app.js` — dropdown pilih Campaign

- Tambah `<select id="home-campaign-select">` di form Create Clip, isi dari
  `get_campaigns()` + 1 opsi default `"Tanpa campaign"` (value kosong).
- Di `app.js` fungsi `start()`: ambil `homeView.fields.campaign.value`,
  sisipkan sebagai argumen TERAKHIR ke `start_processing(...)` (tambah di
  akhir, jangan ubah urutan argumen yang sudah ada).
- **Jangan ubah** `lockControls()`, `updateStepStatus()`, atau logic
  polling/progress yang sudah ada.

### 4.6 `web/index.html`

Tambahkan:
```html
<script src="components/campaign-list.js"></script>
<script src="components/campaign-edit.js"></script>
```
setelah `file-item.js`, sebelum `dashboard.js`.

---

## 5. Checklist testing manual

- [ ] Nav "Campaign" muncul, klik masuk ke grid list (kosong pertama kali).
- [ ] "+ Buat campaign baru" → halaman 2 kolom sesuai wireframe muncul.
- [ ] Tempel teks brief contoh (pakai isi CSV yang dikasih user) di "Isi cepat
      dengan AI" → klik "Create brief" → field-field kolom kiri terisi sesuai.
- [ ] Upload gambar screenshot brief (seperti 4 gambar referensi) →
      "Create brief" → field ke-extract dengan benar (minimal sebagian besar
      benar, wajar kalau ada yang perlu dikoreksi manual).
- [ ] Upload banner 3:2 → tersimpan & muncul di card list.
- [ ] Pilih beberapa akun → simpan → campaign muncul di list dengan jumlah
      akun yang benar.
- [ ] Di Create Clip, dropdown Campaign berisi campaign yang baru dibuat →
      pilih → generate → cek `data.json` video-level punya `campaign_id` benar.
- [ ] Tombol "Stok" & "Upload" di card campaign mengarahkan ke Stock Clip
      dengan filter yang sesuai.
- [ ] Kalau provider `brief_extractor` belum diisi api_key-nya, tombol
      "Create brief" kasih pesan error yang jelas, bukan crash diam-diam.

---

## 6. Reminder — jangan scope creep

Jangan bangun ulang Distribution Panel/Stock Clip di sini — itu domain
`GEMINI_INSTRUCTIONS_upload.md`. Jangan sentuh logic highlight/overlap clip
di `clipper_core.py`. Kalau nemu isu di luar scope, catat `// TODO:`, jangan
diperbaiki di PR yang sama.
