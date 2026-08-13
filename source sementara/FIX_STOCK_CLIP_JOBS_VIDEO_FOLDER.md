# FIX: Stock Clip — Jobs Panel Jadi Video Folder Browser

**Tingkat: KRITIS. Baca seluruh file ini dulu sebelum edit apapun. Kerjakan STEP 1 → 4 berurutan, jangan loncat.**

## Kamu AI Junior. Ini Aturan Wajib.

1. Cuma edit 3 file ini: `utils/helpers.py`, `clipper_core.py`, `app.py`, `web/components/stock-clip.js` — total 4 file. JANGAN sentuh file lain (jangan sentuh `app_tkinter_backup.py`, `pages/*.py`, dialog manapun).
2. Setiap "STEP" kasih kode PERSIS (`CARI` dan `GANTI`). Kalau teks yang harus dicari tidak ketemu persis sama di file, STOP — jangan improvisasi/nebak, laporkan balik ke user teks apa yang beda.
3. Untuk `web/components/stock-clip.js` di STEP 4: itu bukan search-replace, itu GANTI SELURUH ISI FILE dengan kode yang disediakan. Jangan digabung manual.
4. Jangan ubah logic upload (`upload_clip`, `upload-platform`, `upload-account`, tombol Upload Semua) — itu semua tetap sama persis, cuma dipindah lokasinya dalam file.
5. Jangan rename label UI yang tidak diminta (misal teks "Campaign: All" tetap, jangan diganti "Video: All" dsb).
6. Selesai semua step → jalankan bagian "CARA TEST MANUAL" di bawah, laporkan hasilnya.

---

## Konteks Bug (biar paham, bukan buat diubah)

Sekarang setiap clip hasil generate disimpan di folder sendiri-sendiri, rata (flat), langsung di dalam `output/`:

```
output/
  20260813-142233-01/   ← 1 clip
    data.json
    clip.mp4
  20260813-142235-02/   ← 1 clip lain, folder terpisah
    data.json
    clip.mp4
```

Tidak ada folder yang mewakili "1 video sumber = N clips". Makanya:
- Panel **Clips** (kanan) nampilin semua clip campur, judulnya selalu "Clip 1 - ..." karena tiap folder cuma isi 1 mp4.
- Panel **Jobs** (kiri) kosong ("No jobs found") karena dia baca `job_history` di memory (`self.job_history` di `app.py`), bukan dari folder di disk.

## Target Setelah Fix

```
output/
  Gengsi Omzet Besar Tapi Enggak Punya Uang Tunai/   ← folder = 1 video, nama dari judul video di link
    data.json                                         ← metadata video (title, url, created_at, clip_count)
    20260813-142233-01/
      data.json                                       ← metadata clip ini (hook_text, duration_seconds, dst — TIDAK DIUBAH)
      clip.mp4
    20260813-142235-02/
      data.json
      clip.mp4
  Bahaya Bisnis Muntah & Kebiasaan Pebisnis Tua/
    data.json
    20260813-150000-01/
      ...
```

- Panel **Jobs** (kiri) = daftar folder video di atas (klik salah satu = filter Clips panel ke folder itu, klik lagi = balik ke "All").
- Panel **Clips** (kanan) = isi folder yang lagi dipilih (atau semua kalau tidak ada yang dipilih).

---

## STEP 1 — `utils/helpers.py`

Tambahkan fungsi baru untuk bikin nama folder yang aman dari judul video. Taruh di paling bawah file (setelah fungsi `extract_video_id`).

**CARI** (baris paling akhir file):
```python
def extract_video_id(url: str) -> str:
    """Extract YouTube video ID from URL"""
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'(?:youtu\.be\/)([0-9A-Za-z_-]{11})'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None
```

**GANTI DENGAN** (kode lama tetap ada, cuma ditambah fungsi baru di bawahnya):
```python
def extract_video_id(url: str) -> str:
    """Extract YouTube video ID from URL"""
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'(?:youtu\.be\/)([0-9A-Za-z_-]{11})'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def sanitize_folder_name(title: str, max_length: int = 80) -> str:
    """Convert a video title into a safe, filesystem-friendly folder name.

    Removes characters not allowed on Windows/Mac/Linux, collapses whitespace,
    and caps the length so long titles don't break path limits.
    """
    if not title:
        return "Untitled Video"
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', title)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip().strip('.')
    if not cleaned:
        cleaned = "Untitled Video"
    return cleaned[:max_length].strip()
```

Cek: file ini sudah `import re` di baris atas — jangan tambah import baru, sudah ada.

---

## STEP 2 — `clipper_core.py`

Ada 2 edit di file ini.

### 2a. Import `sanitize_folder_name`

**CARI**:
```python
from utils.helpers import get_deno_path, get_ffmpeg_path, is_ytdlp_module_available
```

**GANTI DENGAN**:
```python
from utils.helpers import get_deno_path, get_ffmpeg_path, is_ytdlp_module_available, sanitize_folder_name
```

### 2b. Fungsi `process()` — bikin folder video sebelum proses clip

Cari method `process` (ada komentar `"""Main processing pipeline"""` persis di bawah definisinya). Ini method-nya lumayan panjang, cari BLOK PERSIS ini:

**CARI**:
```python
    def process(self, url: str, num_clips: int = 5, add_captions: bool = True, add_hook: bool = True, portrait: bool = True, highlight_finder: bool = True, yt_title_maker: bool = True):
        """Main processing pipeline"""
        
        # TODO: logic highlight_finder/yt_title_maker belum diimplementasi di core
        
        # Step 1: Download video
        self.set_progress("Downloading video...", 0.1)
        video_path, srt_path, video_info = self.download_video(url)
        
        # Store channel name for credit watermark
        self.channel_name = video_info.get("channel", "") if video_info else ""
        
        if self.is_cancelled():
            return
        
        if not srt_path:
            raise SubtitleNotFoundError(
                f"No subtitle available for language: {self.subtitle_language.upper()}",
                video_path=video_path,
                video_info=video_info
            )
        
        # Step 2: Find highlights
        self.set_progress("Finding highlights...", 0.3)
        transcript = self.parse_srt(srt_path)
        highlights = self.find_highlights(transcript, video_info, num_clips)
        
        if self.is_cancelled():
            return
        
        if not highlights:
            raise Exception("No valid highlights found!")
        
        # Step 3: Process each clip
        total_clips = len(highlights)
        for i, highlight in enumerate(highlights, 1):
            if self.is_cancelled():
                return
            self.process_clip(video_path, highlight, i, total_clips, add_captions=add_captions, add_hook=add_hook, portrait=portrait)
        
        # Cleanup
        self.set_progress("Cleaning up...", 0.95)
        self.cleanup()
        
        self.set_progress("Complete!", 1.0)
        self.log(f"\n✅ Created {total_clips} clips in: {self.output_dir}")
```

**GANTI DENGAN**:
```python
    def process(self, url: str, num_clips: int = 5, add_captions: bool = True, add_hook: bool = True, portrait: bool = True, highlight_finder: bool = True, yt_title_maker: bool = True):
        """Main processing pipeline"""
        
        # TODO: logic highlight_finder/yt_title_maker belum diimplementasi di core
        
        # Step 1: Download video
        self.set_progress("Downloading video...", 0.1)
        video_path, srt_path, video_info = self.download_video(url)
        
        # Store channel name for credit watermark
        self.channel_name = video_info.get("channel", "") if video_info else ""
        
        if self.is_cancelled():
            return
        
        if not srt_path:
            raise SubtitleNotFoundError(
                f"No subtitle available for language: {self.subtitle_language.upper()}",
                video_path=video_path,
                video_info=video_info
            )
        
        # Step 2: Find highlights
        self.set_progress("Finding highlights...", 0.3)
        transcript = self.parse_srt(srt_path)
        highlights = self.find_highlights(transcript, video_info, num_clips)
        
        if self.is_cancelled():
            return
        
        if not highlights:
            raise Exception("No valid highlights found!")
        
        # Step 3: Buat SATU folder untuk video ini, nama dari judul video
        video_title = video_info.get("title", "Untitled Video") if video_info else "Untitled Video"
        folder_name = sanitize_folder_name(video_title)
        video_folder = self.output_dir / folder_name
        suffix = 2
        while video_folder.exists():
            video_folder = self.output_dir / f"{folder_name}-{suffix}"
            suffix += 1
        video_folder.mkdir(parents=True, exist_ok=True)
        
        # Alihkan sementara output_dir ke folder video ini, supaya semua clip
        # dari video ini kebuat DI DALAM folder video (bukan langsung di output/)
        original_output_dir = self.output_dir
        self.output_dir = video_folder
        
        # Step 4: Process each clip
        total_clips = len(highlights)
        try:
            for i, highlight in enumerate(highlights, 1):
                if self.is_cancelled():
                    return
                self.process_clip(video_path, highlight, i, total_clips, add_captions=add_captions, add_hook=add_hook, portrait=portrait)
        finally:
            self.output_dir = original_output_dir
        
        # Step 5: Simpan metadata video (dipakai Jobs panel buat nampilin folder ini)
        video_meta = {
            "title": video_title,
            "url": url,
            "created_at": datetime.now().isoformat(),
            "clip_count": total_clips,
        }
        with open(video_folder / "data.json", "w", encoding="utf-8") as f:
            json.dump(video_meta, f, ensure_ascii=False, indent=2)
        
        # Cleanup
        self.set_progress("Cleaning up...", 0.95)
        self.cleanup()
        
        self.set_progress("Complete!", 1.0)
        self.log(f"\n✅ Created {total_clips} clips in: {video_folder}")
```

**PENTING**: jangan sentuh method `process_clip()` atau `process_selected_highlights()` sama sekali. Fix ini cukup dengan numpang lewat `self.output_dir` — sudah cukup buat bikin semua clip masuk ke dalam `video_folder`.

---

## STEP 3 — `app.py`

Ada 3 edit: 1 fungsi baru (`get_video_folders`), 1 fungsi diganti total (`get_stock_clips`), 1 fungsi baru (`delete_video_folder`).

### 3a. Ganti `get_stock_clips` + tambah `get_video_folders` sebelumnya

**CARI**:
```python
    def get_stock_clips(self):
        """Returns a list of generated clips from the output directory."""
        clips = []
        out_dir = Path(self.output_dir)
        
        if out_dir.exists():
            # Find all JSON metadata files
            for json_file in out_dir.rglob("data.json"):
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        
                    folder_path = json_file.parent
                    video_title = data.get("title", "Unknown Video")
                    
                    # Look for clip metadata
                    clip_meta = data.get("clips", [])
                    if not clip_meta:
                        # Maybe legacy format, scan for mp4s
                        mp4s = list(folder_path.glob("*.mp4"))
                        for i, mp4 in enumerate(mp4s):
                            stat = mp4.stat()
                            clips.append({
                                "id": f"clip_{mp4.stem}",
                                "title": f"Clip {i+1} - {video_title}",
                                "date": stat.st_mtime * 1000,
                                "duration": "00:00", # Need ffprobe to get real duration, mock for now
                                "path": str(mp4),
                                "thumbnail": "", # Could generate a thumbnail here
                            })
                    else:
                        for c in clip_meta:
                            # Verify MP4 exists
                            mp4_path = folder_path / f"clip_{c.get('id', '')}.mp4"
                            if mp4_path.exists():
                                stat = mp4_path.stat()
                                clips.append({
                                    "id": c.get("id", ""),
                                    "title": c.get("hook_text", video_title),
                                    "date": stat.st_mtime * 1000,
                                    "duration": f"00:{int(c.get('duration', 0)):02d}",
                                    "path": str(mp4_path),
                                })
                except Exception as e:
                    print(f"Error parsing {json_file}: {e}")
                    
        # Sort by newest first
        clips.sort(key=lambda x: x.get("date", 0), reverse=True)
        return clips
```

**GANTI DENGAN**:
```python
    def get_video_folders(self):
        """Returns list of video folders (jobs) for the Jobs panel.
        A 'video folder' = direct child of output_dir that has its own data.json
        containing a 'url' key (this is the marker that separates the new
        video-level data.json from the old per-clip data.json format)."""
        folders = []
        out_dir = Path(self.output_dir)

        if out_dir.exists():
            for child in out_dir.iterdir():
                if not child.is_dir():
                    continue
                meta_file = child / "data.json"
                if not meta_file.exists():
                    continue
                try:
                    with open(meta_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                except Exception:
                    continue
                if "url" not in data:
                    # Bukan folder video baru (kemungkinan folder clip lama/legacy), skip
                    continue
                clip_count = len(list(child.glob("*/*.mp4")))
                folders.append({
                    "id": child.name,
                    "title": data.get("title", child.name),
                    "clip_count": clip_count,
                    "date": data.get("created_at", ""),
                    "path": str(child),
                })

        folders.sort(key=lambda f: f.get("date", ""), reverse=True)
        return folders

    def get_stock_clips(self, folder_id=None):
        """Returns a list of clips. If folder_id is given, only returns clips
        inside that video folder. Otherwise returns clips from ALL video folders."""
        clips = []
        out_dir = Path(self.output_dir)

        if not out_dir.exists():
            return clips

        if folder_id:
            target_folders = [out_dir / folder_id]
        else:
            target_folders = [c for c in out_dir.iterdir() if c.is_dir()]

        for video_folder in target_folders:
            if not video_folder.exists() or not video_folder.is_dir():
                continue

            video_meta_file = video_folder / "data.json"
            video_title = video_folder.name
            is_new_format = False

            if video_meta_file.exists():
                try:
                    with open(video_meta_file, 'r', encoding='utf-8') as f:
                        vdata = json.load(f)
                    if "url" in vdata:
                        video_title = vdata.get("title", video_title)
                        is_new_format = True
                except Exception as e:
                    print(f"Error parsing {video_meta_file}: {e}")

            if is_new_format:
                # Struktur baru: tiap clip ada di subfolder video_folder/<timestamp>/
                for clip_json in video_folder.glob("*/data.json"):
                    try:
                        with open(clip_json, 'r', encoding='utf-8') as f:
                            cdata = json.load(f)
                        mp4s = list(clip_json.parent.glob("*.mp4"))
                        if not mp4s:
                            continue
                        mp4_path = mp4s[0]
                        stat = mp4_path.stat()
                        duration_sec = int(cdata.get("duration_seconds", 0))
                        clips.append({
                            "id": clip_json.parent.name,
                            "title": cdata.get("hook_text", cdata.get("title", video_title)),
                            "video_title": video_title,
                            "date": stat.st_mtime * 1000,
                            "duration": f"{duration_sec // 60:02d}:{duration_sec % 60:02d}",
                            "path": str(mp4_path),
                        })
                    except Exception as e:
                        print(f"Error parsing {clip_json}: {e}")
            else:
                # Struktur lama (legacy): folder ini SENDIRI adalah 1 clip
                try:
                    if video_meta_file.exists():
                        with open(video_meta_file, 'r', encoding='utf-8') as f:
                            cdata = json.load(f)
                        mp4s = list(video_folder.glob("*.mp4"))
                        if mp4s:
                            mp4_path = mp4s[0]
                            stat = mp4_path.stat()
                            clips.append({
                                "id": video_folder.name,
                                "title": cdata.get("title", "Unknown Clip"),
                                "video_title": cdata.get("title", "Unknown Clip"),
                                "date": stat.st_mtime * 1000,
                                "duration": "00:00",
                                "path": str(mp4_path),
                            })
                except Exception as e:
                    print(f"Error parsing legacy {video_meta_file}: {e}")

        clips.sort(key=lambda x: x.get("date", 0), reverse=True)
        return clips
```

### 3b. Tambah `delete_video_folder`

**CARI**:
```python
    def delete_job(self, job_id):
        """Delete a job from job history."""
        self.job_history = [j for j in self.job_history if j.get("id") != job_id]
        return {"status": "ok"}
```

**GANTI DENGAN** (fungsi lama TETAP ADA, cuma ditambah fungsi baru di bawahnya — jangan hapus `delete_job`, biarin nganggur, aman):
```python
    def delete_job(self, job_id):
        """Delete a job from job history."""
        self.job_history = [j for j in self.job_history if j.get("id") != job_id]
        return {"status": "ok"}

    def delete_video_folder(self, folder_id):
        """Delete an entire video folder (and every clip inside it)."""
        try:
            target = Path(self.output_dir) / folder_id
            if target.exists() and target.is_dir():
                import shutil
                shutil.rmtree(str(target), ignore_errors=True)
                return {"status": "ok"}
            return {"status": "not_found"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
```

**Jangan ubah** `delete_clip`, `upload_clip`, `play_clip`, `open_output_folder`, `get_dashboard_stats` — semua itu tetap jalan normal tanpa perlu diubah.

---

## STEP 4 — `web/components/stock-clip.js`

File ini GANTI SELURUH ISINYA (bukan search-replace). Hapus semua isi file lama, ganti persis dengan kode di bawah ini.

```javascript
window.Components = window.Components || {};

window.Components.StockClipView = function () {
  const section = document.createElement('section');
  section.className = 'view entrance';
  section.dataset.view = 'stock-clip';

  // Folder video yang lagi dipilih di Jobs panel. null = tampilkan semua ("All Video")
  let selectedFolderId = null;

  // Page header
  const pageHeader = document.createElement('div');
  pageHeader.style.marginBottom = '28px';
  pageHeader.innerHTML = `<h1 class="page-title">Stock Clip</h1><p class="page-subtitle">An easy way to manage clips with care and precision.</p>`;
  section.appendChild(pageHeader);

  // 2-column layout
  const layout = document.createElement('div');
  layout.style.cssText = 'display:grid;grid-template-columns:4fr 8fr;gap:20px;min-height:calc(100vh - 240px);';

  // ── Left: Jobs Panel (= daftar folder video) ──
  const jobsPanel = document.createElement('div');
  jobsPanel.className = 'card';
  jobsPanel.style.cssText = 'display:flex;flex-direction:column;max-height:700px;';

  const jobsHeader = document.createElement('div');
  jobsHeader.className = 'card-header';
  jobsHeader.innerHTML = '<h2 class="card-title">Jobs</h2>';
  jobsPanel.appendChild(jobsHeader);

  const jobsBody = document.createElement('div');
  jobsBody.className = 'card-body';
  jobsBody.style.cssText = 'flex:1;display:flex;flex-direction:column;overflow:hidden;';

  // Filter
  const filterRow = document.createElement('div');
  filterRow.style.cssText = 'display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;';
  filterRow.innerHTML = `
    <select id="stock-campaign-filter" class="select" style="width:auto;min-width:140px;max-width:200px;"><option value="all">Campaign: All</option></select>
    <span id="stock-clips-count" style="font-size:13px;color:var(--text-secondary);font-weight:500;">Clips: 0</span>
  `;
  jobsBody.appendChild(filterRow);

  // Jobs list (video folders)
  const jobsList = document.createElement('div');
  jobsList.style.cssText = 'flex:1;overflow-y:auto;display:flex;flex-direction:column;gap:8px;padding-right:8px;padding-bottom:8px;';
  jobsBody.appendChild(jobsList);

  // Create button
  const createBtnWrap = document.createElement('div');
  createBtnWrap.style.cssText = 'margin-top:14px;padding-top:14px;border-top:1px solid var(--border-light);';
  const createBtn = document.createElement('button');
  createBtn.className = 'btn btn-lime-full';
  createBtn.textContent = 'Create Clip New';
  createBtn.addEventListener('click', () => {
    document.querySelectorAll('.nav-item').forEach(n => {
      n.classList.toggle('active', n.dataset.view === 'create-clip');
    });
    document.querySelectorAll('.view').forEach(v => {
      v.classList.toggle('active', v.dataset.view === 'create-clip');
    });
  });
  createBtnWrap.appendChild(createBtn);
  jobsBody.appendChild(createBtnWrap);

  jobsPanel.appendChild(jobsBody);

  // ── Right: Clips Panel ──
  const clipsPanel = document.createElement('div');
  clipsPanel.className = 'card';
  clipsPanel.style.cssText = 'display:flex;flex-direction:column;max-height:700px;';

  const clipsHeader = document.createElement('div');
  clipsHeader.className = 'card-header';
  clipsHeader.innerHTML = `
    <h2 class="card-title">Clips</h2>
    <div style="display:flex; gap:8px;">
        <select id="upload-platform" class="select" style="width:100px;">
            <option value="tiktok">TikTok</option>
            <option value="youtube">YouTube</option>
            <option value="repliz">Repliz</option>
        </select>
        <select id="upload-account" class="select" style="width:120px; display:none;">
            <option value="">Select Account...</option>
        </select>
        <button id="upload-all-btn" class="btn btn-pill">Upload Semua</button>
    </div>
  `;
  clipsPanel.appendChild(clipsHeader);

  // Clips subheader
  const clipsSub = document.createElement('div');
  clipsSub.style.cssText = 'padding:14px 24px 0 24px;display:flex;justify-content:space-between;align-items:center;font-size:13px;';
  clipsSub.innerHTML = `
    <div id="clips-sub-title" style="flex:1;max-width:400px;height:32px;border:1px solid var(--border-light);border-radius:4px;display:flex;align-items:center;padding:0 12px;color:var(--text-secondary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">
      All Video
    </div>
    <div style="display:flex;gap:16px;color:var(--text-secondary);margin-left:16px;">
      <span id="clips-sub-count">Clips: 0</span>
      <span id="clips-sub-size">Size: 0mb</span>
    </div>
  `;
  clipsPanel.appendChild(clipsSub);

  // Clips list
  const clipsBody = document.createElement('div');
  clipsBody.style.cssText = 'flex:1;overflow-y:auto;padding:20px 24px;display:flex;flex-direction:column;gap:10px;';
  clipsPanel.appendChild(clipsBody);

  layout.appendChild(jobsPanel);
  layout.appendChild(clipsPanel);
  section.appendChild(layout);

  async function refresh() {
    if (!window.pywebview || !window.pywebview.api) return;
    try {
      const stats = await window.pywebview.api.get_dashboard_stats();
      const folders = await window.pywebview.api.get_video_folders();
      const foldersById = {};
      folders.forEach(f => { foldersById[f.id] = f; });

      // Kalau folder yang lagi dipilih ternyata sudah kehapus, reset ke "All"
      if (selectedFolderId && !foldersById[selectedFolderId]) {
        selectedFolderId = null;
      }

      // ── Update Jobs panel (list folder video) ──
      jobsList.innerHTML = '';
      if (folders.length === 0) {
        jobsList.innerHTML = '<div style="padding:16px;color:var(--text-secondary);font-size:13px;">No jobs found.</div>';
      } else {
        folders.forEach(folder => {
          const item = window.FileItem.v2({
            title: folder.title || 'Unknown Video',
            info1: `${folder.clip_count} clip${folder.clip_count === 1 ? '' : 's'}`,
            info2: folder.date ? new Date(folder.date).toLocaleDateString() : '',
            size: '',
            onDelete: async () => {
              if (confirm('Delete this video and all its clips?')) {
                const res = await window.pywebview.api.delete_video_folder(folder.id);
                if (res && res.status === 'ok') refresh();
              }
            }
          });

          item.style.cursor = 'pointer';
          if (selectedFolderId === folder.id) {
            item.style.borderColor = '#8DC63F';
            item.style.boxShadow = '0 0 0 1px #8DC63F';
          }
          item.addEventListener('click', (e) => {
            if (e.target.closest('.fi-btn-del') || e.target.closest('.fi-btn-edit2')) return;
            selectedFolderId = (selectedFolderId === folder.id) ? null : folder.id;
            refresh();
          });

          jobsList.appendChild(item);
        });
      }

      // ── Sync Campaign dropdown dengan daftar folder video ──
      const filterSelect = section.querySelector('#stock-campaign-filter');
      filterSelect.innerHTML = '<option value="all">Campaign: All</option>';
      folders.forEach(f => {
        const opt = document.createElement('option');
        opt.value = f.id;
        opt.textContent = 'Campaign: ' + (f.title.length > 20 ? f.title.substring(0, 20) + '...' : f.title);
        filterSelect.appendChild(opt);
      });
      filterSelect.value = selectedFolderId && foldersById[selectedFolderId] ? selectedFolderId : 'all';
      filterSelect.onchange = () => {
        selectedFolderId = filterSelect.value === 'all' ? null : filterSelect.value;
        refresh();
      };

      // ── Update Clips panel ──
      let clips = await window.pywebview.api.get_stock_clips(selectedFolderId);

      const countEl = section.querySelector('#stock-clips-count');
      if (countEl) countEl.textContent = `Clips: ${clips.length}`;

      const subTitleEl = section.querySelector('#clips-sub-title');
      const subCountEl = section.querySelector('#clips-sub-count');
      const subSizeEl = section.querySelector('#clips-sub-size');
      if (subTitleEl) subTitleEl.textContent = selectedFolderId && foldersById[selectedFolderId] ? foldersById[selectedFolderId].title : 'All Video';
      if (subCountEl) subCountEl.textContent = `Clips: ${clips.length}`;
      if (subSizeEl) subSizeEl.textContent = `Size: ${stats.storageUsed}`;

      // Setup Upload Semua button
      const uploadAllBtn = section.querySelector('#upload-all-btn');
      const platformSelect = section.querySelector('#upload-platform');
      const accountSelect = section.querySelector('#upload-account');

      platformSelect.addEventListener('change', async () => {
          if (platformSelect.value === 'repliz') {
              accountSelect.style.display = 'block';
              accountSelect.innerHTML = '<option value="">Loading...</option>';
              try {
                  const res = await window.pywebview.api.get_repliz_accounts();
                  accountSelect.innerHTML = '<option value="">Select Account...</option>';
                  if (res && res.status === 'ok') {
                      res.accounts.forEach(acc => {
                          const opt = document.createElement('option');
                          opt.value = acc._id;
                          opt.textContent = acc.name + ' (' + acc.type + ')';
                          accountSelect.appendChild(opt);
                      });
                  } else {
                      accountSelect.innerHTML = '<option value="">Failed to load</option>';
                  }
              } catch(e) {
                  accountSelect.innerHTML = '<option value="">Error</option>';
              }
          } else {
              accountSelect.style.display = 'none';
          }
      });

      const newBtn = uploadAllBtn.cloneNode(true);
      uploadAllBtn.parentNode.replaceChild(newBtn, uploadAllBtn);

      newBtn.addEventListener('click', async () => {
         if (clips.length === 0) return;
         const platform = platformSelect.value;
         const accountId = accountSelect.value;

         if (platform === 'repliz' && !accountId) {
             alert('Please select a Repliz account first.');
             return;
         }

         if (!confirm(`Upload ${clips.length} clips to ${platform}?`)) return;

         let success = 0, fail = 0;
         newBtn.textContent = 'Uploading...';
         newBtn.disabled = true;

         for (let c of clips) {
             try {
                const res = await window.pywebview.api.upload_clip(c.path, platform, {title: c.title, account_id: accountId});
                if (res && res.status === 'success') {
                    success++;
                } else {
                    fail++;
                    console.error("Upload failed for", c.title, res?.message);
                }
             } catch(e) {
                fail++;
             }
         }

         newBtn.textContent = 'Upload Semua';
         newBtn.disabled = false;
         alert(`Upload complete!\nSuccess: ${success}\nFailed: ${fail}`);
      });

      clipsBody.innerHTML = '';

      if (clips.length === 0) {
        clipsBody.innerHTML = '<div style="padding:16px;color:var(--text-secondary);font-size:13px;">No clips found.</div>';
      } else {
        clips.forEach(c => {
          const clip = window.FileItem.v3({
            title: c.title,
            info1: 'Durasi: ' + c.duration,
            info2: new Date(c.date).toLocaleDateString(),
            onDelete: async () => {
              if (!confirm('Delete this clip?')) return;
              const res = await window.pywebview.api.delete_clip(c.path);
              if (res && res.status === 'ok') refresh();
            },
            onPlay: async () => {
              await window.pywebview.api.play_clip(c.path);
            },
            onUpload: async () => {
              const platform = platformSelect.value;
              const accountId = accountSelect.value;

              if (platform === 'repliz' && !accountId) {
                  alert('Please select a Repliz account first.');
                  return;
              }

              if (confirm(`Upload this clip to ${platform}?`)) {
                  try {
                      const res = await window.pywebview.api.upload_clip(c.path, platform, {title: c.title, account_id: accountId});
                      if (res && res.status === 'success') {
                          alert('Upload successful!');
                      } else {
                          alert('Upload failed: ' + (res?.message || 'Unknown error'));
                      }
                  } catch (e) {
                      alert('Upload error');
                  }
              }
            }
          });

          const actionsDiv = clip.querySelector('.fi-actions');
          if (actionsDiv) {
              const folderBtn = document.createElement('button');
              folderBtn.className = 'icon-btn';
              folderBtn.innerHTML = '📁';
              folderBtn.title = 'Open Folder';
              folderBtn.style.background = 'none';
              folderBtn.style.border = 'none';
              folderBtn.style.cursor = 'pointer';
              folderBtn.style.fontSize = '16px';
              folderBtn.onclick = () => window.pywebview.api.open_output_folder();
              actionsDiv.appendChild(folderBtn);
          }

          clipsBody.appendChild(clip);
        });
      }

    } catch(e) {
      console.error("Failed to load stock clips", e);
    }
  }

  return { element: section, refresh };
};
```

---

## CARA TEST MANUAL (wajib dijalankan setelah 4 step selesai)

1. Jalankan app (`python app.py` atau cara biasa buka dev build-nya).
2. Generate clip baru dari 1 link video (misal 3 clip).
3. Buka folder `output/` di file explorer. Yang harus kelihatan:
   - 1 folder baru namanya = judul video itu (bukan timestamp).
   - Di dalam folder itu ada `data.json` (isi: title, url, created_at, clip_count) + N subfolder timestamp, masing-masing isi 1 mp4 + 1 data.json.
4. Buka halaman Stock Clip di app:
   - Panel **Jobs** (kiri) harus nampilin 1 item = judul video tadi, dengan info "3 clips".
   - Panel **Clips** (kanan), default (belum klik apa-apa) harus nampilin semua clip dari semua folder video yang ada.
   - Klik item video di Jobs panel → Clips panel harus ke-filter cuma nampilin 3 clip dari video itu aja, dan judul tiap clip beda-beda (bukan "Clip 1" semua).
   - Klik item yang sama lagi → balik ke "All Video".
   - Klik icon trash di item Jobs panel → konfirmasi → folder video + semua clip di dalamnya kehapus dari disk, Jobs panel & Clips panel ke-refresh otomatis.
5. Generate 1 video lagi dengan judul beda → pastikan muncul sebagai folder terpisah, bukan numpuk sama video pertama.

Kalau ada step di atas yang GAGAL, laporkan: nomor step yang gagal + screenshot/isi console error (klik kanan → Inspect → Console) + isi folder `output/` (screenshot file explorer). Jangan coba fix sendiri di luar 4 file yang disebut di atas.

---

## Known Limitation (JANGAN dicoba diperbaiki, ini di luar scope)

Clip-clip yang SUDAH ada sebelum fix ini (folder flat lama, langsung di `output/`) tetap kebaca sama `get_stock_clips()` (masuk kategori "legacy"), tapi TIDAK akan muncul sebagai video folder di Jobs panel (karena `data.json` lama nggak punya key `"url"`). Itu normal, itu data lama dari sebelum fix — nggak perlu dimigrasikan, nggak perlu ditulis ulang. Video baru yang di-generate SETELAH fix ini yang bakal kelihatan bener di Jobs panel.
