# Settings — GUI Ada, Program Tidak Ada/Tidak Terhubung
File: `web/components/ai-settings.js`, `web/app.js`

## 1. Tombol "Test" (Open AI / Anthropic / Gemini)
- Lokasi: ai-settings.js:106-114 (`testBtn` per field)
- Status: program ada TAPI salah wiring
- Masalah: `validateAndLoad()` di app.js dipasang ke `dummyBtn` (elemen tersembunyi, tidak pernah di-append ke DOM), BUKAN ke `testBtn` yang user lihat -> tombol visible tidak pernah trigger `validate_api_key`
- Aksi: di ai-settings.js return `fields.hfValidateBtn = openai.testBtn` (dst. untuk cm/hm), hapus `dummyBtn`

## 2. Tombol "Test" Custom Provider
- Lokasi: ai-settings.js:162-164 (`custTestBtn`)
- Status: program tidak ada
- Aksi: wire ke `validate_api_key(custEndpointInput.value, custKeyInput.value)`

## 3. Input Custom Provider (Endpoint & API Key)
- Lokasi: ai-settings.js:151-160
- Status: program tidak ada — elemen tidak dimasukkan ke object `fields`, app.js tidak bisa baca nilainya
- Aksi: tambahkan `custEndpoint`, `custKey` ke return `fields`; masukkan ke payload `save_ai_settings`

## 4. Dropdown "YT Title Maker"
- Lokasi: ai-settings.js:171 (`ytTitle`)
- Status: program tidak ada
- Aksi: tambah key `yt_title_maker` di payload `save_ai_settings` (app.js) DAN di `save_ai_settings()` (app.py) DAN implementasi pemakaiannya di `clipper_core.py`

## 5. Dropdown Whisper Model
- Lokasi: ai-settings.js:29-37 (`whisperModelSelect`)
- Status: program ada sebagian — parameter `local_whisper_settings` sudah ada di `AutoClipperCore.__init__` tapi tidak nyambung end-to-end
- Aksi: (a) baca `whisperModelSelect.value` saat save -> simpan ke config; (b) di `app.py._run()` teruskan `local_whisper_settings={"enabled": value != "api", "model": value}` ke `AutoClipperCore`

## 6. Tombol "Install All"
- Lokasi: ai-settings.js:39-42 (`installBtn`)
- Status: program ada di modul lama (`utils/dependency_manager.py`), tidak diekspos ke WebAPI baru
- Aksi: buat endpoint `install_dependencies()` yang panggil `dependency_manager.py`, wire tombol + progress feedback

## 7. Tombol "Reload Model"
- Lokasi: ai-settings.js:61-65 (`#reload-model-btn`)
- Status: program tidak ada
- Aksi: wire untuk panggil ulang `get_models()` dengan base_url/key aktif, refresh dropdown model

## 8. Dependency status dots (header Settings)
- Lokasi: ai-settings.js:18-23 (`.dep-item`, tidak ada id)
- Status: program ada (`check_dependencies()`) tapi TIDAK dipanggil di halaman ini
- Aksi: tambah `id` per dot, panggil `check_dependencies()` saat init/refresh Settings view, update warna dot

## 9. Panel "Repliz" (Access Key, Secret Key, Test Connection, Connect More, list account)
- Lokasi: ai-settings.js:180-227
- Status: program tidak ada sama sekali — seluruhnya statis/dummy
- Aksi: buat endpoint `save_repliz_credentials(access_key, secret_key)`, `test_repliz_connection()`, `get_repliz_accounts()`, `connect_repliz_account()`; wire semua elemen panel
