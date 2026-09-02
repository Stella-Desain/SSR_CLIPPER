# FIX — Upload Selalu Gagal Total Tanpa Feedback

**File yang diubah:** `app.py` (Bug #1) dan `web/components/stock-clip.js` (Bug #2)
**Sifat perubahan:** 2 fix kecil dan terpisah, tidak saling bergantung. Tidak menyentuh logic lain (SPEC A/B/C sebelumnya TIDAK diubah).

---

## BUG #1 (AKAR MASALAH — WAJIB) — `campaign_id` dibaca dari sumber yang salah

### Lokasi
`app.py`, method `get_stock_clips()`, di dalam cabang "Struktur baru" (`is_new_format`), sekitar baris 1353.

### Masalah
```python
                        clips.append({
                            "id": clip_json.parent.name,
                            "title": cdata.get("hook_text", cdata.get("title", video_title)),
                            "video_title": video_title,
                            "date": stat.st_mtime * 1000,
                            "duration": f"{duration_sec // 60:02d}:{duration_sec % 60:02d}",
                            "path": str(mp4_path),
                            "upload_status": cdata.get("upload_status", "belum_diupload"),
                            "conflict_group_id": cdata.get("conflict_group_id"),
                            "campaign_id": vdata.get("campaign_id")
                        })
```

Baris terakhir salah: `vdata` adalah `data.json` milik VIDEO INDUK (folder luar, isinya cuma `url` & `title` video sumber) — field `campaign_id` **tidak pernah ada di situ**. `campaign_id` yang benar itu ada di `cdata` (data.json milik clip itu sendiri, di folder timestamp di dalamnya) — persis yang dipakai di baris `"conflict_group_id": cdata.get("conflict_group_id")` tepat di atasnya.

### Akibat
`get_stock_clips()` selalu balikin `campaign_id: None` untuk SEMUA clip format baru, walau clip itu sebenarnya dari campaign yang valid. Ini bikin `preview_distribution()` (dipanggil dari tombol Upload) SELALU gagal auto-detect campaign → status `mixed_or_missing_campaign` → `quick_upload()` selalu return `{"status": "error", ...}` → upload gak akan PERNAH jalan untuk clip manapun, walau semua konfigurasi lain (API key, akun, dsb) sudah benar.

### Fix
Ganti baris:
```python
                            "campaign_id": vdata.get("campaign_id")
```
menjadi:
```python
                            "campaign_id": cdata.get("campaign_id")
```

Itu saja. 1 baris. JANGAN ubah baris lain di dict itu, JANGAN ubah cabang "Struktur lama (legacy)" di bawahnya (baris ~1376) — cabang itu SUDAH BENAR (`cdata.get("campaign_id")`), jadi jadi acuan yang benar untuk fix di atas.

---

## BUG #2 — Tidak ada feedback apapun ke user (bahkan saat gagal)

### Lokasi
`web/components/stock-clip.js`, handler `section.querySelector('#distribute-btn').onclick`, sekitar baris 138-165.

### Masalah
```javascript
      try {
          const res = await window.pywebview.api.quick_upload(idsToUpload);
          if (res && res.status === 'ok') {
              selectedClipIds.clear();
              await refresh();
          } else {
              alert('Gagal upload: ' + (res?.message || 'Unknown error'));
              distributeBtn.disabled = false;
              distributeBtn.textContent = originalText;
          }
      } catch (e) {
          alert('Terjadi error saat upload');
          distributeBtn.disabled = false;
          distributeBtn.textContent = originalText;
      }
```

Dua masalah:
1. Kalau SUKSES, tidak ada feedback sama sekali ke user — cuma diam-diam refresh list.
2. Kalau GAGAL, satu-satunya feedback adalah `alert()` bawaan browser — di aplikasi desktop berbasis PyWebView, `alert()`/`confirm()` sering tidak ter-render sama sekali tergantung GUI engine yang dipakai (WebView2/Qt/GTK), sehingga user tidak melihat apa-apa walau proses sudah selesai (gagal).

### Fix
Project ini SUDAH PUNYA pola toast in-app yang benar (tidak pakai `alert()`), ada di `web/components/home.js` (function `showToast`, sekitar baris 415-429):

```javascript
  function showToast(msg, isError = false) {
    const toast = document.createElement('div');
    toast.textContent = msg;
    toast.style.cssText = `
      position: fixed; bottom: 20px; right: 20px; 
      background: ${isError ? '#ef4444' : '#10b981'}; 
      color: white; padding: 12px 24px; border-radius: 8px; 
      font-size: 14px; font-weight: 500; z-index: 9999;
      box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
      transition: opacity 0.3s;
    `;
    document.body.appendChild(toast);
    setTimeout(() => { toast.style.opacity = '0'; }, 2500);
    setTimeout(() => { if (toast.parentNode) toast.parentNode.removeChild(toast); }, 2800);
  }
```

**Langkah:**

1. Copy function `showToast` di atas PERSIS APA ADANYA (tidak diubah sama sekali) ke dalam `stock-clip.js`. Taruh di scope module-level (di luar function komponen manapun, atau di dalam function utama yang me-render halaman Stock Clip — yang penting bisa diakses dari handler `#distribute-btn`).

2. Ganti handler `#distribute-btn` di atas jadi:

```javascript
      try {
          const res = await window.pywebview.api.quick_upload(idsToUpload);
          if (res && res.status === 'ok') {
              selectedClipIds.clear();
              showToast(`${res.total_scheduled} clip berhasil dijadwalkan`);
              await refresh();
          } else {
              showToast('Gagal upload: ' + (res?.message || 'Unknown error'), true);
              distributeBtn.disabled = false;
              distributeBtn.textContent = originalText;
          }
      } catch (e) {
          showToast('Terjadi error saat upload', true);
          distributeBtn.disabled = false;
          distributeBtn.textContent = originalText;
      }
```

3. Cari pemanggilan `quick_upload` yang KEDUA di file yang sama (sekitar baris 275, di handler lain — cek konteksnya, kemungkinan modal/dialog upload per-campaign). Kalau di situ juga ada `alert()`, ganti dengan `showToast` pola yang sama. Kalau di situ TIDAK ada `alert()` sama sekali (tidak ada feedback), tambahkan `showToast` sukses/gagal dengan pola yang sama seperti di atas.

---

## ATURAN KETAT — JANGAN LAKUKAN INI

- JANGAN ubah apapun di `confirm_distribution()`, `preview_distribution()`, `ReplizUploaderAdapter`, `_select_background_sound`, `get_repliz_tiktok_music` — semua itu SUDAH BENAR dari spec sebelumnya, jangan disentuh.
- JANGAN bikin progress panel / UI baru apapun. Scope-nya CUMA 2 fix di atas.
- JANGAN ubah struktur `metadata`/`cdata`/`vdata` di `clipper_core.py` atau bagian lain `app.py`.
- JANGAN ubah cabang "Struktur lama (legacy)" di `get_stock_clips()` — itu sudah benar, jadi acuan.

---

## Cara Test

1. **Test Bug #1:** Setelah fix, panggil `get_stock_clips()` untuk clip yang berasal dari campaign yang valid (format baru) — pastikan field `campaign_id` di hasilnya BUKAN `null`, tapi ID campaign yang benar (cocok dengan campaign yang kelihatan di halaman Campaign).
2. Generate 1 clip baru dari sebuah Campaign yang sudah ada akun terhubung. Buka Stock Clip, pilih clip itu, pencet Upload.
3. Pastikan sekarang **beneran ke-upload** — cek `data.json` clip: `scheduled_uploads` harus ada entry baru dengan status `"sukses"` atau `"gagal"` (bukan lagi selalu `mixed_or_missing_campaign` di response `quick_upload`).
4. **Test Bug #2:** Pastikan muncul toast HIJAU di pojok kanan bawah pas upload sukses (bukan diam-diam), dan toast MERAH pas gagal (misal, test dengan mengosongkan Repliz Secret Key sementara) — pastikan toast ini yang muncul, bukan popup `alert()` browser.
5. Pastikan toast otomatis hilang sendiri setelah ~2.5 detik, tidak menumpuk kalau upload beberapa kali berturut-turut.
