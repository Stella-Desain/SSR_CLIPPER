# Audit frontend aktual — SSR_CLIPPER

Tanggal audit: 24 September 2026. Audit statis kode frontend; tanpa menjalankan aplikasi, GUI, akun, upload, atau API produksi. Tujuannya mendukung dokumentasi user flow dan inventaris fitur, bukan mengubah produk.

## 1. Mana UI yang benar-benar aktif

- Menu utama: **Dashboard, Campaign, Create Clip, Review & Upload, Settings**. Edit Campaign merupakan subhalaman dari Campaign. Sumber: `web/components/header.js:28`, `web/app.js:26`.
- `web/index.html:56` memuat komponen lama lalu `components/workflow-review.js`, kemudian `app.js`. Karena keduanya mendefinisikan `Components.StockClipView`, **workflow-review.js menimpa stock-clip.js sebelum view dibuat**. Inventaris flow sekarang harus memakai workflow-review.js; fitur lama pada stock-clip.js tidak otomatis masih dapat dijangkau.
- `campaigns.js` masih menangani daftar campaign, field brief dinamis, banner, pembukaan form dasar, shortcut. `campaign-workspace.js` kemudian membungkus `openCampaignEdit` dan **mengganti tombol Save/extract/file-picker** agar hanya handler baru yang berjalan. Sumber: `web/campaign-workspace.js:190`, `:208`, `:221`.
- `workflow-source.js` menambahkan tombol MP4 dan ringkasan template campaign pada Create Clip.
- Global search, wallet, notifikasi, serta halaman Credit disembunyikan/tidak diimplementasi. User header adalah `Local User`. Ini bukan fitur aktif. Sumber: `web/components/header.js:35`, `:101`.

## 2. Peta halaman dan alur navigasi aktual

```text
Dashboard
├─ ringkasan campaign/akun/clip/dependency/job
├─ Restock Clip / tombol pekerjaan → Create Clip
├─ klik file clip/job → folder output (bukan detail review)
└─ Repliz Dashboard → website Repliz

Campaign
├─ Create Campaign → Edit Campaign kosong
├─ klik kartu → Edit Campaign tersimpan
├─ hapus → konfirmasi → hapus campaign
└─ Stok ATAU Upload → Review & Upload, filter campaign, tab Review clip

Edit Campaign
├─ brief/manual dan/atau multi-file → Baca brief dengan AI → periksa konflik
├─ template aktif + bobot → konfigurasi produksi
├─ pilih akun → Save Campaign
├─ jam/batas per akun → Simpan jadwal akun (save terpisah)
├─ banner → simpan campaign dahulu → pilih gambar
└─ Back → Campaign

Create Clip
├─ input sumber (banyak baris) + campaign + jumlah/AI + cookie opsional
├─ Create Clip → satu job per sumber → form siap menerima job berikutnya
└─ pilih job → detail progress / clip berjalan-menunggu-gagal / log

Review & Upload
├─ Review clip → detail → simpan metadata / tolak / setujui / render revisi
├─ pilih clip disetujui → Preview distribusi → edit & simpan jadwal → Upload paket
├─ Pekerjaan → jeda queued / batal queued-running / lanjutkan gagal-terhenti
└─ Tracking → sinkronisasi / buka posting / metrik / CSV / retry-cancel terbatas

Settings
├─ dependency dan model lokal
├─ timezone global
├─ provider/model AI
├─ Repliz & daftar akun
├─ watermark, credit, hook style, face tracking, GPU, output folder
└─ koneksi YouTube OAuth (terpisah dari jalur distribusi Repliz)
```

## 3. Inventaris Dashboard

Sumber: `web/components/dashboard.js:18`, `:259`, `:391`, `:410`.

| Kelompok | Isi yang terlihat / aksi |
|---|---|
| Ringkasan akun | Jumlah TikTok, YouTube, Instagram dari account stats; jumlah campaign |
| Ringkasan produksi | Jumlah clip dibuat |
| Kesehatan alat | Indikator yt-dlp, FFmpeg, Deno, Whisper |
| Campaign | Pohon campaign yang bisa expand/collapse; nama, count, anak akun/source yang disediakan backend |
| Stock Clips | Total ukuran, total clip; maksimal 10 clip terbaru, judul/durasi/tanggal |
| Jobs Proses | Maksimal 10 active/recent jobs; judul, jumlah clip jika ada, status |
| Shortcut | Restock Clip dan tombol Jobs menuju Create Clip; Repliz Dashboard membuka website eksternal |

Catatan UX aktual: `Campaign: All` adalah **div statis**, bukan filter. Child row campaign bergaya clickable tetapi tidak memiliki handler navigasi. Aksi edit pada clip membuka seluruh folder output. Aksi job gagal memunculkan alert; job lain membuka folder output. Dashboard belum menjadi pusat drill-down ke detail job/clip.

## 4. Inventaris Campaign

### 4.1 Daftar

Sumber: `web/components/campaign-list.js:12`, `web/campaigns.js:233`.

- Buat campaign.
- Kartu: banner 3:2 bila ada, nama, jumlah akun, jumlah stok clip.
- Klik kartu untuk edit.
- Hapus dengan konfirmasi.
- Shortcut `Stok` dan `Upload`.
- Belum ada search, sort, pagination, filter status campaign yang aktif dalam daftar.
- Hanya campaign status `active` dimasukkan dropdown Create Clip (`campaigns.js:250`).

### 4.2 Identitas, brief, dan aturan

Sumber: `web/components/campaign-edit.js:45–250`, `web/campaign-workspace.js:105`.

1. Nama campaign.
2. Platform asal campaign: teks bebas (misal Clippo/platform lain/langsung).
3. Genre/lingkup audiens.
4. Bahasa konten.
5. Platform publikasi: comma-separated; kosong berarti semua.
6. Status: draft, active, archived.
7. Durasi min dan max (detik).
8. Hashtags: chip, Enter untuk tambah, bisa hapus.
9. Tagged accounts: comma-separated.
10. Hooks list: tambah/hapus textarea.
11. Catatan campaign.
12. Angles: chip, tambah/hapus.
13. Persona.
14. Tujuan.
15. CTA.
16. Do rules: tambah/hapus baris.
17. Don't rules: tambah/hapus baris.
18. Aturan umum: judul + deskripsi per item, tambah/hapus.
19. Banner gambar; perlu campaign tersimpan dulu.

### 4.3 Brief dan aset

Sumber: `web/components/campaign-edit.js:305`, `web/campaign-workspace.js:70`, `:118`, `:221`.

- Paste teks brief.
- Tambahkan beberapa file; komponen mencantumkan teks/Markdown/SRT/PDF/DOCX/gambar/video/audio.
- Set peran tiap aset: Brief, Video campaign, Musik, Penutup, Gambar.
- Tanda `Wajib` per aset; hapus aset dari daftar.
- Tombol `Baca brief dengan AI` membaca aset berperan Brief + teks.
- Status ekstraksi, kesalahan per sumber, data yang belum ditemukan.
- Konflik menampilkan field/nilai form/nilai usulan/nama sumber; pilih `Gunakan nilai form` atau `Gunakan usulan`.
- Bagian expandable sumber hasil pengisian AI/provenance dalam JSON.
- Nilai form yang diubah selama ekstraksi dipertahankan; existing campaign dilindungi dengan konflik, bukan diam-diam seluruhnya diganti.
- AI hanya mengisi usulan. Pengguna tetap menyimpan campaign secara eksplisit.

### 4.4 Template dan aturan produksi

Sumber: `web/campaign-workspace.js:20`, `:50`; katalog `services/campaigns.py:38`.

| Template saat ini | Format / subtitle | Feature tetap |
|---|---|---|
| Standar | Vertikal 9:16; Clean | Highlight Finder aktif; Caption Maker aktif; Hook Maker nonaktif; YT Title Maker aktif |
| Podcast Kotak | Kotak 1:1; kata per kata | Highlight Finder aktif; Caption Maker aktif; Hook Maker nonaktif; YT Title Maker aktif |

- Aktif/nonaktif per template.
- Bobot peluang 1–100 per template; tampil persentase peluang relatif.
- Minimal satu template aktif; satu aktif berarti selalu template itu.
- Pengacakan berlaku **per clip**, bukan satu kali per job; peluang tidak menjamin jumlah hasil persis.
- `Lihat template` memilih detail yang ditampilkan, **bukan** memilih satu-satunya template produksi.
- `Lihat contoh [nama]` memuat video preview template.
- Isi template berupa indikator read-only, bukan toggle editable fitur.

Bagian expandable `Musik, framing, dan aturan produksi`:

1. Framing: ikuti pembicara / seluruh frame / crop tengah.
2. Peran sumber produksi: materi luar campaign / materi resmi campaign.
3. Musik: pilih otomatis / file campaign; tidak ada opsi tanpa musik.
4. File musik dari aset campaign berperan Musik.
5. Volume musik 1–100%.
6. Offset mulai lagu dalam detik.
7. Turunkan musik saat dialog (ducking).
8. Penutup campaign: aset penutup/gambar/video atau kosong.
9. Penutup wajib atau tidak.
10. Durasi penutup.
11. Batas persentase materi luar campaign.
12. Proporsi harus **kurang dari** batas (strict), bukan sama dengan.
13. Jumlah clip diproses bersamaan: 1–8.
14. Persetujuan hasil: review manual / otomatis setelah semua pemeriksaan lolos.

**Mode otomatis campaign dapat melewati tombol Upload paket.** Setelah job selesai penuh, backend menyetujui clip tanpa warning/blocker, membuat preview, lalu mengonfirmasikannya. Jalur manual pada UI tetap meminta pengguna menekan Upload paket.

### 4.5 Akun dan penjadwalan

Sumber: `web/campaign-workspace.js:135`.

- Daftar akun Repliz + checkbox penugasan campaign; counter akun terpilih.
- Tiap akun hanya memiliki dua jenis pengaturan editable:
  - Jam upload: satu atau lebih, tambah/hapus, jam + menit + AM/PM.
  - Maks upload per hari: integer 1–100.
- Default UI saat belum ada profil: 09:00 AM dan 02:30 PM, maks 2/hari.
- Read-only: status koneksi, kecocokan genre/audiens dan bahasa. Genre/bahasa profil mengikuti campaign yang disimpan.
- Zona waktu ditampilkan read-only; perubahan zona hanya melalui Settings.
- `Simpan jadwal akun` adalah aksi terpisah dari `Save Campaign`.
- Campaign harus sudah disimpan; perubahan audiens/bahasa harus disimpan terlebih dahulu; akun harus sudah ditugaskan ke campaign tersimpan.
- Status `Jadwal belum disimpan`, sukses, atau error per akun.
- Jika daftar akun gagal dimuat, assignment sebelumnya dipertahankan; akun tersimpan yang tidak lagi tersedia ditampilkan sebagai checkbox fallback.
- Setelah `Save Campaign`, readiness menampilkan `Siap produksi` / production blockers dan `Siap distribusi` / publication blockers.

Catatan: UI tidak memiliki tombol gabungan simpan campaign + semua jadwal akun. Back tidak memiliki guard unsaved change. Banner merupakan save terpisah lagi.

## 5. Inventaris Create Clip

Sumber: `web/components/home.js:29`, `web/workflow-source.js:4`, `web/app.js:142–344`.

Empat kelompok input utama:

1. **Sumber video**: textarea satu sumber per baris, tempel clipboard, native picker MP4 lokal, drop file.
2. **Campaign**: dropdown campaign active, ringkasan template/jumlah template aktif dan blockers produksi.
3. **Jumlah clip**: tentukan jumlah integer 1–100 (default5) atau AI menentukan mengikuti highlight berkualitas; jumlah fixed berlaku per sumber.
4. **Cookie**: pilih cookies.txt; opsional untuk sumber yang perlu login; cookie tersimpan digunakan kembali.

Aksi dan state:

- `Create Clip` mengantrekan banyak sumber sekaligus; tiap sumber menjadi job sendiri.
- Form dikunci hanya saat request enqueue, bukan sepanjang render; pengguna bisa menambahkan job berikutnya segera setelah request selesai.
- Source dikosongkan setelah berhasil; campaign dan jumlah tetap.
- Validasi sumber kosong, campaign kosong, jumlah invalid; error inline; clipboard gagal memberi cara tempel langsung.
- Pekerjaan video: refresh manual, refresh otomatis tiap2detik hanya saat Create Clip terlihat.
- Job row: judul sumber/video, campaign, target/total clip, status, posisi antrean.
- Pilih job: judul, campaign, status, jumlah selesai/gagal/dibatalkan; progress; tahap persiapan download/transcribe/highlights.
- Subbagian clip: in progress, waiting, error; progress per clip; judul/step/error.
- Log pekerjaan per job, copy log.
- State job: queued, running, completed, partial, failed, interrupted, cancelled, cancelling, paused.
- **Tidak ada pause/cancel/resume di panel Create Clip** saat ini; kontrol itu ada di Review & Upload > Pekerjaan.

## 6. Inventaris Review & Upload

Sumber utama seluruh bagian: `web/components/workflow-review.js` (185baris).

### 6.1 Daftar review (`:18`)

- Search judul clip.
- Filter review: semua / perlu review / disetujui / ditolak.
- Filter campaign datang dari shortcut campaign; `Semua campaign` menghapusnya.
- List: checkbox selection (enabled hanya approved), judul, durasi, template, campaign, badge review, tombol Review.
- `Preview distribusi` memakai clip approved yang dipilih.
- Empty state dengan arahan Create Clip.
- Refresh manual.

### 6.2 Detail review (`:34`)

- Pemutar video final.
- Edit judul.
- Edit caption publikasi.
- Caption opsional per platform: TikTok, Instagram, YouTube, Facebook, Threads, LinkedIn; kosong pakai caption umum.
- Blockers/warnings teknis; bila kosong tetap mengarahkan user menilai cerita, audio, teks.
- Pengukuran audio: integrated LUFS, true peak dBTP, loudness range LU; kondisi measured/silent/no_audio/belum tersedia.
- `Simpan revisi` menyimpan metadata review; `Tolak`; `Setujui clip`.
- `Ubah framing atau musik` untuk clip preset terkunci; template read-only.
- Clip legacy tanpa preset dapat memilih subtitle template clean/social/bold saat revision; ini **bukan katalog template campaign baru**.
- Revisi framing: speaker/fit/center.
- Revisi musik: teks path file lokal; kosong berarti musik otomatis; tidak ada file picker khusus di detail review.
- `Render revisi` membuat pekerjaan revisi dan hasil baru masuk review lagi.
- Expandable `Rencana editing dan sumber` berisi JSON clip_plan.
- Belum ada timeline editor, drag trim in/out, text-transcript editor, waveform editor, atau preview draft sebelum render.

### 6.3 Preview distribusi (`:74`)

- Tabel: clip, akun, platform, jadwal, caption.
- Caption final per assignment bisa dibuka.
- Jadwal inline: tanggal + jam/menit/AMPM + tombol Simpan jadwal + status canonical timezone.
- Perubahan unsaved atau save pending memblokir Upload paket.
- Save gagal mempertahankan error/dirty state; user koreksi dan simpan kembali.
- Selama saving, input baris dikunci; selama confirming upload, semua input jadwal dikunci.
- Kembali ke daftar atau `Upload paket ini` → masuk Tracking.
- UI **tidak menyediakan manual ganti akun assignment, platform, atau drag reorder alokasi**; hanya edit jadwal pada preview.

### 6.4 Pekerjaan (`:125`)

- Semua workflow jobs; campaign, source, step/error/attention, status.
- Detail expandable clip gagal.
- `Lanjutkan`: failed, partial, interrupted, cancelled, paused.
- `Batalkan`: queued, running.
- `Jeda`: queued saja.
- Polling4detik saat tab ini aktif; worker_note bila ada.
- Ini tampilan job kedua selain Create Clip; title utamanya campaign, bukan video seperti di Create Clip.

### 6.5 Tracking (`:138`)

- List publication: clip, akun, platform, jadwal global, badge status.
- Buka posting bila URL tersedia.
- Metrik numeric dari provider; placeholder jika belum tersedia; waktu pembaruan metrik.
- Error upload, sync, metrik ditampilkan.
- `Sinkronkan provider` memulai background sync.
- `Ekspor CSV`.
- `Batalkan` hanya queued/failed yang belum memiliki schedule provider dan bukan uncertain submission.
- `Coba lagi` hanya failed yang bukan uncertain submission.
- Polling4detik saat aktif.
- Status mencakup queued, uploading, scheduled, publishing, published, failed, needs_attention, cancelled.
- Tidak ada edit jadwal setelah paket disubmit, cancel jadwal provider yang sudah terbuat, chart analytics, filter/search tracking yang terpisah, atau dashboard pendapatan.

## 7. Inventaris Settings

Sumber: `web/components/ai-settings.js`, `web/app.js:365`, `:385`, `:846`, `:1041`.

### Sistem / dependency

- Status dan install/update/retry tiap dependency: yt-dlp, FFmpeg, Deno, Whisper, tzdata.
- Install All / tindakan gabungan; Check Updates; progress/status background; restart required.
- Pilihan Whisper: API, large-v3-turbo, medium.
- Reload Model.

### Jadwal global

- Zona waktu global; default WITA/Asia/Makassar, juga WIB/WIT/UTC dan zona Intl yang tersedia.
- Format waktu AM/PM tetap, bukan opsi perakun.
- Perubahan timezone tidak menggeser waktu absolut publikasi yang sudah ada; preview perlu dibuat kembali.

### Provider dan model AI

- API key OpenAI; API key Gemini.
- Custom Provider1,2,3: endpoint + key masing-masing.
- Test key/endpoint memuat model provider.
- Pemilihan model untuk Highlight Finder, Caption Maker, Hook Maker, YT Title Maker, Brief Extractor.
- Tombol Test per model.
- Pemilihan model memakai prefix provider; menu model gabungan dari provider yang berhasil dimuat.
- Auto-save input800ms, select/checkbox/radio langsung; tombol Save Settings juga tersedia.
- Tidak ada toggle provider lama yang aktif (`providerButtons: []`), eye controls dan sebagian URL inputs adalah compatibility elements tersembunyi.

### Akun publikasi

- Repliz access key + secret key.
- Test Connection.
- Daftar akun dan status koneksi; Connect More membuka dashboard Repliz di luar app.
- Tidak ada halaman Accounts tersendiri, login sosial in-app, atau pemetaan account schedule di Settings; profile schedule ada dalam campaign.

### Visual global dan performa

- Watermark: enable, file gambar Browse, posisi X/Y, opacity, scale.
- Credit Watermark: enable, posisi X/Y, text size, opacity; credit nama channel.
- Hook Style: font system, font color, background color, font size, corner radius, posisi X/Y.
- Face tracking mode: OpenCV / MediaPipe.
- GPU acceleration enable; Detect GPU; info encoder/hardware atau CPU fallback.
- Output Folder: pilih, lihat path, buka folder.
- YouTube API: connect OAuth, disconnect, channel/status, missing client_secret error. Panel tetap visible walaupun distribusi aktif memakai Repliz; jangan dokumentasikan sebagai jalur upload alternatif dalam flow sekarang tanpa memastikan backend.

## 8. Friksi / ketidakteraturan yang penting untuk redesign

Fakta kode saat ini, bukan permintaan perubahan otomatis:

1. **Dua kata berbeda menuju aksi sama:** Stok dan Upload pada kartu/detail campaign sama-sama memanggil Review & Upload dengan filter campaign. `refresh(filter)` tidak membaca parameter boolean kedua.
2. **Job terpecah di tiga tempat:** Dashboard (overview), Create Clip (detail progress), Review & Upload > Pekerjaan (control recovery). Pengguna harus berpindah untuk pause/resume.
3. **Save terpisah:** campaign, jadwal masing-masing akun, banner. Simpan campaign tidak menyimpan perubahan jadwal akun; first-time setup perlu urutan tertentu.
4. **Aturan produksi bercampur dengan identitas dan distribusi:** template, music, concurrency, approval mode, account quota semuanya dalam satu edit page panjang.
5. **Global Hook Maker/Hook Style tetap terlihat**, tetapi kedua template campaign yang aktif kini mematikan hook. Hooks list brief juga tetap ada. Jangan menganggap edit Hook Style akan terlihat pada kedua template sekarang.
6. **Template istilah berlapis:** preset campaign Standar/Podcast Kotak, subtitle_style internal clean/social/bold, dan rendered template metadata. Tampilan legacy revision membawa nama lain.
7. **Dashboard affordance belum sepenuhnya fungsional:** Campaign: All terlihat seperti filter tetapi statis; child row cursor pointer tanpa navigasi; klik clip membuka output folder.
8. **Pengaturan global visual** masih dapat memengaruhi semua campaign, sementara user flow kini berorientasi template campaign. Perlu memutuskan ownership desain yang konsisten.
9. **Preview distribution berfokus jadwal:** tidak bisa mengoreksi pemilihan akun secara langsung; perlu kembali campaign/profile atau regenerasi preview.
10. **Bahasa/naming campur:** Campaigns/Edit Campaign/Create Clip, Stok, Review clip, Pekerjaan, Jobs Proses, in progress, waiting; sebagian subtitle Settings masih placeholder sales.
11. **Jadwal dan waktu memakai helper global**, tetapi log pekerjaan menampilkan timestamp mentah yang dikirim backend (`web/app.js:266`). Log debug tidak diformat oleh SSRTime.
12. **Mode otomatis perlu nama dan konsekuensi jelas:** backend dapat menyetujui sekaligus mengirim clip yang lolos setelah job selesai; clip dengan warning/blocker memerlukan review manual.
13. **Tidak ada UI pencarian campaign marketplace, klaim reward/cuan, pembayaran, atau payout.** Sumber campaign dipilih user di luar sistem.
14. **Tidak ada template editor/designer UI.** User mengaktifkan preset dan mengatur bobot; fitur/appearance preset tetap.

## 9. Prinsip dokumentasi perbandingan

- Bedakan `fitur visible dan wired`, `legacy code yang tidak dijangkau`, `placeholder`, dan `target masa depan`.
- Jangan menjumlahkan seluruh simbol API/komponen sebagai fitur user aktif.
- Jangan mengklaim semua settings editing berlaku pada semua template; hook template kini off.
- Istilah `otomatis` harus diberi objek: ekstraksi brief, pemilihan highlight/template/musik, approval, atau publication. Tingkat otomatisasi tiap tahap berbeda.
- Dokumen ini tidak memastikan status runtime provider/model, hak musik, atau kualitas footage aktual; hal itu bukan hasil audit statis frontend.
