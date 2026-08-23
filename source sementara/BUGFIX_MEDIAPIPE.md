# BUG FIX — DEPENDENCY VERSION BREAKING CHANGE

Sudah diverifikasi ulang analisa Gemini + dicek semua dependency lain buat pola yang sama. Hasil: cuma `mediapipe` yang beneran broken. Yang lain aman, sudah dicek satu-satu.

## Aturan Wajib
- Cuma ubah yang disebut di sini.
- Setelah fix, WAJIB test: generate 1 clip pakai Portrait + Face Tracking mode MediaPipe, pastikan nggak muncul error `module 'mediapipe' has no attribute 'solutions'` lagi.

---

## FIX — mediapipe (satu-satunya yang broken, koreksi sedikit dari analisa Gemini)

**Klaim Gemini "solutions dihapus total di versi 1.0.0" itu kurang presisi** — sudah dicek langsung: `mediapipe==0.10.14` MASIH punya `mp.solutions` (aman), tapi `mediapipe==0.10.33` ke atas (dan tentu 1.0.x) SUDAH TIDAK PUNYA `mp.solutions` sama sekali. Jadi breaking change-nya kejadian lebih awal dari yang diklaim, di suatu titik antara 0.10.14 dan 0.10.33 — bukan pas nyampe 1.0.0. Fix akhirnya tetap sama kayak saran Gemini, cuma alasannya dikoreksi.

**Perubahan di `requirements.txt`:**

Cari baris:
```
mediapipe>=0.10.0
```
Ganti jadi:
```
mediapipe==0.10.14
```

**Setelah ganti, install ulang:**
```
pip uninstall mediapipe -y
pip install -r requirements.txt
```

Nggak perlu ubah kode apapun di `clipper_core.py` — pattern `mp.solutions.face_mesh` dan `mp.solutions.drawing_utils` yang sudah ada di situ tetap valid buat versi 0.10.14.

---

## HASIL AUDIT DEPENDENCY LAIN (sudah dicek, semua di `requirements.txt` pakai `>=` longgar sama kayak mediapipe, jadi berpotensi kena pola yang sama)

Sudah dicek satu-satu, dites langsung install versi terbaru yang beneran ke-resolve dari `>=` yang ada sekarang, dicocokin ke fungsi yang dipanggil di kode:

- `openai>=1.0.0` → versi terbaru sekarang 3.x. Sudah dites: `from openai import OpenAI, APIConnectionError, RateLimitError, APIStatusError` (dipakai di `clipper_core.py`) masih jalan normal, `.chat.completions.create()` dan `.audio.speech.create()` (yang dipakai di kode) juga masih valid. AMAN, nggak perlu diubah.
- `faster-whisper>=1.0.0` → parameter yang dipake di `WhisperModel(model_size, device=device, compute_type=compute_type)` (`clipper_core.py` baris ~2331) masih cocok sama signature versi terbaru. AMAN.
- `opencv-python>=4.8.0` → fungsi yang dipake (`VideoCapture`, `VideoWriter`, `VideoWriter_fourcc`, `resize`, `CascadeClassifier`) semuanya API inti OpenCV yang stabil, nggak ada yang deprecated/dihapus. AMAN.
- `numpy>=1.24.0` → dicek, kode nggak pakai alias lama yang udah dihapus (`np.float`, `np.int`, `np.bool`, dll — ini yang biasanya jadi korban breaking change numpy 2.0). AMAN.

**Kesimpulan: cuma mediapipe yang perlu difix. Jangan ubah versi library lain.**

---

## SARAN TAMBAHAN (opsional, minta approval dulu sebelum eksekusi — JANGAN langsung dikerjain)

Semua dependency di `requirements.txt` pakai `>=` tanpa batas atas. Ini yang bikin bug mediapipe ini kejadian — install baru di komputer manapun bakal narik versi terbaru yang belum tentu kompatibel. Kalau mau, ke depannya semua baris di `requirements.txt` bisa di-pin ke versi PERSIS yang udah diverifikasi jalan (bukan `>=`, tapi `==`), biar install di komputer lain nggak tiba-tiba dapet versi baru yang breaking. Ini di luar scope fix mediapipe sekarang — jangan dikerjain kecuali saya minta eksplisit.

## FORMAT LAPORAN

| Item | Aksi | Bukti |
|---|---|---|
| mediapipe pin 0.10.14 | Fixed | (hasil generate clip Portrait+MediaPipe sukses tanpa error) |
