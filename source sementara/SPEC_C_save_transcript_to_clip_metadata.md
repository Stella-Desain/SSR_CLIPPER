# SPEC C — Simpan Transcript ke data.json Setiap Clip

**File yang diubah:** `clipper_core.py` SAJA
**Urutan kerja:** Bisa dikerjakan kapan saja (tidak bergantung ke spec lain). Wajib selesai sebelum SPEC A.
**Sifat perubahan:** Nambah 1 method baru + edit kecil di 2 tempat (thread 1 variable baru). TIDAK mengubah logic AI pencari highlight, TIDAK mengubah proses cutting/portrait/hook/caption/watermark.

---

## Tujuan

Setiap clip yang di-generate saat ini menyimpan `title`, `hook_text`, `description`, dll ke `data.json` — tapi TIDAK menyimpan potongan transcript (dialog/ucapan) dari clip tersebut. SPEC A nanti butuh transcript ini supaya AI bisa milih musik yang cocok berdasarkan ISI OMONGAN di clip, bukan cuma judulnya.

Ada 3 langkah:
1. Tambah 1 method baru: ekstrak potongan transcript sesuai rentang waktu highlight.
2. "Alirkan" (thread) transcript video penuh dari `process()` ke `process_clip()`.
3. Simpan hasil potongan transcript ke `metadata` yang ditulis ke `data.json`.

---

## LANGKAH 1 — Tambah method baru

Cari method `extract_transcript_for_highlight` di `clipper_core.py` (sekitar baris 1552). Method ini SUDAH ADA dan JANGAN DIUBAH SAMA SEKALI — dia baca dari file `.srt` di disk.

Persis SETELAH method `extract_transcript_for_highlight` selesai (baris `return " ".join(lines)`, sebelum `def download_subtitle_only`), tambahkan method BARU ini:

```python
    def extract_transcript_for_highlight_from_text(self, transcript_text: str, highlight: dict) -> str:
        """Sama seperti extract_transcript_for_highlight, tapi input-nya string transcript
        yang sudah ada di memory (bukan path file .srt). Dipakai karena variable `transcript`
        di process() adalah string, bukan file.

        Args:
            transcript_text: string transcript format SRT (hasil parse_srt() atau transcribe_full_video())
            highlight: Dict dengan key start_time dan end_time

        Returns:
            str: Gabungan teks subtitle yang overlap dengan rentang waktu highlight
        """
        if not transcript_text:
            return ""

        pattern = r"(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n(.*?)(?=\n\n|\Z)"
        matches = re.findall(pattern, transcript_text, re.DOTALL)

        start_sec = self.parse_timestamp(highlight["start_time"])
        end_sec = self.parse_timestamp(highlight["end_time"])

        lines = []
        for idx, start, end, text in matches:
            sub_start = self.parse_timestamp(start)
            sub_end = self.parse_timestamp(end)

            if sub_end >= start_sec and sub_start <= end_sec:
                clean_text = text.replace("\n", " ").strip()
                if clean_text:
                    lines.append(clean_text)

        return " ".join(lines)
```

> Catatan: kalau format `transcript_text` ternyata BUKAN format SRT (regex di atas gak match apapun, jadi `matches` kosong), method ini akan balikin string kosong `""` — TIDAK error/crash. Ini sengaja, biar aman (fallback nanti ditangani di SPEC A, bukan di sini).

---

## LANGKAH 2 — Alirkan `transcript` dari `process()` ke `process_clip()`

Di method `process()`, cari closure function `_worker` (sekitar baris 750-761). Kodenya PERSIS seperti ini sekarang:

```python
        def _worker(index, highlight):
            gid = highlight["conflict_group_id"]
            src_path, is_pre_cut = clip_sources[gid]
            self._update_clip_state(index, status="running", step="Starting")
            try:
                self.process_clip(
                    src_path, highlight, index, total_clips,
                    add_captions=add_captions, add_hook=add_hook,
                    portrait=portrait, campaign_id=campaign_id,
                    pre_cut=is_pre_cut,
                    completed_counter=(completed_count, completed_lock, total_clips),
                )
```

Ganti baris `self.process_clip(...)` supaya nambah 1 argumen baru `full_transcript=transcript`. Hasil akhirnya HARUS PERSIS seperti ini:

```python
        def _worker(index, highlight):
            gid = highlight["conflict_group_id"]
            src_path, is_pre_cut = clip_sources[gid]
            self._update_clip_state(index, status="running", step="Starting")
            try:
                self.process_clip(
                    src_path, highlight, index, total_clips,
                    add_captions=add_captions, add_hook=add_hook,
                    portrait=portrait, campaign_id=campaign_id,
                    pre_cut=is_pre_cut,
                    completed_counter=(completed_count, completed_lock, total_clips),
                    full_transcript=transcript,
                )
```

Variable `transcript` di sini adalah variable yang SUDAH ADA di scope `process()` (diisi di Step 2, baris ~636-649, dari `self.parse_srt(srt_path)` atau `self.transcribe_full_video(video_path)`). JANGAN buat variable baru, tinggal pakai yang sudah ada.

---

## LANGKAH 3 — Terima parameter baru di `process_clip()` dan simpan ke metadata

### 3a. Ubah signature method

Cari definisi method (sekitar baris 2872):

```python
    def process_clip(self, video_path: str, highlight: dict, index: int, total_clips: int = 1, add_captions: bool = True, add_hook: bool = True, pre_cut: bool = False, portrait: bool = True, campaign_id: str = None, completed_counter: tuple = None):
```

Ganti jadi (nambah 1 parameter baru `full_transcript: str = None` di akhir):

```python
    def process_clip(self, video_path: str, highlight: dict, index: int, total_clips: int = 1, add_captions: bool = True, add_hook: bool = True, pre_cut: bool = False, portrait: bool = True, campaign_id: str = None, completed_counter: tuple = None, full_transcript: str = None):
```

### 3b. Simpan potongan transcript ke metadata

Cari blok `metadata = {...}` di dalam `process_clip()` (sekitar baris 3122-3138). Kodenya PERSIS seperti ini sekarang:

```python
        # Save metadata
        metadata = {
            "title": highlight["title"],
            "hook_text": highlight.get("hook_text", highlight["title"]),
            "start_time": highlight["start_time"],
            "end_time": highlight["end_time"],
            "duration_seconds": highlight["duration_seconds"],
            "has_hook": add_hook,
            "has_captions": add_captions,
            "has_watermark": self.watermark_settings.get("enabled", False),
            "has_credit": self.credit_watermark_settings.get("enabled", False),
            "channel_name": self.channel_name,
            "campaign_id": campaign_id,
            "virality_score": highlight.get("virality_score"),
            "description": highlight.get("description"),
            "conflict_group_id": highlight.get("conflict_group_id"),
        }
```

Ganti jadi (tambah 1 baris SEBELUM `metadata = {...}` untuk hitung transcript-nya, dan tambah 1 key baru `"transcript"` di dalam dict):

```python
        # Save metadata
        clip_transcript = ""
        if full_transcript:
            try:
                clip_transcript = self.extract_transcript_for_highlight_from_text(full_transcript, highlight)
            except Exception as e:
                self.log(f"  Warning: Gagal extract transcript untuk metadata: {e}")

        metadata = {
            "title": highlight["title"],
            "hook_text": highlight.get("hook_text", highlight["title"]),
            "start_time": highlight["start_time"],
            "end_time": highlight["end_time"],
            "duration_seconds": highlight["duration_seconds"],
            "has_hook": add_hook,
            "has_captions": add_captions,
            "has_watermark": self.watermark_settings.get("enabled", False),
            "has_credit": self.credit_watermark_settings.get("enabled", False),
            "channel_name": self.channel_name,
            "campaign_id": campaign_id,
            "virality_score": highlight.get("virality_score"),
            "description": highlight.get("description"),
            "conflict_group_id": highlight.get("conflict_group_id"),
            "transcript": clip_transcript,
        }
```

---

## ATURAN KETAT — JANGAN LAKUKAN INI

- JANGAN ubah method `extract_transcript_for_highlight` yang lama (yang baca dari file `.srt`). Dia dipakai fitur lain, biarkan apa adanya.
- JANGAN ubah logic AI di `find_highlights()`. Fitur ini gak nyentuh prompt/JSON schema highlight sama sekali.
- JANGAN ubah urutan/isi field lain di dalam `metadata` — cuma NAMBAH 1 key baru `"transcript"` di akhir.
- Kalau `full_transcript` kosong/None (misal ada jalur kode lain yang manggil `process_clip()` tanpa argumen ini), `clip_transcript` HARUS tetap `""` (string kosong), BUKAN error/crash.

---

## Cara Test

1. Generate 1 video baru dari awal (URL apa aja yang ada subtitle-nya).
2. Buka folder output clip yang baru selesai, buka `data.json`-nya.
3. Pastikan ada key `"transcript"` dengan isi teks yang MASUK AKAL — sesuai omongan di rentang waktu `start_time`–`end_time` clip tersebut (bukan string kosong, kecuali videonya memang gak ada dialog di rentang itu).
4. Generate 1 video lagi yang TIDAK ada subtitle YouTube-nya (supaya lewat jalur Whisper transcription) — pastikan `"transcript"` juga terisi dengan benar, bukan error.
