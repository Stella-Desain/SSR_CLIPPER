# Sistem 1 — SSR Template Studio

Editor yang dipilih: **Kdenlive**, repositori resmi https://invent.kde.org/multimedia/kdenlive.
Toolkit ini mengekspor hasil authoring Kdenlive; tidak melakukan fork editor atau mengubah UI Kdenlive.

## Instalasi toolkit

Python 3.10+ diperlukan untuk exporter. Kdenlive hanya diperlukan untuk menyusun template secara visual.

```powershell
python -m pip install ../template_sdk .
```

SDK adalah dependency format bersama. Toolkit dapat didistribusikan sebagai wheel bersama wheel
`ssr-template-engine`; tidak memerlukan source code atau instalasi SSR_CLIPPER.

## Membuat template

1. Pasang Kdenlive dari https://kdenlive.org/download/.
2. Buat project dengan ukuran dan fps hasil yang diinginkan.
3. Taruh satu video contoh pada track sumber, dari frame 0 sampai akhir project, tanpa memotongnya.
   Track audio terpisah dari video contoh boleh digunakan. Seluruh track sumber harus menampilkan
   rentang contoh yang sama. Logo, overlay, warna, dan efek diletakkan pada track/efek lain.
4. Untuk judul dinamis, gunakan efek **Dynamic Text** dengan teks `{{SSR_TITLE}}`.
   Subtitle otomatis SSR tetap dipasang setelah komposisi; pilih Clean, Social, atau Bold saat ekspor.
5. Pilih **Render → Generate Script** untuk mendapatkan **render `.mlt`**. File `.kdenlive`
   adalah project authoring, bukan paket yang dikonsumsi SSR.
6. Ekspor dengan CLI:

```powershell
ssr-template-export render.mlt motivasi.ssrtemplate --source contoh.mp4 --id motivasi --name "Motivasi" --version 1 --subtitle-style bold --source-framing fit
```

7. Impor `motivasi.ssrtemplate` ke campaign SSR_CLIPPER. Editor dan folder project boleh ditutup
   atau tidak berada pada komputer yang menjalankan SSR.

## Batas format v1

- Sumber adalah satu clip lengkap. Durasi source track dan batas akhir komposisi mengikuti clip,
  bukan durasi video contoh. Opening/closing campaign dikerjakan oleh SSR sebelum template diterapkan.
- `fit` mempertahankan frame sumber untuk komposisi editor. `speaker`/`center` memakai preprocessing
  portrait SSR dan saat ini membutuhkan kanvas 9:16; pilih `fit` untuk kanvas lain.
- Efek sepanjang project mengikuti batas akhir clip; posisi keyframe di tengah masih menggunakan
  waktu authoring. Jangan membuat animasi penutup dengan keyframe waktu tetap untuk clip beragam durasi.
- Efek harus ada pada daftar layanan yang didukung SDK **dan** tersedia pada runtime MLT milik SSR.
  Exporter menolak efek yang belum didukung dengan nama layanannya, tanpa menggantinya diam-diam.
- Template mengomposisi visual. SSR mempertahankan audio ucapan dari clip sumber, membuat subtitle,
  lalu memasang musik campaign. Audio tambahan/mix dari timeline authoring tidak digunakan.
- Judul XML Kdenlive, nested project, timewarp, GPU effects, script/QML, proxy, font custom,
  dan asset dari URL belum didukung. Judul dekoratif bisa dirender dulu menjadi gambar/video overlay;
  teks dinamis memakai Dynamic Text dan font yang sudah tersedia di komputer renderer.
- Aset media disalin ke paket dan diperiksa checksum-nya. Paket tidak memuat program editor atau script.
- Untuk mengubah isi template yang sudah diimpor, naikkan `--version`. Job lama mempertahankan versi lama.

Lihat [kontrak format](../docs/TEMPLATE_SYSTEMS.md) untuk arsitektur, rendering dan batas kompatibilitas.
