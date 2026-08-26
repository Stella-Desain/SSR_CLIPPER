# SPEC B — Fetch Trending TikTok Music dari Repliz

**File yang diubah:** `app.py` SAJA
**Urutan kerja:** Bisa dikerjakan kapan saja (tidak bergantung ke spec lain). Wajib selesai sebelum SPEC A.
**Sifat perubahan:** Additive only — nambah 1 method baru. Tidak mengubah method lain, tidak menghapus apapun.

---

## Tujuan

Nambah 1 method baru di class `WebAPI` (file `app.py`) yang manggil endpoint Repliz:

```
GET https://api.repliz.com/public/tiktok/music
```

untuk ambil daftar musik trending TikTok, biar bisa dipakai spec lain (SPEC A) buat nentuin musik yang di-attach ke post TikTok.

---

## Konteks (biar paham, TIDAK PERLU diubah)

Di `app.py` sudah ada pola auth Repliz yang persis sama, di method `get_repliz_accounts()`. Method baru ini HARUS ikut pola yang SAMA PERSIS (`HTTPBasicAuth`, struktur try/except, format return).

Cari method `get_repliz_accounts` di `app.py` (ada di dalam class `WebAPI`). Persis SETELAH method itu selesai (setelah baris `return {"status": "error", "message": str(e)}` yang menutup `get_repliz_accounts`), tambahkan method baru di bawah ini.

---

## Kode yang harus ditambahkan

Tempel PERSIS kode ini sebagai method baru di dalam class `WebAPI`, tepat setelah `get_repliz_accounts`:

```python
    def get_repliz_tiktok_music(self, genre="ALL", country_code="ID", date_range="7DAY"):
        """Fetch daftar musik trending TikTok dari Repliz.

        Args:
            genre: kategori genre musik, default "ALL" (lihat dokumentasi Repliz untuk daftar genre valid)
            country_code: ISO country code, default "ID"
            date_range: salah satu dari "1DAY", "7DAY", "30DAY", "90DAY", default "7DAY"

        Returns:
            {"status": "ok", "tracks": [ {id, artist, name, thumbnail, duration, url}, ... ]}
            atau
            {"status": "error", "message": "..."}
        """
        try:
            cfg = self._get_cfg()
            repliz_cfg = cfg.get("repliz", {})
            access_key = repliz_cfg.get("access_key")
            secret_key = repliz_cfg.get("secret_key")

            if not access_key or not secret_key:
                return {"status": "error", "message": "Repliz keys not configured"}

            import requests
            from requests.auth import HTTPBasicAuth
            url = "https://api.repliz.com/public/tiktok/music"
            params = {
                "genre": genre,
                "countryCode": country_code,
                "dateRange": date_range
            }

            response = requests.get(
                url,
                params=params,
                auth=HTTPBasicAuth(access_key, secret_key),
                timeout=15
            )

            if response.status_code == 200:
                data = response.json()
                docs = data.get("docs", [])
                tracks = [
                    {
                        "id": d.get("id"),
                        "artist": d.get("artist"),
                        "name": d.get("name"),
                        "thumbnail": d.get("thumbnail"),
                        "duration": d.get("duration"),
                        "url": d.get("url")
                    }
                    for d in docs
                ]
                return {"status": "ok", "tracks": tracks}
            else:
                error_msg = f"HTTP {response.status_code}"
                try:
                    error_msg = response.json().get("message", error_msg)
                except Exception:
                    pass
                return {"status": "error", "message": error_msg}
        except Exception as e:
            return {"status": "error", "message": str(e)}
```

---

## ATURAN KETAT — JANGAN LAKUKAN INI

- JANGAN ubah `get_repliz_accounts`, `test_repliz_connection`, atau method Repliz lain yang sudah ada.
- JANGAN tambahkan tombol/UI apapun di frontend (`web/`) untuk fitur ini. Method ini HANYA dipanggil dari backend Python nanti oleh SPEC A, bukan dari JavaScript.
- JANGAN ubah nama method (`get_repliz_tiktok_music`) — nama ini dipakai persis oleh SPEC A.
- JANGAN ubah nama field di dalam dict `tracks` (`id`, `artist`, `name`, `thumbnail`, `duration`, `url`) — nama ini dipakai persis oleh SPEC A.

---

## Cara Test

1. Pastikan Repliz Access/Secret Key sudah diisi di Settings.
2. Panggil `get_repliz_tiktok_music()` tanpa argumen (pakai default) dari Python console/debug — harus balikin `{"status": "ok", "tracks": [...]}` dengan minimal 1 track.
3. Coba dengan `country_code` yang aneh/tidak valid — harus balikin `{"status": "error", "message": "..."}` tanpa aplikasi crash.
4. Cek: setiap item di `tracks` punya 6 field (`id`, `artist`, `name`, `thumbnail`, `duration`, `url`), tidak ada field tambahan/kurang.
