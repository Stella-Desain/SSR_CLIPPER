# INSTRUKSI FIX BUG — Migrasi Whisper API → Local Whisper (repo `clip-v2`)

## PERAN KAMU
Kamu adalah AI coding assistant yang bekerja di repo Python ini. Tugasmu **HANYA** mengeksekusi 3 TASK di bawah, **PERSIS** seperti instruksi. Ini bukan sesi refactor/cleanup bebas.

## ATURAN KETAT (WAJIB DIPATUHI)
1. **JANGAN** mengubah file/fungsi/baris apa pun di luar yang disebutkan di TASK.
2. **JANGAN** rename variabel, function, atau class.
3. **JANGAN** menambah dependency baru.
4. **JANGAN** "merapikan" / refactor kode yang tidak diminta, walau menurutmu jelek.
5. Setiap TASK punya blok `CARI` (kode yang harus ditemukan persis) dan `GANTI DENGAN` (kode pengganti). Kalau blok `CARI` **tidak ditemukan persis** di file (beda whitespace, sudah berubah, dsb), **JANGAN menebak/memaksa edit**. Tandai TASK itu sebagai `❌ BLOCKED` di laporan akhir dan jelaskan bedanya.
6. Kerjakan TASK 1 → 2 → 3 secara berurutan. Kalau salah satu gagal, tetap lanjut ke task berikutnya (independen satu sama lain), tapi laporkan semua yang gagal.
7. Setelah semua task selesai, jalankan (jika kamu punya akses eksekusi):
   ```
   python -m py_compile app.py clipper_core.py pages/status_pages.py
   ```
   Ini cuma cek syntax error, bukan test fungsional. Kalau tidak punya akses eksekusi, lewati langkah ini dan katakan begitu di laporan.
8. Di akhir, WAJIB kasih laporan sesuai format di bagian **FORMAT OUTPUT** paling bawah. Jangan cuma bilang "sudah selesai".

---

## TASK 1 (WAJIB — PRIORITAS TERTINGGI) — File: `app.py`

**Masalah:** Dialog fallback "video tanpa subtitle → pakai Whisper (lokal/API)" sudah dibuat (`_show_whisper_fallback_dialog`) tapi **tidak pernah dipanggil**. Alur aktif (`run_find_highlights`) cuma menampilkan pesan error dan berhenti. Akibatnya fitur Local Whisper tidak pernah kepakai untuk video tanpa subtitle.

### TASK 1a — Sambungkan exception handler ke dialog fallback

**CARI** blok ini persis (di dalam method `run_find_highlights`):
```python
            except SubtitleNotFoundError as snf:
                # No subtitle found - can't proceed without video for Whisper
                if self.cancelled:
                    self.after(0, self.on_cancelled)
                    return
                
                self.after(0, lambda: self.on_error(
                    f"No subtitle available for language: {subtitle_lang.upper()}\n\n"
                    "This video doesn't have the selected subtitle.\n\n"
                    "Tips:\n"
                    "1. Go back and select a different subtitle language\n"
                    "2. Try a video that has subtitles available"
                ))
                return
```

**GANTI DENGAN:**
```python
            except SubtitleNotFoundError as snf:
                # No subtitle found - offer Whisper transcription fallback (local or API)
                if self.cancelled:
                    self.after(0, self.on_cancelled)
                    return
                
                self.after(0, lambda: self._show_whisper_fallback_dialog(core, snf, num_clips))
                return
```

### TASK 1b — Perbaiki pengecekan "Caption Maker belum dikonfigurasi" agar sadar mode Local Whisper

Method `_show_whisper_fallback_dialog` saat ini menolak menawarkan fallback kalau API key Caption Maker kosong — padahal kalau user pakai Local Whisper, API key memang sengaja dikosongkan.

**CARI** blok ini persis (di dalam method `_show_whisper_fallback_dialog`):
```python
        # Check if Caption Maker is configured
        ai_providers = self.config.get("ai_providers", {})
        cm_config = ai_providers.get("caption_maker", {})
        cm_api_key = cm_config.get("api_key", "").strip()
        
        if not cm_api_key:
            self.on_error(
                "No subtitle found for this video.\n\n"
                "You can use AI transcription (Whisper API) as a fallback,\n"
                "but Caption Maker is not configured yet.\n\n"
                "Please set it up in:\n"
                "Settings → AI API Settings → Caption Maker"
            )
            return
```

**GANTI DENGAN:**
```python
        # Check if a transcription method is available:
        # Local Whisper enabled, OR Caption Maker API key configured.
        local_whisper_enabled = self.config.get("local_whisper", {}).get("enabled", False)
        ai_providers = self.config.get("ai_providers", {})
        cm_config = ai_providers.get("caption_maker", {})
        cm_api_key = cm_config.get("api_key", "").strip()
        
        if not local_whisper_enabled and not cm_api_key:
            self.on_error(
                "No subtitle found for this video.\n\n"
                "You can use AI transcription (Whisper) as a fallback,\n"
                "but it's not configured yet.\n\n"
                "Please set it up in:\n"
                "Settings → AI API Settings → Caption Maker\n"
                "(enable Local Whisper, or add a Caption Maker API key)"
            )
            return
```

---

## TASK 2 (WAJIB) — File: `clipper_core.py`

**Masalah:** Deteksi otomatis device (`device="auto"`) untuk Local Whisper SELALU jatuh ke `"cpu"`, bahkan di mesin dengan GPU CUDA valid. `ctranslate2.get_supported_compute_types("cuda")` mengembalikan SET TIPE KOMPUTASI (contoh: `{'float32','float16','int8'}`), bukan nama device — jadi string `"cuda"` tidak akan pernah ada di dalamnya.

**CARI** blok ini persis (di dalam method `_load_local_whisper`):
```python
        # Resolve "auto" device
        if device == "auto":
            try:
                import ctranslate2
                device = "cuda" if "cuda" in ctranslate2.get_supported_compute_types("cuda") else "cpu"
            except Exception:
                device = "cpu"
```

**GANTI DENGAN:**
```python
        # Resolve "auto" device
        if device == "auto":
            try:
                import ctranslate2
                device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
            except Exception:
                device = "cpu"
```

---

## TASK 3 (DISARANKAN, RISIKO RENDAH) — File: `pages/status_pages.py`

**Masalah:** Halaman "API Status" mengecek status Caption Maker HANYA lewat `api_key`. Kalau user pakai Local Whisper (API key sengaja kosong), status akan selalu tampil "✗ Not configured" padahal sebenarnya siap pakai.

**CARI** blok ini persis (di dalam nested function `check_status`, method `refresh_status`):
```python
        def check_status():
            from openai import OpenAI
            
            # Get config
            config = self.get_config()
            ai_providers = config.get("ai_providers", {})
            
            # Check each AI provider
            providers_to_check = [
                ("highlight_finder", self.hf_status_label, self.hf_info_label),
                ("caption_maker", self.cm_status_label, self.cm_info_label),
                ("hook_maker", self.hm_status_label, self.hm_info_label),
                ("youtube_title_maker", self.yt_maker_status_label, self.yt_maker_info_label)
            ]
            
            for provider_key, status_label, info_label in providers_to_check:
                provider_config = ai_providers.get(provider_key, {})
                api_key = provider_config.get("api_key", "")
                base_url = provider_config.get("base_url", "https://api.openai.com/v1")
                model = provider_config.get("model", "N/A")
                
                if not api_key:
                    self.after(0, lambda sl=status_label, il=info_label: (
                        sl.configure(text="✗ Not configured", text_color="orange"),
                        il.configure(text="Configure in Settings")
                    ))
                    continue
```

**GANTI DENGAN:**
```python
        def check_status():
            from openai import OpenAI
            
            # Get config
            config = self.get_config()
            ai_providers = config.get("ai_providers", {})
            local_whisper_cfg = config.get("local_whisper", {})
            local_whisper_enabled = local_whisper_cfg.get("enabled", False)
            
            # Check each AI provider
            providers_to_check = [
                ("highlight_finder", self.hf_status_label, self.hf_info_label),
                ("caption_maker", self.cm_status_label, self.cm_info_label),
                ("hook_maker", self.hm_status_label, self.hm_info_label),
                ("youtube_title_maker", self.yt_maker_status_label, self.yt_maker_info_label)
            ]
            
            for provider_key, status_label, info_label in providers_to_check:
                # Caption Maker: if Local Whisper is enabled, it doesn't need an API key.
                if provider_key == "caption_maker" and local_whisper_enabled:
                    model_size = local_whisper_cfg.get("model_size", "large-v3-turbo")
                    self.after(0, lambda sl=status_label, il=info_label, m=model_size: (
                        sl.configure(text="✓ Local Whisper", text_color="green"),
                        il.configure(text=f"Model: {m} (local)")
                    ))
                    continue
                
                provider_config = ai_providers.get(provider_key, {})
                api_key = provider_config.get("api_key", "")
                base_url = provider_config.get("base_url", "https://api.openai.com/v1")
                model = provider_config.get("model", "N/A")
                
                if not api_key:
                    self.after(0, lambda sl=status_label, il=info_label: (
                        sl.configure(text="✗ Not configured", text_color="orange"),
                        il.configure(text="Configure in Settings")
                    ))
                    continue
```

---

## YANG **TIDAK** PERLU/BOLEH DISENTUH SEKARANG
- `add_captions_api()` di `clipper_core.py` (dead code, ada fungsi kembar `add_captions_api_with_progress` yang dipakai) — **JANGAN dihapus**, di luar scope.
- `pages/settings_page_backup.py` — file backup tidak dipakai, **JANGAN diedit/dihapus**.
- Jangan ubah `requirements.txt`.

---

## FORMAT OUTPUT (WAJIB DIISI PERSIS SEPERTI INI)

Untuk **setiap** task, laporkan:

```
### TASK <nomor><sub-huruf jika ada>: <✅ SELESAI | ❌ BLOCKED>
File: <path file>
<Jika BLOCKED: jelaskan kenapa blok CARI tidak ditemukan / bedanya di mana>
<Jika SELESAI: tempel unified diff (format ---/+++/@@) dari perubahan yang benar-benar dilakukan>
```

Di akhir, tambahkan:
```
### RINGKASAN
- File yang diubah: <daftar file>
- File yang TIDAK disentuh selain yang di atas: dikonfirmasi ✅ / ada yang tersentuh ❌ (sebutkan)
- Hasil py_compile: <PASS / FAIL + error / tidak dijalankan (jelaskan kenapa)>
```
