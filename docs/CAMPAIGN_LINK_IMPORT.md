# Impor campaign dari link: keputusan untuk jangka panjang

Tanggal riset: 7 Oktober 2026, WITA.

Pilihan produksi saat ini: ambil halaman publik dengan HTTP, baca JSON campaign
yang sudah disertakan di halaman, lalu petakan field secara deterministik. AI
dipakai untuk interpretasi tambahan atau fallback teks halaman. Untuk jangka
panjang, API resmi dengan kontrak dan versi tetap menjadi pilihan utama **jika
tersedia**; belum ada API resmi Clippo yang berhasil diverifikasi dalam riset ini.

## Perbandingan

| Cara | Biaya dan latensi | Perawatan jangka panjang | Keputusan |
| --- | --- | --- | --- |
| API resmi terdokumentasi | Tidak perlu render halaman/AI; biaya mengikuti penyedia | Terbaik bila ada versi, autentikasi resmi, dan pemberitahuan perubahan | Utamakan jika akses resmi tersedia; jangan mengarang endpoint |
| HTTP + JSON bawaan halaman | Satu request halaman, parsing lokal, tanpa token AI | Perlu adapter dan tes karena format internal situs dapat berubah | **Pilihan yang sudah terbukti untuk Clippo saat ini** |
| API internal tanpa dokumentasi | Bisa mengirim payload lebih kecil | Endpoint, cookie, parameter, dan akses bisa berubah tanpa kontrak | Jangan dijadikan fondasi utama hanya karena cepat hari ini |
| HTTP + parsing HTML/teks + AI | Request halaman ditambah biaya/latensi AI | Selektor bisa berubah; hasil AI perlu validasi dan bukti sumber | Fallback untuk halaman publik yang masih berisi brief |
| Browser automation + ekstraksi DOM/network | Menjalankan browser, JavaScript, dan banyak request | Tambahan runtime/browser, login/session, serta pemeliharaan UI | Cadangan untuk sumber yang benar-benar membutuhkan JavaScript; belum ditambahkan ke runtime aplikasi |
| Layanan scraping seperti Firecrawl | Mengurangi pekerjaan menangani banyak situs, tetapi menambah pemakaian layanan | Bergantung pada layanan eksternal, batas penggunaan, dan kualitas ekstraksi | Pertimbangkan bila perlu banyak domain; belum perlu untuk Clippo saja |
| Screenshot + AI/OCR | Membutuhkan render dan analisis gambar | Tautan target, bagian tersembunyi, dan nilai kecil sulit diambil lengkap | Pilihan terakhir untuk dokumen/gambar, bukan jalur utama impor link |

Penilaian selain hasil HTTP di bawah adalah pertimbangan arsitektur, bukan hasil
benchmark langsung semua alternatif. Firecrawl mendukung halaman dinamis dan
hasil terstruktur; dokumentasinya menyebut scraping memakai kredit, dan JSON mode
menambah kredit. [Dokumentasi Firecrawl](https://docs.firecrawl.dev/features/scrape).
Browser seperti Playwright dapat membaca request/response halaman, tetapi itu
tidak menjadikan endpoint internal situs sebuah API resmi.
[Dokumentasi network Playwright](https://playwright.dev/python/docs/network).

## Bukti dari URL pengguna

Sumber: [campaign Bevan](https://app.clippo.id/campaigns/cmtjkbbat06s17t26cxn7lk1k).
Halaman memberikan HTTP 200 tanpa cookie atau login. `initialCampaign` berada
dalam data Next.js Flight. Pembacaan pertama dengan urllib sekitar 0,6 detik;
dengan importer aplikasi sekitar 1,2 detik. Pembacaan ulang dari cache importer
sekitar 0,002 detik. Ini pengamatan beberapa request lokal, bukan SLA atau
persentil latensi. Halaman contoh Ozzaskin juga berhasil diparsing.

Data Bevan yang diambil: judul, durasi 15–180 detik, 5 hashtag, tag akun TikTok
dan Instagram, catatan, angle, persona, tujuan, CTA, 12 Do, 14 Don't, 8 aturan umum,
banner, 12 tautan materi, 2 tautan produk, dan 2 contoh relevan. `campaignHook`
memang kosong, sehingga importer tidak membuat hook baru. Metadata komersial
yang tersedia disimpan sebagai snapshot sumber, bukan sebagai pengaturan upload.

`audience_scope` bukan field asli Clippo. Untuk campaign yang dibuat dalam tugas
ini, lingkup “Crypto dan memecoin” ditambahkan setelah membaca persona/brief,
dengan provenance yang menyatakan bahwa nilai tersebut adalah interpretasi.

## Yang sudah diimplementasikan

- Adapter terpisah di `services/campaign_links.py`, tanpa dependency browser baru.
- Input link dalam Brief & aset campaign; paste URL tunggal dalam textarea juga
  memicu impor otomatis. Tombol Muat ulang link meminta validasi ulang sumber.
- Pemetaan field, tag per platform, rich text Quill/HTML, dan banner.
- Decoder JSON tanpa `eval`; menangani chunk Flight terpisah, referensi JSON,
  serta referensi teks dengan panjang UTF-8. Tidak bergantung pada hash file JS.
- Validasi host, HTTPS, path dan ID campaign. Tidak mengikuti redirect/login.
  Timeout koneksi/baca dan batas respons 2 MB mencegah request tak terbatas.
- Cache memori 5 menit, maksimal 32 snapshot; memakai ETag/Last-Modified bila
  disediakan server. Snapshot campaign yang disimpan tetap tersimpan di config
  dan SQLite. Cache request tidak bertahan setelah aplikasi ditutup.
- Provenance URL/metode, pemeriksaan perbedaan nilai, dan perlindungan terhadap
  hasil request lama ketika user pindah campaign atau mengedit form.
- Tautan bahan, produk, dan referensi tersimpan; aset wajib harus dihubungkan
  dengan file lokal berstatus wajib sebelum campaign dianggap siap produksi.
- JSON langsung tidak memerlukan provider AI. Jika struktur hilang tetapi
  halaman publik masih memiliki brief, fallback teks memakai Brief Extractor
  yang sudah dikonfigurasi dan menandai hasil sebagai parsial.
- Schema/identitas yang tidak cocok berhenti dengan pesan yang bisa diperiksa.
  Jika bagian aturan umum atau enum platform berubah, importer menampilkan
  peringatan; ia tidak menebak nilai yang belum dikenali.

Tautan folder Drive bukan file lokal. Importer tidak mengunduh seluruh folder,
video panjang, atau menjalankan link produk. Download materi adalah tahap
terpisah agar pengisian brief tetap cepat dan file wajib tidak dianggap tersedia
hanya karena URL-nya ditemukan.

Next.js menjelaskan bahwa payload RSC membawa hasil render dan props untuk
komponen client. Bentuk Flight adalah detail internal, sehingga adapter ini
tetap membutuhkan pemeliharaan; ia tidak memiliki kontrak API Clippo.
[Dokumentasi Next.js](https://nextjs.org/docs/app/getting-started/server-and-client-components).
Conditional requests dapat menghemat transfer saat server mendukung validator
dan mengembalikan 304.
[Dokumentasi HTTP conditional requests](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/Conditional_requests).

## Rencana ketika sumber bertambah

1. Tambahkan adapter per penyedia dengan keluaran schema yang sama. API resmi
   menggantikan transport Clippo tanpa mengganti form atau alur review.
2. Untuk perubahan aturan, impor ulang ke draft dan bandingkan dengan snapshot
   tersimpan. Jangan mengubah job/campaign version yang sudah dipakai produksi.
3. Tambahkan fixture setiap bentuk schema yang benar-benar ditemukan, lalu
   jalankan tes parsing, mapping, validasi ID, dan konflik sebelum rilis adapter.
4. Ukur waktu request, cache hit, field kosong, dan gagal parsing tanpa mencatat
   API key/cookie atau identitas admin yang tidak diperlukan.
5. Baru pertimbangkan browser atau layanan scraping ketika pengujian sumber
   tertentu membuktikan HTTP tidak mencukupi. Penggunaan API resmi dan opsi
   fallback tersebut belum tersedia sebagai fitur otomatis dalam perubahan ini.

## Campaign yang dibuat dan validasi

Campaign lokal: `camp_a0ad79a3ee99`, status draft. Brief Bevan tersimpan dalam
`config.json` dan `workflow.sqlite3`, beserta snapshot versi. Ekspor tanpa
konfigurasi rahasia ada di `output/campaign_imports/BEVAN_PRAMUDITO.campaign.json`.
Campaign dan konfigurasi sebelumnya diperiksa tetap sama.

Penutup disetel wajib selama 10 detik mengikuti brief. Produksi masih memerlukan
file FOOTAGE CTA WAJIB dan pemeriksaan kontradiksi antara angle perbandingan
dengan trader lain dan larangan perbandingan. Publikasi memerlukan akun tujuan.
Campaign tidak menjalankan proses video atau publikasi saat disimpan.

Validasi: 18 tes khusus importer lulus; 40 tes frontend lulus; 35 tes regresi
workflow/preset/tag dan tes campaign highlight/musik terkait juga lulus. Pengujian
live HTTP berhasil pada dua campaign. Provider Brief Extractor tersimpan gagal
karena origin DNS saat dicoba; JSON importer tetap berfungsi tanpa provider itu.
Belum dilakukan build EXE atau verifikasi visual pada native WebView.

Tes utama:

```powershell
py -3.12 -m unittest discover -s tests -p test_campaign_links.py
# Frontend memerlukan linkedom pada NODE_PATH lingkungan pengujian.
node --test tests/frontend_workflow.test.cjs tests/frontend_highlight_profiles.test.cjs
```
