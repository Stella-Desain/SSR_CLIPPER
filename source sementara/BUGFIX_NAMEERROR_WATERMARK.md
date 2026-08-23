# BUG FIX — NameError 'audio_file' + Watermark Hilang

Ini bug lama, peninggalan commit "Efesiensi" paling awal — udah dianalisa mendalam sebelumnya, sekarang baru kejadian di produksi. Root cause 100% pasti, dari baca source langsung.

## Root Cause
Di `clipper_core.py`, fungsi `process_clip()`, ada blok kode "Step 5: Add watermark" dan "Step 6: Add credit watermark" yang KEHAPUS waktu refactor lama, digantikan kode nyasar yang harusnya punya fungsi lain (probe durasi audio). Akibatnya:
1. `audio_file` dipanggil padahal nggak pernah didefinisikan di scope ini → crash `NameError` di SETIAP clip, watermark on ataupun off.
2. Kalau watermark diaktifkan, captions ditulis ke file temporary (`temp_captioned`) tapi nggak pernah ada proses lanjutan yang convert itu jadi `final_file` — watermark mati total.

Project ini bahkan udah punya fungsi gabungan `add_watermark_and_credit_with_progress` (dibikin pas commit yang sama, niatnya efisien gabung watermark+credit jadi 1 ffmpeg pass) yang nganggur nggak pernah dipanggil dari mana pun.

## Aturan Wajib
- Ganti PERSIS sesuai instruksi, jangan improvisasi.
- Setelah fix, WAJIB generate 1 clip dengan watermark OFF dan 1 clip dengan watermark ON, dua-duanya harus selesai tanpa error.

---

## Perubahan 1 — Tambah hitungan step buat progress bar

Cari (sekitar baris 2877-2878):
```python
        if add_captions:
            total_steps += 1
```
Tambahin PERSIS DI BAWAHNYA:
```python
        if self.watermark_settings.get("enabled") or self.credit_watermark_settings.get("enabled"):
            total_steps += 1
```

---

## Perubahan 2 — Perbaiki kondisi gate (sekarang cuma cek watermark, harusnya cek credit juga)

Cari (sekitar baris 3016):
```python
            if self.watermark_settings.get("enabled"):
```
Ganti jadi:
```python
            if self.watermark_settings.get("enabled") or self.credit_watermark_settings.get("enabled"):
```

---

## Perubahan 3 — Hapus kode nyasar, ganti dengan proses watermark yang bener

Cari blok ini PERSIS (sekitar baris 3038-3041):
```python
        # Get total audio duration
        probe_cmd = [self.ffmpeg_path, "-i", audio_file]
        probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, creationflags=SUBPROCESS_FLAGS)
        duration_match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", probe_result.stderr)
```
Ganti SELURUH blok itu jadi:
```python
        # Apply watermark / credit watermark if enabled
        if self.watermark_settings.get("enabled") or self.credit_watermark_settings.get("enabled"):
            if self.is_cancelled():
                return
            clip_progress("Adding watermark...", current_step, 0)
            wm_on = self.watermark_settings.get("enabled")
            credit_on = self.credit_watermark_settings.get("enabled")
            if wm_on and credit_on:
                self.add_watermark_and_credit_with_progress(str(temp_captioned), str(final_file),
                    lambda p: clip_progress("Adding watermark...", current_step, p))
            elif wm_on:
                self.add_watermark_with_progress(str(temp_captioned), str(final_file),
                    lambda p: clip_progress("Adding watermark...", current_step, p))
            else:
                self.add_credit_watermark_with_progress(str(temp_captioned), str(final_file),
                    lambda p: clip_progress("Adding watermark...", current_step, p))

            if not final_file.exists():
                raise Exception(f"Failed to create final video with watermark: {final_file}")

            try:
                if temp_captioned.exists():
                    temp_captioned.unlink()
            except Exception as e:
                self.log(f"  Warning: Could not delete {temp_captioned.name}: {e}")

            self.log("  ✓ Added watermark")
            current_step += 1
```

Catatan: `temp_captioned` di sini merujuk ke variabel yang sama yang udah dibikin di Perubahan 2 (baris ~3017 `temp_captioned = clip_dir / "temp_captioned.mp4"`) — jangan bikin variabel baru, pakai yang udah ada.

---

## FORMAT LAPORAN

| Perubahan | Diff sesuai instruksi? | Bukti test |
|---|---|---|
| 1. total_steps | | |
| 2. Gate condition | | |
| 3. Ganti kode nyasar jadi proses watermark | | |
| Test clip watermark OFF | | |
| Test clip watermark ON | | |
