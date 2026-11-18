# Perbaikan upload dan cara mencoba

Pembaruan: 22 September 2026. Validasi perbaikan ini memakai tes lokal dan respons
HTTP tiruan. Upload nyata diserahkan kepada pengguna; kontrol GUI tidak dijalankan
pada tahap ini.

## Yang diperbaiki

- Payload jadwal Repliz menghilangkan `additionalInfo.music` jika sound native
  platform tidak dipilih. Musik yang sudah dicampur ke video tetap berada pada
  video. Jika sound native diberikan ke adapter, volume video/musik disertakan.
- Storage menerima respons sukses 2xx, termasuk init 201 dan complete 204 tanpa
  body. ID file berasal dari respons init; kegagalan setiap tahap menghentikan
  tahap berikutnya.
- Error mencantumkan tahap, kode HTTP, dan pesan validasi provider yang tersedia.
  Penolakan request yang pasti menjadi **Gagal** dan dapat dicoba lagi secara
  manual. Retry schedule menggunakan URL video yang sudah berhasil diunggah.
- Timeout, HTTP 408/499, kegagalan server, atau respons sukses tanpa ID jadwal
  menjadi **Perlu perhatian**. Sinkronisasi memeriksa jadwal provider terlebih
  dahulu; aplikasi tidak langsung membuat jadwal lain untuk hasil yang belum pasti.
- Ketersediaan zona waktu diperiksa lewat pembacaan data IANA. `tzdata` muncul
  pada Settings dan masuk dependency serta konfigurasi packaging.
- Validasi akun menyebutkan penyebab spesifik: profil belum disimpan, audiens atau
  bahasa berbeda, platform tidak sesuai, koneksi terputus, atau akun tidak tersedia.
  Form profil menyediakan **Gunakan audiens campaign**, diikuti **Simpan profil akun**.
- Preview distribusi menampilkan caption yang benar-benar akan dikirim. Tombol
  **Perbarui** membersihkan pesan error lama dan menampilkan kegagalan terbaru.

## Uji manual oleh pengguna

1. Tutup aplikasi versi yang sedang berjalan, kemudian buka kembali dengan
   lingkungan proyek yang digunakan untuk validasi:

   ```powershell
   py -3.12 app.py
   ```

2. Buka Campaign. Pastikan akun tujuan dipilih dan terhubung. Lingkup audiens akun
   berisi genre/audiens, bukan judul satu clip. Jika akun memang ditujukan untuk
   audiens campaign tersebut, gunakan **Gunakan audiens campaign**, lalu
   **Simpan profil akun**. Simpan campaign jika penugasan atau aturannya berubah.
3. Di **Review & Upload**, pilih clip yang sudah disetujui, lalu
   **Preview distribusi**. Periksa akun, caption, jadwal, dan zona waktu.
4. Tekan **Upload paket ini**. Status **Terjadwal** memerlukan ID jadwal dari
   provider; status **Terbit** baru ditampilkan setelah provider melaporkan sukses.
5. Jika gagal, laporkan pesan error lengkap dan status pada Tracking. Jika
   **Perlu perhatian**, gunakan **Sinkronkan provider** untuk rekonsiliasi.

Jika Settings melaporkan data zona waktu tidak tersedia, instal/perbaiki **tzdata
(zona waktu)** lalu buka ulang aplikasi. Perbaikan ini tidak otomatis mengubah
profil akun tersimpan atau mengirim ulang publikasi lama.

## Cakupan tes

`tests/test_repliz_upload.py` menguji adapter dan workflow dengan database
sementara, termasuk payload tanpa musik, volume nol, init/complete storage,
penolakan HTTP, timeout, respons tanpa ID, retry tanpa upload file kedua,
serta larangan retry saat pengiriman belum pasti. Transport HTTP dimock.
`tests/test_account_eligibility.py` memeriksa validasi profil dan pesan tindak
lanjut. `tests/test_dependencies.py` memeriksa deteksi/perbaikan data zona waktu.

Keberhasilan tes tersebut belum membuktikan upload nyata, izin akun provider,
atau keberhasilan publikasi pada masing-masing platform. Pengujian manual di
atas diperlukan untuk memeriksa integrasi pada akun pengguna.
