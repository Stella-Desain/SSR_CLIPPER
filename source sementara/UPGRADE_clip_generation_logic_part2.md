# SSR_CLIPPER — Upgrade Part 2: Smart Download, Clip Count Mode, Parallel Progress UI

**Repo**: `github.com/Stella-Desain/SSR_CLIPPER`, branch `Master`
**Prasyarat**: Part 1 (transkrip mandiri, highlight uncapped, parallel worker pool 4-7, metadata campaign/conflict_group) SUDAH diimplementasikan dan berjalan di `clipper_core.py` (`process()` baris ~608, `find_highlights()` ~2537, `_assign_conflict_groups()` ~2491, `process_clip()` ~2710). MD ini **menambah**, bukan mengganti, itu semua.

Ground truth tambahan yang sudah diverifikasi:
- `download_subtitle_only(url) -> (srt_path, video_info)` — sudah ada, tidak pernah dipanggil. `srt_path` bisa `None`.
- `download_video_section(url, start_time, end_time, output_path) -> str` — sudah ada, tidak pernah dipanggil. Terima timestamp format `"HH:MM:SS,mmm"` ATAU `"HH:MM:SS.mmm"` langsung (sama seperti `highlight["start_time"]`), tidak perlu konversi tambahan.
- `process_clip(..., pre_cut: bool = False, ...)` — param `pre_cut` sudah ada dari awal, cuma belum pernah dipanggil dengan `True`. Kalau `True`, artinya `video_path` yang dioper adalah file yang sudah dipotong duluan (skip step cutting).
- `video_info` dict (dibangun di 4 tempat: `_download_video_module`, `_download_video_subprocess`, `_download_subtitle_only_module`, `_download_subtitle_only_subprocess`) **belum ada field `duration`**.
- `AutoClipperCore.process()`: `video_path, srt_path, video_info = self.download_video(url)` selalu download FULL video di awal, tidak ada jalur ringan.
- `app.py` `WebAPI._run()`: bikin `core = AutoClipperCore(...)` sebagai variabel LOKAL (baris ~308), tidak disimpan sebagai `self.core` — jadi `get_progress()` cuma bisa baca `self.status`/`self.progress` (dua field global), tidak bisa akses state internal `core`.
- `web/components/home.js`: field `clips` (id `clips`, number input) → dikirim sebagai `num_clips` ke `start_processing()`. Field progress lama (`stepDownload/stepHighlight/stepEditing/stepExport`, satu `terminal`, satu `bar`) di-drive murni dari parsing string `status` di `web/app.js` (`updateStepStatus()`, `poll()` — polling `get_progress()` tiap 500ms). Tidak ada state per-clip sama sekali di frontend saat ini.

---

## Task 5 — Tambah field `duration` ke video_info

**File**: `clipper_core.py`, keempat method pembangun `video_info` dict.

Di tiap tempat `video_info = {"title": ..., "description": ..., "channel": ...}` dibangun (baik dari `info.get(...)` [module/yt-dlp python] maupun `yt_data.get(...)` [subprocess/json]), tambah satu key: `"duration": info.get("duration")` (module) atau `"duration": yt_data.get("duration")` (subprocess). Ini field angka detik dari yt-dlp, sudah tersedia gratis di metadata (tidak butuh download tambahan). Lakukan di keempat tempat (2 di `_download_video_module`/`_download_video_subprocess`, 2 di `_download_subtitle_only_module`/`_download_subtitle_only_subprocess`) — cari semua literal `video_info = {` di file untuk memastikan tidak ada yang kelewat.

**Definition of done**: `video_info.get("duration")` selalu berisi angka (detik) baik lewat jalur subtitle-only maupun full-download.

---

## Task 6 — Subtitle-first + heuristik download segmen vs full (bergantung Task 5)

**File**: `clipper_core.py`, method `process()` — restrukturisasi bagian awal (Step 1) dan titik sebelum dispatch worker pool.

**Alur baru**:
1. Coba `srt_path, video_info = self.download_subtitle_only(url)` dulu (ringan, TIDAK download video).
2. Kalau `srt_path` ada → `transcript = self.parse_srt(srt_path)`, `video_path` masih `None` di titik ini.
3. Kalau `srt_path` `None` → **harus** download full video untuk Whisper (tidak ada jalan lain): `video_path, _, video_info = self.download_video(url)`, lalu `transcript = self.transcribe_full_video(video_path)`.
4. Lanjut seperti biasa: `find_highlights()` (Task 7 akan ubah signature-nya, lihat di bawah), validasi `if not highlights`, setup `video_folder`, `self._assign_conflict_groups(highlights)`.
5. **Baru di sini** tentukan sumber video untuk tiap clip, SEBELUM dispatch ke worker pool:
   - **Kalau `video_path` sudah ada** (dari langkah 3 — kasus tanpa subtitle): pakai itu untuk SEMUA clip apa adanya (`pre_cut=False`, seperti perilaku lama). Jangan download apa-apa lagi — percuma, file lengkap sudah di disk.
   - **Kalau `video_path` masih `None`** (kasus subtitle tersedia, belum ada video sama sekali): hitung `unique_duration` = total durasi UNIK dari gabungan semua rentang `[start_time, end_time]` highlight (merge dulu rentang yang overlap sebelum dijumlah — jangan hitung dobel bagian yang overlap). Bandingkan dengan `video_info.get("duration")`:
     - Kalau `unique_duration / total_duration > 0.5` → download full video sekali (`video_path, _, _ = self.download_video(url)`), pakai untuk semua clip (`pre_cut=False`).
     - Kalau tidak → untuk tiap `conflict_group_id` yang ada (bukan tiap highlight — highlight yang overlap share satu rentang waktu, jadi cukup satu download per grup): hitung union `[min(start di grup), max(end di grup)]`, panggil `download_video_section(url, start_union, end_union, output_path)` (simpan di dalam `video_folder`, misal `video_folder / f"segment_{group_id}.mp4"`). Simpan hasil path per `conflict_group_id` di sebuah dict, misal `clip_sources[group_id] = segment_path`.
6. Di loop dispatch worker (`_worker(index, highlight)`), tentukan `video_path` dan `pre_cut` yang dioper ke `process_clip()` per-highlight:
   - Mode full: selalu `(shared_video_path, pre_cut=False)`.
   - Mode segmen: `(clip_sources[highlight["conflict_group_id"]], pre_cut=True)`.

**Catatan implementasi**:
- Butuh helper hitung union durasi dari list rentang waktu yang mungkin overlap (sort by start, merge kalau start berikutnya <= end sebelumnya, jumlahkan panjang tiap merged range). Highlight pakai `parse_timestamp()` yang sudah ada untuk convert ke detik.
- Cek apakah sudah ada helper detik→timestamp string (`format_timestamp` atau semacamnya) untuk convert union start/end kembali ke string sebelum dioper ke `download_video_section`. Kalau belum ada, cukup tulis satu fungsi kecil (kebalikan dari `parse_timestamp`), jangan reinvent parsing yang sudah ada.
- Tetap panggil `self.set_progress(...)` di titik-titik ini supaya progress bar global tidak diam lama saat proses download berlangsung.

**Definition of done**: video dengan subtitle tersedia DAN highlight-nya sedikit/terpencar tidak lagi men-download full video — cukup segmen per conflict group. Video tanpa subtitle tetap download full video seperti sebelumnya (tidak ada perubahan perilaku di jalur ini).

---

## Task 7 — Mode jumlah clip: Fixed number vs AI decides (independen dari Task 6, tapi sama-sama sentuh `process()`)

**File**: `clipper_core.py` (`find_highlights`, `process`), `app.py` (`start_processing`, `_run`), `config/config_manager.py`.

### 7a. `find_highlights()` — tambah dua param opsional
Signature baru: `find_highlights(self, transcript, video_info, max_highlights=30, fixed_count=None, min_score=None)`.

Di bagian akhir (setelah `valid.sort(key=lambda h: h.get("virality_score", 5), reverse=True)`, baris ~2701), ganti blok capping yang sekarang jadi:
```python
if fixed_count is not None:
    valid = valid[:fixed_count]
elif min_score is not None:
    valid = [h for h in valid if h.get("virality_score", 5) >= min_score]
    if len(valid) > max_highlights:
        valid = valid[:max_highlights]
else:
    if len(valid) > max_highlights:
        valid = valid[:max_highlights]
```
`fixed_count` = mode "Fixed number" (ambil N teratas by score, walau skornya rendah — user minta angka pasti). `min_score` = mode "AI decides" (buang yang di bawah skor minimal, cap tetap `max_highlights` sebagai pengaman). Kalau keduanya `None` → perilaku Part 1 tidak berubah (backward compatible).

### 7b. `process()` — terima & teruskan param baru
Tambah param `fixed_count: int = None`, `min_score: int = 6` (default 6 sesuai keputusan produk). Update pemanggilan `find_highlights(transcript, video_info, max_highlights, fixed_count=fixed_count, min_score=min_score)`.

### 7c. `config/config_manager.py`
Tambah default `"ai_decides_min_score": 6` di dict default config (dekat `max_highlights` yang sudah ditambahkan di Part 1).

### 7d. `app.py`
- `start_processing(self, url, num_clips=5, ..., clip_mode="fixed", ...)` — tambah param `clip_mode` (`"fixed"` atau `"ai"`).
- Di dalam, sebelum bikin thread: `fixed_count = int(num_clips) if clip_mode == "fixed" else None`. Kalau `clip_mode == "ai"`, ambil `min_score = int(cfg.get("ai_decides_min_score", 6))`; kalau `"fixed"`, `min_score` tidak relevan (boleh tetap dioper, diabaikan karena `fixed_count` sudah di-set).
- Teruskan `fixed_count` dan `min_score` lewat `args=(...)` thread → `_run(...)` → `core.process(url, ..., fixed_count=fixed_count, min_score=min_score, ...)`.
- Param `num_clips` yang lama tetap diterima di signature (untuk kompatibilitas pemanggil lain kalau ada), tapi nilainya sekarang hanya dipakai kalau `clip_mode == "fixed"`.

**Definition of done**: generate dengan mode "Fixed" menghasilkan persis N clip (atau kurang kalau highlight valid yang ditemukan memang kurang dari N). Generate dengan mode "AI decides" tidak menghasilkan clip dengan `virality_score` di bawah `ai_decides_min_score`, jumlahnya bisa berapa saja sampai `max_highlights`.

---

## Task 8 — Structured per-clip state (bergantung Task 6+7 selesai, karena sentuh dispatch loop yang sama)

**File**: `clipper_core.py` (`process()`, `process_clip()`), `app.py` (`_run`, method baru `get_clips_status`)

### 8a. `clipper_core.py`
Di `process()`, tepat sebelum dispatch ke worker pool (setelah `_assign_conflict_groups`):
```python
self.clips_state_lock = threading.Lock()
self.clips_state = {
    i: {
        "index": i,
        "title": h.get("title"),
        "virality_score": h.get("virality_score"),
        "start_time": h.get("start_time"),
        "end_time": h.get("end_time"),
        "status": "waiting",   # waiting | running | done | error
        "step": "Queued",
        "step_progress": 0.0,
        "error": None,
    }
    for i, h in enumerate(highlights, 1)
}

def _update_clip_state(index, **fields):
    with self.clips_state_lock:
        if index in self.clips_state:
            self.clips_state[index].update(fields)
```
(letakkan `_update_clip_state` sebagai nested function atau method biasa, terserah gaya kode yang sudah ada — yang penting thread-safe lewat lock yang sama).

Tambah method baru: `def get_clips_state(self) -> list: ...` — return `list(self.clips_state.values())` dengan lock, atau `[]` kalau `clips_state` belum pernah di-set (proses belum pernah jalan).

Wiring status:
- Di `_worker(index, highlight)`: panggil `_update_clip_state(index, status="running", step="Starting")` sebelum `process_clip(...)`. Di blok `except`, `_update_clip_state(index, status="error", error=str(e))`. Setelah `process_clip()` sukses (tidak exception), `_update_clip_state(index, status="done", step="Done", step_progress=1.0)`.
- Di dalam `process_clip()`, closure `clip_progress(step_name, step_num, sub_progress)` yang sudah ada (dipakai untuk `self.set_progress` global) — tambah satu baris di situ juga memanggil `self._update_clip_state(index, step=step_name, step_progress=(step_num - 1 + sub_progress) / total_steps)` (pakai formula fraction yang sama persis dengan yang sudah dipakai untuk global bar, jangan bikin formula baru). `index` sudah ada di scope closure (parameter `process_clip`), tidak perlu plumbing tambahan.

### 8b. `app.py`
- Di `_run()`, tepat setelah `core = AutoClipperCore(...)` dibuat: tambah `self.core = core`. Ini satu-satunya cara `get_clips_status()` bisa baca state internal core dari method lain.
- Method baru di `WebAPI`: `def get_clips_status(self): return {"clips": self.core.get_clips_state() if self.core else []}`.

**Definition of done**: memanggil `get_clips_status()` di tengah proses generate mengembalikan list clip dengan status campuran (`waiting`/`running`/`done`), tiap yang `running` punya `step` dan `step_progress` yang berubah seiring waktu. Setelah semua selesai, semua entry `status == "done"` (atau `"error"` untuk yang gagal).

---

## Task 9 — Frontend: toggle mode jumlah clip (bergantung Task 7 untuk kontrak API)

**File**: `web/components/home.js`

Ganti blok `clipsLabel` + `clipsInput` (baris ~172-185) dengan: segmented control 2 opsi ("Fixed number" / "AI decides") di atas, lalu conditional:
- Mode "Fixed number" (default, biar tidak mengejutkan user lama): tampilkan `clipsInput` seperti sekarang.
- Mode "AI decides": sembunyikan `clipsInput`, tampilkan catatan singkat kira-kira "AI akan menghasilkan sebanyak mungkin clip — hanya highlight skor sedang & tinggi yang dipakai" (styling: kotak kecil, background lime muda, teks hijau tua — konsisten dengan `--accent-lime: #8DC63F` yang sudah dipakai di komponen lain).

Simpan mode terpilih di variabel/flag internal (misal `let clipMode = 'fixed';`), export lewat `fields` object yang sudah ada (tambah `fields.clipMode` — getter function atau tracked variable, terserah pola yang dipakai field lain di file ini).

Di `web/app.js`, fungsi `start()` (baris ~262): tambah param `homeView.fields.clipMode` (atau apapun cara Task 9 mengekspornya) ke pemanggilan `window.pywebview.api.start_processing(...)`, sesuai urutan param baru di `start_processing` (Task 7d).

**Definition of done**: toggle Fixed/AI decides bisa diklik, `clipsInput` show/hide sesuai mode, dan `start_processing` menerima `clip_mode` yang benar sesuai pilihan user.

---

## Task 10 — Frontend: progress panel per-clip (bergantung Task 8 untuk `get_clips_status()`)

**File**: `web/components/home.js` (struktur DOM), `web/app.js` (polling & render logic)

### 10a. `home.js` — restrukturisasi kartu Progress (col3)
- Ganti 4 step (`stepDownload/stepHighlight/stepEditing/stepExport`) jadi SATU baris "Preparing" (label + status pill) — merepresentasikan fase download+transkrip+cari-highlight yang masih global/sequential sebelum clip mulai diproses paralel.
- Tambah dua container baru: `inProgressList` (div kosong, diisi JS) dengan label "In progress" + badge count, dan `waitingList` (sama, label "Waiting" + badge count).
- Tambah `errorLogBox` (div kosong, diisi JS) — TERPISAH dari `terminal` (Program Log) yang sudah ada, jangan gabung lagi.
- `terminal`/Program Log yang sudah ada TETAP dipertahankan apa adanya (general log), cuma mekanisme `termAddError` yang lama (nyisipin blok error DI DALAM terminal, lihat `web/app.js` baris ~223-235) di-nonaktifkan/dipindah — error sekarang HANYA muncul di `errorLogBox` baru, tidak dobel di terminal.
- Export container baru ini lewat `fields` (`fields.inProgressList`, `fields.waitingList`, `fields.errorLogBox`).

Tiap baris clip (dipakai untuk in-progress maupun waiting) render: judul (truncate dengan ellipsis kalau kepanjangan), badge skor (`virality_score`), rentang waktu (`start_time`–`end_time`), teks step kecil (untuk waiting selalu "Queued", untuk in-progress pakai `step` dari data), dan progress bar tipis (untuk waiting sembunyikan/isi 0%, untuk in-progress isi dari `step_progress`).

### 10b. `web/app.js` — render dari `get_clips_status()`
Di `poll()` (baris ~308) yang sudah jalan tiap 500ms, tambah satu panggilan lagi: `const cs = await window.pywebview.api.get_clips_status();` lalu:
- Filter `cs.clips` yang `status === "running"` → render ke `fields.inProgressList`, urutkan by `index` (urutan submit = urutan skor, sudah benar).
- Filter yang `status === "waiting"` → render ke `fields.waitingList`.
- Filter yang `status === "error"` → render ke `fields.errorLogBox` (kalau kosong, tampilkan state kosong "Tidak ada error" alih-alih kotak merah kosong).
- Update badge count "Preparing" jadi "Done" begitu `cs.clips.length > 0` (tandanya sudah lewat fase highlight-finding, worker pool sudah mulai jalan).
- Header "Progress X/Y" (`progressCount`, sudah ada elemennya) dihitung dari `done_count = cs.clips.filter(c => c.status === "done").length` dan `total = cs.clips.length`.

Re-render list tiap poll cukup dengan cara paling sederhana yang sudah dipakai file ini (rebuild innerHTML dari array), tidak perlu diffing/virtual-dom — jumlah clip kecil (≤30).

**Definition of done**: saat generate clip jalan dengan banyak highlight, panel Progress menampilkan clip yang sedang dikerjakan (dengan step & persen yang update tiap 500ms) terpisah dari yang masih antre, dan error (kalau ada) muncul di kotak error tersendiri, bukan tercampur di Program Log.

---

## Pembagian subagent (disarankan)

| Subagent | Task | Dependency |
|---|---|---|
| A | Task 5 + 6 (download heuristik) | Tidak ada |
| B | Task 7 (mode jumlah clip, backend+config) | Tidak ada — TAPI A dan B sama-sama edit `process()`. A restrukturisasi bagian download (atas) & dispatch loop (bawah); B cuma nambah parameter & baris pemanggilan `find_highlights`. Review gabungan file `process()` sebelum lanjut ke C, jangan asumsi otomatis clean-merge. |
| C | Task 8 (structured state, backend) | Butuh A+B sudah merge (nyentuh worker dispatch yang sama) |
| D | Task 9 (frontend toggle) | Butuh B (kontrak param `clip_mode`) |
| E | Task 10 (frontend progress panel) | Butuh C (`get_clips_status()` sudah ada dan bentuknya final) |

## Eksplisit DI LUAR SCOPE
- Semua yang sudah "di luar scope" di MD Part 1 (encoder GPU, distribusi/upload, AI auto-fill campaign brief).
- Perubahan visual/styling di luar yang disebutkan eksplisit di Task 9 & 10 (jangan redesign komponen lain di halaman yang sama).

## Final checklist
- [ ] `video_info["duration"]` selalu terisi (Task 5)
- [ ] Video dengan subtitle & highlight sedikit → download per-segmen, bukan full (Task 6)
- [ ] Video tanpa subtitle → tetap full download seperti sebelumnya, tidak ada regresi (Task 6)
- [ ] Mode Fixed menghasilkan tepat N clip; mode AI decides membuang skor di bawah `ai_decides_min_score` (Task 7)
- [ ] `get_clips_status()` mengembalikan state per-clip yang akurat & real-time (Task 8)
- [ ] Toggle Fixed/AI decides berfungsi di UI dan mengirim param yang benar (Task 9)
- [ ] Panel Progress menampilkan in-progress, waiting, dan error log terpisah, update tiap 500ms (Task 10)
