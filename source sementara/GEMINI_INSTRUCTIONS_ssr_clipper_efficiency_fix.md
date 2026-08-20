# INSTRUKSI KERJA — Perbaikan Efisiensi SSR_CLIPPER

**Kamu adalah eksekutor teknis.** Instruksi ini dibuat oleh senior engineer yang SUDAH membaca dan memverifikasi seluruh alur kode secara manual. Semua lokasi, anchor text, dan kode pengganti di bawah **sudah dicek dan dipastikan benar** terhadap kondisi repo saat ini.

## ATURAN KERAS — BACA DULU SEBELUM MULAI

1. **JANGAN improvisasi.** Kerjakan HANYA 5 task yang tercantum di bawah, persis seperti instruksinya. Jangan "sambil membenahi" kode lain yang menurutmu jelek, jangan reformat, jangan rename variabel, jangan tambah komentar baru selain yang diinstruksikan.
2. **JANGAN sentuh file/fungsi di luar yang disebut eksplisit.** Khususnya: **JANGAN** ubah `stabilize_positions()`, `_stabilize_positions_with_activity()`, `_calculate_lip_activity()`, atau logic face-detection di `convert_to_portrait_opencv_with_progress` / `convert_to_portrait_mediapipe_with_progress`. Fungsi-fungsi itu sengaja TIDAK dimasukkan ke task ini (terlalu berisiko untuk dikerjakan tanpa review manual) — abaikan meski kelihatan "bisa dioptimasi juga".
3. **Setiap task punya langkah VERIFIKASI wajib sebelum edit.** Kalau hasil verifikasi tidak cocok dengan yang diharapkan (misal grep menemukan jumlah match yang beda dari yang disebutkan), **STOP total**, jangan lanjut edit, jangan menebak-nebak fix-nya sendiri. Catat di laporan akhir bagian mana yang mismatch, lalu lanjut ke task berikutnya.
4. **Kerjakan task 1 → 5 berurutan**, jangan diacak, karena beberapa anchor text saling bergantung pada urutan file yang belum berubah.
5. Semua task ada di **satu file**: `clipper_core.py` (root project).
6. Setelah **setiap** task selesai (bukan cuma di akhir semua task), jalankan:
   ```
   python3 -m py_compile clipper_core.py
   ```
   Kalau ada `SyntaxError` atau error lain, **JANGAN lanjut ke task berikutnya**. Balikkan (undo) edit task itu saja, catat error persis di laporan, lanjut ke task berikutnya dari kondisi file yang bersih.
7. Untuk mencari teks anchor, gunakan pencarian **exact match** (bukan mirip-mirip). Semua blok kode di bawah ini disalin persis dari file asli — spasi/indentasi harus sama persis.

---

## TASK 1 — Hapus debug print yang nyangkut di hot path

**Alasan:** baris ini mencetak `[DEBUG] ...` ke console SETIAP kali progress bar update (bisa ratusan kali per klip). Jelas debug leftover, tidak berguna di production.

**Verifikasi dulu:**
```
grep -n 'print(f"\[DEBUG\] clip_progress' clipper_core.py
```
Harus muncul **tepat 1 baris**. Kalau tidak, STOP, laporkan.

**Cari (hapus baris ini saja, baris di atas dan bawahnya JANGAN diubah):**
```python
            print(f"[DEBUG] clip_progress: {status} (overall: {overall*100:.1f}%)")
```

**Ganti dengan:** (dihapus total, tidak diganti apa-apa — baris kosong)

**Konteks di sekitarnya (untuk memastikan kamu di tempat yang benar), SEBELUM edit harus terlihat seperti ini:**
```python
            if percent > 0:
                status = f"Clip {index}/{total_clips}: {step_name} ({percent}%)"
            else:
                status = f"Clip {index}/{total_clips}: {step_name}"
            
            print(f"[DEBUG] clip_progress: {status} (overall: {overall*100:.1f}%)")
            self.set_progress(status, overall)
            self._update_clip_state(index, step=step_name, step_progress=(step_num + sub_progress) / total_steps)
```

**Setelah edit harus jadi:**
```python
            if percent > 0:
                status = f"Clip {index}/{total_clips}: {step_name} ({percent}%)"
            else:
                status = f"Clip {index}/{total_clips}: {step_name}"
            
            self.set_progress(status, overall)
            self._update_clip_state(index, step=step_name, step_progress=(step_num + sub_progress) / total_steps)
```

---

## TASK 2 — Hilangkan 3 pemborosan "decode 2x" di probe durasi

**Alasan:** flag `-f null -` bikin ffmpeg decode SELURUH audio/video hanya untuk baca durasi di stderr, padahal file yang sama akan di-decode LAGI di command berikutnya untuk kerjaan aslinya (extract audio / burn caption). Video yang sama jadi di-decode 2x. Cukup pakai `ffmpeg -i <file>` tanpa `-f null -` — ffmpeg tetap print baris `Duration: ...` di stderr dalam waktu instan, tanpa decode penuh. Pola ini SUDAH dipakai dengan benar di fungsi `add_watermark_with_progress` dan `add_credit_watermark_with_progress` di file yang sama — kita cuma menyamakan 3 tempat lain biar konsisten.

**PENTING:** ada JUGA 2 pemakaian `-f null -` lain di file ini (untuk probe durasi file MP3 hasil TTS, satu di dalam fungsi mati `add_hook` yang akan dihapus di Task 3, satu lagi di dalam fungsi aktif `add_hook_with_progress`). **JANGAN sentuh 2 itu** — sengaja dibiarkan, karena file MP3 dari API TTS suka nggak punya header durasi akurat, dan filenya cuma beberapa detik jadi decode-nya murah. Task ini HANYA untuk 4 lokasi spesifik di bawah (bukan 2 itu).

### 2a. Verifikasi dulu:
```
grep -n '"-f", "null", "-"' clipper_core.py
```
Harus muncul **6 baris total** (6 lokasi berbeda di file — 4 yang akan kita fix di task ini, 2 sisanya punya TTS yang sengaja dibiarkan seperti dijelaskan di atas). Kalau bukan 6, STOP, laporkan jumlah yang kamu temukan, jangan lanjut task 2.

### 2b. Lokasi 1 — di dalam fungsi `transcribe_full_video`

**Cari:**
```python
        # Get total audio duration
        probe_cmd = [self.ffmpeg_path, "-i", audio_file, "-f", "null", "-"]
        probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, creationflags=SUBPROCESS_FLAGS)
        duration_match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", probe_result.stderr)
```

**Ganti dengan:**
```python
        # Get total audio duration
        probe_cmd = [self.ffmpeg_path, "-i", audio_file]
        probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, creationflags=SUBPROCESS_FLAGS)
        duration_match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", probe_result.stderr)
```
(Satu-satunya perubahan: hapus `, "-f", "null", "-"` dari list `probe_cmd`. Variabel lain tidak berubah.)

### 2c. Lokasi 2 — di dalam fungsi `add_captions_api_with_progress`, probe pertama (untuk token reporting)

**Cari:**
```python
        # Get audio duration for token reporting
        probe_cmd = [self.ffmpeg_path, "-i", audio_file, "-f", "null", "-"]
        result = subprocess.run(probe_cmd, capture_output=True, text=True, creationflags=SUBPROCESS_FLAGS)
        duration_match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", result.stderr)
        audio_duration = 0
```

**Ganti dengan:**
```python
        # Get audio duration for token reporting
        probe_cmd = [self.ffmpeg_path, "-i", audio_file]
        result = subprocess.run(probe_cmd, capture_output=True, text=True, creationflags=SUBPROCESS_FLAGS)
        duration_match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", result.stderr)
        audio_duration = 0
```

### 2d. Lokasi 3 — di dalam fungsi `add_captions_api_with_progress`, probe kedua (sebelum burn caption)

**Cari:**
```python
        # Get video duration for progress
        probe_cmd = [self.ffmpeg_path, "-i", input_path, "-f", "null", "-"]
        result = subprocess.run(probe_cmd, capture_output=True, text=True, creationflags=SUBPROCESS_FLAGS)
        duration_match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", result.stderr)
        video_duration = 60
        if duration_match:
            h, m, s = duration_match.groups()
            video_duration = int(h) * 3600 + int(m) * 60 + float(s)
        
        encoder_args = self.get_video_encoder_args()
        cmd = [
            self.ffmpeg_path, "-y",
            "-i", input_path,
            "-vf", f"ass='{ass_path_escaped}'",
```

**Ganti dengan:**
```python
        # Get video duration for progress
        probe_cmd = [self.ffmpeg_path, "-i", input_path]
        result = subprocess.run(probe_cmd, capture_output=True, text=True, creationflags=SUBPROCESS_FLAGS)
        duration_match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", result.stderr)
        video_duration = 60
        if duration_match:
            h, m, s = duration_match.groups()
            video_duration = int(h) * 3600 + int(m) * 60 + float(s)
        
        encoder_args = self.get_video_encoder_args()
        cmd = [
            self.ffmpeg_path, "-y",
            "-i", input_path,
            "-vf", f"ass='{ass_path_escaped}'",
```

### 2e. Lokasi 4 — di dalam fungsi `add_hook_with_progress`, probe durasi video utama sebelum concat

**Cari (persis, termasuk komentar):**
```python
        # Get main (input) video duration, just for progress estimation.
        probe_cmd = [self.ffmpeg_path, "-i", input_path, "-f", "null", "-"]
        result = subprocess.run(probe_cmd, capture_output=True, text=True, creationflags=SUBPROCESS_FLAGS)
        duration_match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", result.stderr)
        main_duration = 60
```

**Ganti dengan:**
```python
        # Get main (input) video duration, just for progress estimation.
        probe_cmd = [self.ffmpeg_path, "-i", input_path]
        result = subprocess.run(probe_cmd, capture_output=True, text=True, creationflags=SUBPROCESS_FLAGS)
        duration_match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", result.stderr)
        main_duration = 60
```

### 2f. Verifikasi akhir task 2:
```
grep -n '"-f", "null", "-"' clipper_core.py
```
Sekarang harus tersisa **tepat 2 baris** (2 probe TTS/hook yang memang sengaja dibiarkan — satu di dalam fungsi mati `add_hook` yang baru akan dihapus di Task 3, satu lagi di `add_hook_with_progress`).

---

## TASK 3 — Hapus 3 fungsi mati (dead code, total ±600 baris)

**Alasan:** 3 fungsi ini sudah digantikan versi `_with_progress`-nya dan TIDAK PERNAH dipanggil dari manapun di seluruh project. Sudah dicek manual, dikonfirmasi 0 pemanggil.

### 3a. Verifikasi WAJIB sebelum menghapus apapun — jalankan SEMUA command ini:
```
grep -rn '\badd_hook(' --include="*.py" .
grep -rn '\bconvert_to_portrait_opencv(' --include="*.py" .
grep -rn '\bconvert_to_portrait_mediapipe(' --include="*.py" .
```
**Yang diharapkan:** masing-masing command HANYA menemukan 1 baris, yaitu baris `def` fungsi itu sendiri (bukan pemanggilan/`self.xxx(`). Kalau ada baris lain yang memanggil fungsi tsb (bukan baris `def`), **STOP, JANGAN hapus fungsi itu**, laporkan baris mana yang memanggilnya.

### 3b. Hapus `convert_to_portrait_opencv`

**Cari baris awal (persis):**
```python
    def convert_to_portrait_opencv(self, input_path: str, output_path: str):
```
**Cari baris akhir — batas berhenti (persis, baris ini JANGAN ikut terhapus):**
```python
    def stabilize_positions(self, positions: list) -> list:
```
**Aksi:** hapus semua baris MULAI DARI `def convert_to_portrait_opencv(...)` SAMPAI SEBELUM baris `def stabilize_positions(...)`. Baris `def stabilize_positions` dan semua isinya WAJIB tetap ada (fungsi ini dipakai fungsi lain yang aktif, jangan disentuh).

### 3c. Hapus `convert_to_portrait_mediapipe`

**Cari baris awal (persis):**
```python
    def convert_to_portrait_mediapipe(self, input_path: str, output_path: str):
```
**Cari baris akhir — batas berhenti (persis, baris ini JANGAN ikut terhapus):**
```python
    def _calculate_lip_activity(self, face_landmarks, frame_width, frame_height, prev_lip_distance=None):
```
**Aksi:** hapus semua baris MULAI DARI `def convert_to_portrait_mediapipe(...)` SAMPAI SEBELUM baris `def _calculate_lip_activity(...)`. Baris `def _calculate_lip_activity` dan isinya WAJIB tetap ada (dipakai fungsi lain yang aktif).

### 3d. Hapus `add_hook`

**Cari baris awal (persis):**
```python
    def add_hook(self, input_path: str, hook_text: str, output_path: str) -> float:
```
**Cari baris akhir — batas berhenti (persis, baris ini JANGAN ikut terhapus):**
```python
    def create_ass_subtitle_capcut(self, transcript, output_path: str, time_offset: float = 0, style: str = None):
```
**Aksi:** hapus semua baris MULAI DARI `def add_hook(...)` SAMPAI SEBELUM baris `def create_ass_subtitle_capcut(...)`.

### 3e. Verifikasi akhir task 3:
```
python3 -m py_compile clipper_core.py
grep -c "def convert_to_portrait_opencv(" clipper_core.py
grep -c "def convert_to_portrait_mediapipe(" clipper_core.py
grep -c "def add_hook(" clipper_core.py
```
3 command grep terakhir harus return `0` (fungsinya sudah hilang total), dan `py_compile` harus tanpa error.

---

## TASK 4 — Jangan encode ulang audio yang sudah di-compress (chunk splitting)

**Alasan:** saat file audio hasil ekstraksi terlalu besar dan dipecah jadi beberapa chunk untuk Whisper, kode saat ini men-decode lalu meng-encode ULANG audio yang sudah lossy (mp3 64kbps → mp3 64kbps lagi) untuk tiap chunk. Ini generational loss yang tidak perlu. Solusinya: potong tanpa encode ulang (`-c:a copy`).

**Verifikasi dulu:**
```
grep -n '"-ss", str(chunk_start)' clipper_core.py
```
Harus muncul **tepat 1 baris**. Ini anchor unik untuk memastikan kamu edit blok yang benar — JANGAN pakai grep untuk `"-acodec", "libmp3lame",` saja karena pola itu muncul 4x di file ini untuk keperluan berbeda-beda (WAV→MP3 di fungsi Whisper lokal/API, dll) dan yang lain-lain itu JANGAN disentuh. Task ini HANYA untuk 1 blok spesifik di bawah, yang ada di dalam loop `for i in range(chunk_count):`.

**Cari (persis, termasuk komentar):**
```python
                cmd = [
                    self.ffmpeg_path, "-y",
                    "-ss", str(chunk_start),  # input seek: before -i for fast seeking
                    "-t", str(chunk_duration),
                    "-i", audio_file,
                    "-acodec", "libmp3lame",
                    "-ar", "16000",
                    "-ac", "1",
                    "-b:a", "64k",
                    chunk_file
                ]
```

**Ganti dengan:**
```python
                cmd = [
                    self.ffmpeg_path, "-y",
                    "-ss", str(chunk_start),  # input seek: before -i for fast seeking
                    "-t", str(chunk_duration),
                    "-i", audio_file,
                    "-c:a", "copy",  # audio sudah 16kHz mono 64kbps, tinggal potong tanpa re-encode
                    chunk_file
                ]
```

---

## TASK 5 — Gabung watermark + credit watermark jadi 1 pass FFmpeg (bukan 2)

**Alasan:** saat ini kalau watermark gambar DAN credit text sama-sama aktif, klip di-decode+encode 2x berturut-turut secara terpisah. Bisa digabung jadi 1 `filter_complex` (overlay lalu drawtext) dalam 1 kali encode. Kode di bawah ini SUDAH LENGKAP ditulis — tugasmu HANYA menyisipkan fungsi baru dan mengganti 1 blok pemanggilnya. **Jangan modifikasi isi kode di bawah ini sama sekali**, salin persis.

### 5a. Sisipkan fungsi baru

**Cari titik sisip — baris persis ini (akhir dari fungsi `add_credit_watermark_with_progress`, sekaligus akhir file):**
```python
        if not Path(output_path).exists():
            raise Exception("Failed to apply credit watermark")

    
```

**Ganti dengan (kode lama + fungsi baru setelahnya — perhatikan, ini MENAMBAHKAN kode baru setelah baris yang sudah ada, bukan mengganti isi baris di atas):**
```python
        if not Path(output_path).exists():
            raise Exception("Failed to apply credit watermark")

    def add_watermark_and_credit_with_progress(self, input_path: str, output_path: str, progress_callback):
        """Add image watermark AND credit text in ONE FFmpeg pass (combined
        filter_complex) instead of two sequential full re-encodes. Only
        called from process_clip when BOTH watermark and credit watermark
        are enabled at the same time."""

        watermark_path = self.watermark_settings.get("image_path", "")
        watermark_available = bool(watermark_path) and Path(watermark_path).exists()

        progress_callback(0.1)

        probe_cmd = [self.ffmpeg_path, "-i", input_path]
        result = subprocess.run(probe_cmd, capture_output=True, text=True, creationflags=SUBPROCESS_FLAGS)

        res_match = re.search(r'(\d{3,4})x(\d{3,4})', result.stderr)
        if res_match:
            video_width, video_height = int(res_match.group(1)), int(res_match.group(2))
        else:
            video_width, video_height = 1080, 1920

        duration_match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", result.stderr)
        video_duration = 60
        if duration_match:
            h, m, s = duration_match.groups()
            video_duration = int(h) * 3600 + int(m) * 60 + float(s)

        progress_callback(0.2)

        scale = self.watermark_settings.get("scale", 0.15)
        wm_pos_x = self.watermark_settings.get("position_x", 0.85)
        wm_pos_y = self.watermark_settings.get("position_y", 0.05)
        wm_opacity = self.watermark_settings.get("opacity", 0.8)
        watermark_width = int(video_width * scale)
        wm_x_pixels = int(wm_pos_x * video_width)
        wm_y_pixels = int(wm_pos_y * video_height)

        size = self.credit_watermark_settings.get("size", 0.03)
        cr_pos_x = self.credit_watermark_settings.get("position_x", 0.5)
        cr_pos_y = self.credit_watermark_settings.get("position_y", 0.95)
        cr_opacity = self.credit_watermark_settings.get("opacity", 0.7)
        font_size = int(video_height * size)
        cr_x_pixels = int(cr_pos_x * video_width)
        cr_y_pixels = int(cr_pos_y * video_height)

        credit_text = f"Source: {self.channel_name}"
        credit_text_escaped = credit_text.replace("'", "'\\''").replace(":", "\\:")

        font_file = None
        if sys.platform == "win32":
            windows_fonts = [
                "C:/Windows/Fonts/arial.ttf",
                "C:/Windows/Fonts/segoeui.ttf",
                "C:/Windows/Fonts/tahoma.ttf",
            ]
            for font in windows_fonts:
                if Path(font).exists():
                    font_file = font.replace("\\", "/").replace(":", "\\:")
                    break

        if font_file:
            drawtext_filter = (
                f"drawtext=fontfile='{font_file}':"
                f"text='{credit_text_escaped}':"
                f"fontsize={font_size}:"
                f"fontcolor=white@{cr_opacity}:"
                f"borderw=2:"
                f"bordercolor=black@{cr_opacity}:"
                f"x={cr_x_pixels}-(text_w/2):"
                f"y={cr_y_pixels}-(text_h/2)"
            )
        else:
            drawtext_filter = (
                f"drawtext=text='{credit_text_escaped}':"
                f"fontsize={font_size}:"
                f"fontcolor=white@{cr_opacity}:"
                f"borderw=2:"
                f"bordercolor=black@{cr_opacity}:"
                f"x={cr_x_pixels}-(text_w/2):"
                f"y={cr_y_pixels}-(text_h/2)"
            )

        progress_callback(0.3)

        encoder_args = self.get_video_encoder_args()

        if watermark_available:
            watermark_escaped = watermark_path.replace('\\', '/').replace(':', '\\:')
            filter_complex = (
                f"[1:v]scale={watermark_width}:-1,format=rgba,"
                f"colorchannelmixer=aa={wm_opacity}[wm];"
                f"[0:v][wm]overlay={wm_x_pixels}:{wm_y_pixels}[wmed];"
                f"[wmed]{drawtext_filter}[outv]"
            )
            cmd = [
                self.ffmpeg_path, "-y",
                "-i", input_path,
                "-i", watermark_path,
                "-filter_complex", filter_complex,
                "-map", "[outv]",
                "-map", "0:a",
                *encoder_args,
                "-pix_fmt", "yuv420p",
                "-c:a", "copy",
                "-movflags", "+faststart",
                "-progress", "pipe:1",
                output_path
            ]
            desc = "Apply Watermark + Credit (combined single pass)"
        else:
            self.log("  Warning: Watermark image not found, applying credit text only")
            cmd = [
                self.ffmpeg_path, "-y",
                "-i", input_path,
                "-vf", drawtext_filter,
                *encoder_args,
                "-c:a", "copy",
                "-movflags", "+faststart",
                "-progress", "pipe:1",
                output_path
            ]
            desc = "Apply Credit Only (watermark image missing)"

        self.log_ffmpeg_command(cmd, desc)

        self.run_ffmpeg_with_progress(cmd, video_duration,
            lambda p: progress_callback(0.3 + p * 0.7))

        if not Path(output_path).exists():
            raise Exception("Failed to apply watermark + credit")
```

### 5b. Ganti blok pemanggil di `process_clip`

**Cari blok ini PERSIS (dari komentar `# Step 5:` sampai comment `# Step 6:` beserta isinya, total sampai sebelum `# Mark complete`):**
```python
        # Step 5: Add watermark (if enabled)
        if self.watermark_settings.get("enabled"):
            if self.is_cancelled():
                return
            
            # Check if we need to add watermark step to progress
            if not add_captions:
                # Watermark is a new step
                total_steps += 1
            
            clip_progress("Adding watermark...", current_step, 0)
            
            # Apply watermark to current output
            self.add_watermark_with_progress(str(current_output), str(final_file),
                lambda p: clip_progress("Adding watermark...", current_step, p))
            
            if not final_file.exists():
                raise Exception(f"Failed to create final video with watermark: {final_file}")
            
            self.log("  ✓ Added watermark")
            current_output = final_file
            current_step += 1
            
            # Cleanup temp captioned file if exists
            if add_captions:
                try:
                    temp_captioned = clip_dir / "temp_captioned.mp4"
                    if temp_captioned.exists():
                        temp_captioned.unlink()
                except Exception as e:
                    self.log(f"  Warning: Could not delete temp_captioned.mp4: {e}")
        elif not add_captions:
            # No captions and no watermark, just copy current output to final
            import shutil
            shutil.copy(str(current_output), str(final_file))
            current_output = final_file
        
        # Step 6: Add credit watermark (if enabled)
        if self.credit_watermark_settings.get("enabled") and self.channel_name:
            if self.is_cancelled():
                return
            
            total_steps += 1
            clip_progress("Adding credit...", current_step, 0)
            
            # If current_output is already final_file, we need a temp file
            if str(current_output) == str(final_file):
                temp_credit_input = clip_dir / "temp_before_credit.mp4"
                import shutil
                shutil.copy(str(final_file), str(temp_credit_input))
                current_output = temp_credit_input
            
            self.add_credit_watermark_with_progress(str(current_output), str(final_file),
                lambda p: clip_progress("Adding credit...", current_step, p))
            
            if not final_file.exists():
                raise Exception(f"Failed to create final video with credit: {final_file}")
            
            self.log(f"  ✓ Added credit: Source: {self.channel_name}")
            current_step += 1
            
            # Cleanup temp file
            try:
                temp_credit_input = clip_dir / "temp_before_credit.mp4"
                if temp_credit_input.exists():
                    temp_credit_input.unlink()
            except Exception as e:
                self.log(f"  Warning: Could not delete temp_before_credit.mp4: {e}")
```

**Ganti dengan:**
```python
        # Step 5+6: Add watermark and/or credit watermark (if enabled).
        # If BOTH are enabled, use a single combined FFmpeg pass instead of
        # two separate full re-encodes.
        watermark_on = bool(self.watermark_settings.get("enabled"))
        credit_on = bool(self.credit_watermark_settings.get("enabled") and self.channel_name)

        if watermark_on and credit_on:
            if self.is_cancelled():
                return

            total_steps += 1
            clip_progress("Adding watermark + credit...", current_step, 0)

            self.add_watermark_and_credit_with_progress(str(current_output), str(final_file),
                lambda p: clip_progress("Adding watermark + credit...", current_step, p))

            if not final_file.exists():
                raise Exception(f"Failed to create final video with watermark + credit: {final_file}")

            self.log("  ✓ Added watermark + credit (combined pass)")
            current_output = final_file
            current_step += 1

            if add_captions:
                try:
                    temp_captioned = clip_dir / "temp_captioned.mp4"
                    if temp_captioned.exists():
                        temp_captioned.unlink()
                except Exception as e:
                    self.log(f"  Warning: Could not delete temp_captioned.mp4: {e}")

        elif watermark_on:
            if self.is_cancelled():
                return

            if not add_captions:
                total_steps += 1

            clip_progress("Adding watermark...", current_step, 0)

            self.add_watermark_with_progress(str(current_output), str(final_file),
                lambda p: clip_progress("Adding watermark...", current_step, p))

            if not final_file.exists():
                raise Exception(f"Failed to create final video with watermark: {final_file}")

            self.log("  ✓ Added watermark")
            current_output = final_file
            current_step += 1

            if add_captions:
                try:
                    temp_captioned = clip_dir / "temp_captioned.mp4"
                    if temp_captioned.exists():
                        temp_captioned.unlink()
                except Exception as e:
                    self.log(f"  Warning: Could not delete temp_captioned.mp4: {e}")

        elif credit_on:
            if self.is_cancelled():
                return

            total_steps += 1
            clip_progress("Adding credit...", current_step, 0)

            if str(current_output) == str(final_file):
                temp_credit_input = clip_dir / "temp_before_credit.mp4"
                import shutil
                shutil.copy(str(final_file), str(temp_credit_input))
                current_output = temp_credit_input

            self.add_credit_watermark_with_progress(str(current_output), str(final_file),
                lambda p: clip_progress("Adding credit...", current_step, p))

            if not final_file.exists():
                raise Exception(f"Failed to create final video with credit: {final_file}")

            self.log(f"  ✓ Added credit: Source: {self.channel_name}")
            current_step += 1

            try:
                temp_credit_input = clip_dir / "temp_before_credit.mp4"
                if temp_credit_input.exists():
                    temp_credit_input.unlink()
            except Exception as e:
                self.log(f"  Warning: Could not delete temp_before_credit.mp4: {e}")

        elif not add_captions:
            import shutil
            shutil.copy(str(current_output), str(final_file))
            current_output = final_file
```

### 5c. Verifikasi akhir task 5:
```
python3 -m py_compile clipper_core.py
grep -c "def add_watermark_and_credit_with_progress" clipper_core.py
```
Harus tanpa error, dan grep terakhir harus return `1`.

---

## LAPORAN AKHIR — WAJIB DIISI, format persis seperti ini

Setelah semua task selesai (atau berhenti karena STOP di suatu task), buat laporan dengan format ini, JANGAN diringkas atau diubah formatnya:

```
=== LAPORAN EKSEKUSI ===

Task 1 (hapus debug print): [SELESAI / STOP - alasan: ...]
Task 2 (fix probe -f null -): [SELESAI / STOP - alasan: ...]
  - Lokasi 1 (transcribe_full_video): [OK/GAGAL]
  - Lokasi 2 (token reporting): [OK/GAGAL]
  - Lokasi 3 (sebelum burn caption): [OK/GAGAL]
Task 3 (hapus 3 dead function): [SELESAI / STOP - alasan: ...]
  - convert_to_portrait_opencv: [DIHAPUS / DIBATALKAN karena ada pemanggil: <sebutkan baris>]
  - convert_to_portrait_mediapipe: [DIHAPUS / DIBATALKAN karena ada pemanggil: <sebutkan baris>]
  - add_hook: [DIHAPUS / DIBATALKAN karena ada pemanggil: <sebutkan baris>]
Task 4 (fix audio chunk re-encode): [SELESAI / STOP - alasan: ...]
Task 5 (gabung watermark+credit): [SELESAI / STOP - alasan: ...]
  - Fungsi baru disisipkan: [YA/TIDAK]
  - Blok pemanggil diganti: [YA/TIDAK]

Hasil py_compile TERAKHIR (paste output persis, termasuk kalau kosong/sukses):
<paste di sini>

Jumlah baris clipper_core.py SEBELUM: <angka, dari `wc -l clipper_core.py` sebelum mulai>
Jumlah baris clipper_core.py SESUDAH: <angka, dari `wc -l clipper_core.py` setelah selesai>

Hal yang TIDAK saya lakukan karena ragu/menemukan sesuatu yang tidak sesuai instruksi:
<jelaskan apa adanya, jangan ditutup-tutupi, jangan ambil keputusan sendiri untuk "memperbaiki dengan caramu sendiri">

Perubahan LAIN (di luar 5 task ini) yang saya lakukan:
<HARUSNYA KOSONG. Kalau tidak kosong, jelaskan kenapa kamu menyimpang dari instruksi>
```

**Kirim balik seluruh isi file `clipper_core.py` (atau minimal unified diff-nya) bersama laporan ini**, supaya bisa direview.
