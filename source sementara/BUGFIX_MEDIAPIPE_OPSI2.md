# FIX MEDIAPIPE — OPSI 2 (Venv Python 3.12 + Pin Versi)

Sudah disimulasikan penuh: install `mediapipe==0.10.14` bareng SEMUA dependency lain di `requirements.txt` pakai Python 3.12, hasilnya bersih tanpa konflik. Tinggal eksekusi langkah di bawah persis, nggak ada kode yang perlu diubah sama sekali — cuma environment & satu baris `requirements.txt`.

## Aturan Wajib
- Jangan ubah kode apapun di `clipper_core.py`, `app.py`, atau file lain manapun.
- Jangan pin/ubah versi library lain di `requirements.txt` selain mediapipe.

---

## STEP 1 — Cek Python 3.12 sudah terinstall di mesin atau belum

Buka Command Prompt, jalankan:
```
py -0
```
Ini nunjukin semua versi Python yang ke-install di Windows. Cari apakah ada `3.12` di daftarnya.

**Kalau ADA 3.12** → lanjut ke STEP 2.

**Kalau BELUM ADA** → download installer Python 3.12 dari `https://www.python.org/downloads/release/python-3120/` (pilih "Windows installer (64-bit)"), install seperti biasa (centang "Add python.exe to PATH" pas instalasi). Setelah install, ulangi `py -0` buat pastiin `3.12` sekarang muncul di daftar.

---

## STEP 2 — Bikin virtual environment baru khusus pakai Python 3.12

Di folder root project (tempat `requirements.txt` berada), jalankan:
```
py -3.12 -m venv .venv312
```
Ini bikin folder `.venv312` baru, terpisah dari `.venv` lama (yang masih pakai Python 3.14). JANGAN hapus `.venv` lama dulu — biarin dua-duanya ada sampai `.venv312` kebukti jalan.

---

## STEP 3 — Ganti baris di `requirements.txt`

Cari baris:
```
mediapipe>=0.10.0
```
Ganti jadi:
```
mediapipe==0.10.14
```

---

## STEP 4 — Install semua dependency ke venv baru

```
.\.venv312\Scripts\python -m pip install --upgrade pip
.\.venv312\Scripts\python -m pip install -r requirements.txt
```

---

## STEP 5 — Verifikasi mediapipe jalan bener

```
.\.venv312\Scripts\python -c "import mediapipe as mp; from mediapipe.python.solutions import face_mesh; print('OK, solutions tersedia:', hasattr(mp, 'solutions'))"
```
Harus muncul `OK, solutions tersedia: True` tanpa error. Kalau ada error di sini, STOP — jangan lanjut, laporin full error message-nya.

---

## STEP 6 — Test generate clip beneran

Jalankan aplikasi pakai venv baru:
```
.\.venv312\Scripts\python app.py
```
Generate 1 clip dengan Portrait mode ON + Face Tracking mode MediaPipe ON. Pastikan:
- Nggak muncul error `module 'mediapipe' has no attribute 'solutions'`.
- Clip berhasil selesai sampai akhir.

---

## STEP 7 — Kalau semua sukses, jadiin venv ini yang utama

Setelah STEP 6 kebukti sukses, ganti semua script/shortcut yang sebelumnya manggil `.\.venv\Scripts\python` jadi `.\.venv312\Scripts\python` (termasuk kalau ada di `build_exe.bat` atau file build lain buat proses packaging exe). `.venv` lama (Python 3.14) boleh dihapus setelah ini, tapi tunggu konfirmasi dari saya dulu sebelum hapus.

## FORMAT LAPORAN

| Step | Status | Bukti |
|---|---|---|
| Python 3.12 tersedia | | |
| Venv baru dibuat | | |
| requirements.txt diupdate | | |
| Install bersih (no error) | | |
| mp.solutions terverifikasi | | |
| Generate clip sukses | | |
