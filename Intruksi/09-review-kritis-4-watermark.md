# REVIEW KRITIS #4 — Task 1 Watermark + Residual E1

STATUS: Boleh lanjut ke Task 2 (Credit Watermark) SEKARANG, sambil jawab 2 poin di bawah paralel.

## G1. `browse_watermark_image()` — snippet terpotong, `dest_path` tidak jelas asalnya
Kode yang ditunjukkan:
```python
watermarks_dir.mkdir(parents=True, exist_ok=True)
# ... (logic auto rename counter file lama seperti Python UI)
shutil.copy2(file_path, dest_path)
```
`dest_path` dipakai di `shutil.copy2()` tapi tidak pernah didefinisikan di snippet yang ditunjukkan — cuma ada komentar `# ...`.

Konfirmasi:
- Apakah `# ...` itu cuma disingkat pas nulis laporan (kode aslinya lengkap), atau literally ada di source code?
- Kalau cuma disingkat laporan: tempel kode LENGKAP tanpa dipotong untuk bagian pembuatan `dest_path` (termasuk logic auto-rename counter yang disebut).
- Kalau ternyata literally `# ...` ada di source: itu bug (`NameError: dest_path is not defined`) — perbaiki dulu sebelum lanjut fitur lain yang mirip (Task 2 Credit Watermark kemungkinan butuh browse image juga).

## G2. Wiring tombol "Browse" di UI belum ditunjukkan
Konfirmasi: tombol Browse di panel Watermark sudah punya `onclick`/listener yang manggil `browse_watermark_image()`, lalu hasil `path` dari response dipakai untuk update field read-only path (dan `wmImagePath` yang dipakai di payload save)? Tunjukkan snippet listener-nya.

## G3. (Residual E1) Test button — baru kelihatan untuk OpenAI
Snippet yang ditunjukkan cuma `hfValidateBtn: openai.testBtn`. Task 1 di `04-settings-terputus.md` asalnya minta 3 provider (OpenAI/Anthropic/Gemini). Tunjukkan juga baris mapping untuk Anthropic & Gemini Test button (harusnya ada pola serupa, misal `xxValidateBtn: anthropic.testBtn` dan `xxValidateBtn: gemini.testBtn`) — pastikan ketiganya sudah bind ke tombol asli, bukan cuma OpenAI.

## Lanjut
Silakan kerjakan Task 2 (Credit Watermark) sekarang. Kalau Task 2 juga butuh fitur browse image, terapkan pola yang SAMA dengan Task 1 — tapi pastikan dulu G1 (dest_path) tidak dicopy sebagai bug yang sama ke Task 2. Jawab G1-G3 di laporan Task 2 nanti (gabung boleh, karena ini cuma verifikasi kecil bukan task baru).
