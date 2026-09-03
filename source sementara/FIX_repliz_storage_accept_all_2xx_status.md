# FIX — Init File Balikin 201, Bukan Cuma 200 (Round 2 dari Bug Storage)

**File yang diubah:** `app.py` SAJA — 1 method (`ReplizUploaderAdapter.upload_video_to_storage`)
**Ini LANJUTAN dari fix sebelumnya** (yang benerin Complete File nerima 204). Sekarang ketemu masalah SATU KELAS yang sama, tapi di Step 1 (Init File): API-nya balikin `HTTP 201`, sedangkan kode cuma nerima `200`.

---

## Kenapa ini kejadian

Dokumentasi Repliz nunjukin contoh respons Init File pakai kode `200`. Tapi kenyataannya endpoint ini kadang balikin `201 Created` — masuk akal secara REST, karena Init File itu SECARA HARFIAH membuat resource baru (sebuah upload session/file record), dan `201` adalah kode standar buat "resource baru berhasil dibuat".

Kode SEKARANG di Step 1:
```python
if init_res.status_code != 200:
```
Kode ini SELALU salah kalau API balikin `201` — padahal `201` itu SUKSES, bukan gagal. Efeknya: fungsi langsung `return False` di Step 1, dan **TIDAK PERNAH lanjut ke Step 2 (PUT bytes video ke presigned URL)**. Jadi video-nya kemungkinan besar belum sempat ke-upload beneran — yang ada di Repliz storage kemungkinan cuma placeholder record kosong dari Init File.

Daripada nambal 1 kode spesifik lagi (nanti bisa ketemu variasi lain lagi, sama seperti Complete File yang ternyata 204), sekalian digeneralisasi: **terima semua kode 2xx (200-299) sebagai sukses** di ketiga step (Init, PUT, Complete). Ini standar praktik HTTP — semua kode 2xx artinya sukses, cuma beda nuansa (200 OK, 201 Created, 204 No Content, dst), gak perlu nebak-nebak kode pastinya satu-satu lagi.

---

## TASK 1 — Ganti total isi method `upload_video_to_storage`

Cari method ini di `app.py` (dalam class `ReplizUploaderAdapter`), PERSIS seperti ini SEKARANG (hasil dari fix sebelumnya):

```python
    def upload_video_to_storage(self, file_path):
        """Upload file video ke Repliz Storage pakai 3-step flow resmi:
        Init File -> PUT ke presigned URL -> Complete File.

        Returns:
            (True, public_url)      kalau sukses
            (False, error_message)  kalau gagal di step manapun — error_message berisi
                                     alasan SPESIFIK (HTTP code + pesan dari Repliz kalau ada),
                                     bukan pesan generik.
        """
        import requests
        from requests.auth import HTTPBasicAuth
        import os
        try:
            auth = HTTPBasicAuth(self.access_key, self.secret_key)
            filename = os.path.basename(file_path)
            size = os.path.getsize(file_path)
            mimetype = "video/mp4"

            # Step 1: Init File
            init_res = requests.post(
                "https://api.repliz.com/public/storage/file/init",
                json={"filename": filename, "size": size, "mimetype": mimetype},
                auth=auth,
                timeout=30
            )
            if init_res.status_code != 200:
                try:
                    msg = init_res.json().get("message", f"HTTP {init_res.status_code}")
                except Exception:
                    msg = f"HTTP {init_res.status_code}"
                return False, f"Init File gagal: {msg}"
            init_data = init_res.json()
            file_id = init_data.get("id")
            upload_url = init_data.get("upload")
            public_url = init_data.get("url")
            if not file_id or not upload_url or not public_url:
                return False, "Init File gagal: response tidak lengkap (id/upload/url kosong)"

            # Step 2: PUT raw binary ke presigned URL
            with open(file_path, "rb") as f:
                put_res = requests.put(
                    upload_url,
                    data=f,
                    headers={"Content-Type": mimetype},
                    timeout=300
                )
            if put_res.status_code not in (200, 201, 204):
                return False, f"Upload ke presigned URL gagal: HTTP {put_res.status_code}"

            # Step 3: Complete File
            # PENTING: endpoint ini balikin HTTP 204 No Content kalau SUKSES (BUKAN 200!).
            # Sumber: https://docs.repliz.com/api/storage/complete-file.html
            # Bug lama di sini cuma nerima 200, padahal API selalu balikin 204,
            # jadi upload SELALU dianggap gagal walau sebenarnya sudah sukses.
            complete_res = requests.post(
                f"https://api.repliz.com/public/storage/file/{file_id}/complete",
                auth=auth,
                timeout=30
            )
            if complete_res.status_code not in (200, 204):
                try:
                    msg = complete_res.json().get("message", f"HTTP {complete_res.status_code}")
                except Exception:
                    msg = f"HTTP {complete_res.status_code}"
                return False, f"Complete File gagal: {msg}"

            return True, public_url
        except Exception as e:
            return False, f"Exception saat upload ke storage: {str(e)}"
```

GANTI TOTAL jadi ini:

```python
    def upload_video_to_storage(self, file_path):
        """Upload file video ke Repliz Storage pakai 3-step flow resmi:
        Init File -> PUT ke presigned URL -> Complete File.

        Returns:
            (True, public_url)      kalau sukses
            (False, error_message)  kalau gagal di step manapun — error_message berisi
                                     alasan SPESIFIK (HTTP code + pesan dari Repliz kalau ada),
                                     bukan pesan generik.
        """
        import requests
        from requests.auth import HTTPBasicAuth
        import os
        try:
            auth = HTTPBasicAuth(self.access_key, self.secret_key)
            filename = os.path.basename(file_path)
            size = os.path.getsize(file_path)
            mimetype = "video/mp4"

            # Step 1: Init File
            init_res = requests.post(
                "https://api.repliz.com/public/storage/file/init",
                json={"filename": filename, "size": size, "mimetype": mimetype},
                auth=auth,
                timeout=30
            )
            # PENTING: terima SEMUA kode 2xx sebagai sukses, JANGAN cuma 1 kode spesifik.
            # Dokumentasi Repliz nunjukin contoh "200", tapi di real-world endpoint ini
            # kadang balikin 201 Created (karena secara REST dia memang MEMBUAT resource
            # baru, sebuah upload session). Kalau cuma nerima 200 doang, request yang
            # sebenarnya SUKSES (201) bakal salah dianggap gagal.
            if not (200 <= init_res.status_code < 300):
                try:
                    msg = init_res.json().get("message", f"HTTP {init_res.status_code}")
                except Exception:
                    msg = f"HTTP {init_res.status_code}"
                return False, f"Init File gagal: {msg}"
            init_data = init_res.json()
            file_id = init_data.get("id")
            upload_url = init_data.get("upload")
            public_url = init_data.get("url")
            if not file_id or not upload_url or not public_url:
                return False, "Init File gagal: response tidak lengkap (id/upload/url kosong)"

            # Step 2: PUT raw binary ke presigned URL
            with open(file_path, "rb") as f:
                put_res = requests.put(
                    upload_url,
                    data=f,
                    headers={"Content-Type": mimetype},
                    timeout=300
                )
            # Sama, terima semua 2xx (bukan cuma daftar kode tebakan 200/201/204).
            if not (200 <= put_res.status_code < 300):
                return False, f"Upload ke presigned URL gagal: HTTP {put_res.status_code}"

            # Step 3: Complete File
            # Endpoint ini per dokumentasi resmi balikin 204 No Content kalau sukses
            # (https://docs.repliz.com/api/storage/complete-file.html). Tapi supaya gak
            # kena masalah "kode beda dari dokumentasi" lagi kayak Step 1 barusan, kita
            # gak nebak kode pastinya satu-satu lagi — semua 2xx dianggap sukses.
            complete_res = requests.post(
                f"https://api.repliz.com/public/storage/file/{file_id}/complete",
                auth=auth,
                timeout=30
            )
            if not (200 <= complete_res.status_code < 300):
                try:
                    msg = complete_res.json().get("message", f"HTTP {complete_res.status_code}")
                except Exception:
                    msg = f"HTTP {complete_res.status_code}"
                return False, f"Complete File gagal: {msg}"

            return True, public_url
        except Exception as e:
            return False, f"Exception saat upload ke storage: {str(e)}"
```

**Apa yang berubah:** cuma 3 baris kondisi (`if ... status_code ...`) di Step 1, Step 2, Step 3 — dari cek kode spesifik (`!= 200`, `not in (200, 201, 204)`, `not in (200, 204)`) jadi cek range 2xx (`not (200 <= x < 300)`). Sisanya (parsing response, pesan error, urutan step) **SAMA PERSIS**, tidak ada logic lain yang berubah.

---

## ATURAN KETAT

- JANGAN ubah method lain (`create_schedule`, `confirm_distribution`, `upload_clip`, `_upload_scheduler`) — itu semua sudah benar dari fix sebelumnya, di luar scope fix ini.
- JANGAN ubah urutan atau isi ketiga step (Init → PUT → Complete) — cuma kondisi status code-nya yang berubah.

---

## Cara Test

1. Upload 1 clip lagi dari Stock Clip.
2. Cek `data.json` clip tersebut → `scheduled_uploads` entry terbaru harus `status: "sukses"` dengan `repliz_schedule_id` terisi.
3. Kalau masih ada yang gagal, `error_message`-nya sekarang harus nunjukin step yang BENERAN gagal (bukan cuma soal kode HTTP yang gak dikenali) — kirim isinya balik kalau masih ada masalah.
4. Cek dashboard Repliz (repliz.com → Storage/Files) — pastikan file video yang barusan di-upload statusnya `success` (bukan `pending`), dan di Schedule Content muncul post baru sesuai jadwal.
