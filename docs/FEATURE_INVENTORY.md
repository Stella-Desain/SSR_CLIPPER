# Inventaris fitur SSR_CLIPPER

Diperbarui 28 September 2026. Pasangan dokumen: [user flow sebelum vs sekarang](USER_FLOW_BEFORE_AFTER.md).
Baseline: commit `a5ce5f6` (4 September). “Sekarang” adalah working tree; daftar ini memisahkan jalur
UI aktif, kemampuan mesin, dan hal yang masih terbatas. UI/provider produksi belum diuji langsung.

## 1. Peta modul dan objek

| Modul | Objek utama | Tanggung jawab |
|---|---|---|
| Template Studio, terpisah | Project editor, paket template | Authoring Kdenlive → export MLT → `.ssrtemplate` |
| Campaign | Campaign, aset, versi, assignment akun | Brief, aturan produksi/editing/distribusi yang digunakan ulang |
| Create Clip / produksi | Sumber, job, highlight, ClipPlan | Membuat beberapa job, memilih momen, mengolah clip |
| Review & Upload / review | Clip, metadata, persetujuan | Memeriksa file final dan informasi publikasi |
| Distribusi / tracking | Preview assignment, publication, snapshot statistik | Menjadwalkan, mengirim ke provider, memantau hasil |
| Settings | Konfigurasi global | AI, alat lokal, integrasi, render, zona waktu, penyimpanan |

**Job bukan clip; clip bukan publikasi.** Satu job dapat menghasilkan banyak clip. Clip mempunyai
status review terpisah dari status render dan status pengiriman. Satu preview saat ini menempatkan
setiap clip pada **satu** akun yang memenuhi syarat, bukan otomatis semua akun/platform.

## 2. Perubahan fitur sebelum → sekarang

| Area | Sebelum | Sekarang |
|---|---|---|
| Brief campaign | Manual atau satu dokumen; hasil AI langsung ke form | Multi-file, peran aset, provenance, konflik, readiness, versi |
| Kepemilikan editing | Toggle/config pada Create Clip | Template dan kebijakan produksi pada campaign |
| Template | Style subtitle global | Empat preset bawaan + paket MLT impor, aktif/bobot per campaign |
| Authoring template | Tidak tersedia | Kdenlive dan exporter terpisah; subset kompatibel |
| Additional | Tidak tersedia per campaign | Watermark dan filter orang target, dibatasi rasio, sosmed, serta template |
| Sumber | Link YouTube; pilihan tanpa campaign | YouTube/file lokal; campaign wajib; banyak sumber sekali enqueue |
| Pekerjaan | Satu job aktif; riwayat memori | Antrean persisten, judul sumber, detail per job, recovery |
| Highlight Finder | Prompt viral umum | Profil audiens per campaign, referensi opsional, bukti sumber, penilaian review |
| Akhir ucapan | Timestamp AI + validasi durasi | Pemeriksaan transkrip/jeda, menyelesaikan kalimat dalam budget |
| Musik final | Bukan jaminan setiap render | Wajib berhasil dicampur sebelum clip selesai |
| Framing | Deteksi wajah/crop awal | Identitas geometris, scene reset, smoothing, fallback + metadata |
| Review | Stock Clip dan upload langsung | Pending/approved/rejected, revisi metadata/render, file/hash approval |
| Jadwal akun | Batas campaign/global upload | Jam dan maks/hari per akun, zona global WITA, AM/PM |
| Penyesuaian jadwal | Tidak ada editor inline preview | Tanggal/jam dapat diedit sebelum konfirmasi |
| Upload | Jalur quick upload legacy | Preview → validasi → antrean publication → provider |
| Tracking | State upload lokal | Status provider, post URL, statistik tersedia, CSV, retry/reconcile |

## 3. Dashboard dan navigasi

| Fitur aktif | Isi/aksi | Batas UX |
|---|---|---|
| Menu | Dashboard, Campaign, Create Clip, Review & Upload, Settings | Edit Campaign adalah subhalaman |
| Ringkasan akun/campaign | Jumlah akun TikTok/YouTube/Instagram dan campaign | Bukan analitik pendapatan |
| Ringkasan produksi | Jumlah clip, ukuran stock | Bergantung indeks file lokal |
| Kesehatan alat | FFmpeg, yt-dlp, Deno, Whisper | MLT diperiksa saat impor/readiness template |
| Pohon campaign | Expand/collapse akun/sumber | Bukan drill-down lengkap ke semua objek |
| Clip terbaru | Judul, durasi, tanggal, buka output | Maksimal 10 di Dashboard |
| Job terbaru/aktif | Judul sumber, status, jumlah clip | Detail/kontrol tersebar pada halaman produksi dan Pekerjaan |
| Shortcut | Restock/Create Clip, output folder, Repliz Dashboard | Dashboard belum menjadi pusat review/pemulihan |

## 4. Campaign

### Daftar dan identitas

- Create, buka/edit, hapus dengan konfirmasi; kartu banner, nama, jumlah akun/stock; shortcut Stok/Upload.
- Status draft/active/archived; hanya active muncul di Create Clip.
- Nama, platform asal campaign bebas, genre/lingkup audiens, bahasa, platform publikasi.
- Banner dipilih setelah campaign tersimpan. Belum ada search/sort/pagination/filter status pada daftar.

### Semua field brief dan aturan

| Kelompok | Field |
|---|---|
| Durasi | Min/max detik |
| Caption publikasi | Hashtags, CTA, tag akun TikTok/Instagram terpisah dengan pilihan sosmed |
| Narasi | Hooks list, angles, persona, tujuan, catatan |
| Aturan | Do, Don't, Aturan Umum (judul + deskripsi) |
| Platform | TikTok, Instagram, YouTube, Facebook, Threads, LinkedIn, Twitter/X, Shopee pada validasi backend |

Campaign lama masih menyimpan beberapa field legacy, misalnya batas clip/hari campaign. Limit akun yang
disimpan menjadi acuan utama penjadwalan; field lama tidak perlu dijadikan kontrol per akun tambahan.

### Brief, aset, ekstraksi AI

- Paste teks; beberapa PDF/DOCX/TXT/MD/SRT/CSV/gambar, video dan audio.
- Peran: Brief, Video campaign, Musik, Penutup, Gambar; tanda Wajib; hapus dari daftar.
- Video MP4/MOV/MKV/WebM; musik MP3/WAV/M4A/AAC/FLAC/OGG; gambar PNG/JPG/JPEG/WebP.
- AI membaca sumber Brief dan teks; mengusulkan field yang diizinkan, tidak mengaktifkan upload otomatis.
- Usulan, asal file, data belum ditemukan, error per file; konflik nilai form vs usulan dan resolusi.
- Koreksi manual yang sedang diketik tidak ditimpa respons AI lama.
- Aset disalin/diperiksa hash; file wajib yang hilang memblokir produksi.
- Versi/snapshot campaign untuk job; readiness produksi dan publikasi terpisah.
- PDF scan/OCR penuh dan file binary `.doc` tidak dinyatakan sebagai dukungan andal.

### Profil audiens dan pencarian highlight

- Audiens, tujuan/manfaat, topik, sudut pembahasan, pola pembuka, hal yang dihindari, dan konteks wajib dapat diedit per campaign.
- Bobot kecocokan audiens, kekuatan pesan, daya tarik pembuka, dan keutuhan gagasan; skor minimum 0–100.
- Multi-video **Referensi highlight**, opsional; hapus per contoh; ringkasan dan pola terikat identitas file. Referensi tidak menjadi video sisipan.
- **Usulkan profil dari brief & referensi** memakai provider yang dikonfigurasi hanya setelah tombol ditekan. Preview → Terapkan usulan ke form → Simpan campaign. Perubahan form selama analisis tidak ditimpa.
- Transkrip contoh: SRT/TXT bertimestamp, Whisper lokal yang sudah tersedia, atau Caption Maker API. Tidak mengunduh model otomatis saat analisis.
- Kandidat memiliki pemeriksaan audiens/brief/gagasan/konteks, nilai per dimensi, alasan, dan kutipan sumber. Rentang yang diperbaiki diperiksa ulang; urutan akhir memakai skor setelah pemeriksaan, bukan viral saja.
- Review menyediakan alasan/nilai/bukti dan penilaian cocok, di luar topik, perlu konteks, atau akhir belum selesai. Penilaian menjadi bahan usulan profil; tidak mengubah persetujuan atau publikasi.
- Profil ikut versi campaign/job. Dua contoh bukan bukti performa viral, dan analisis makna bergantung pada transkrip serta model. [Alur dan kontrak finder](CAMPAIGN_HIGHLIGHT_FINDER.md).

### Template dan semua pengaturan produksi

| Fitur | Pilihan/perilaku |
|---|---|
| Standar | 1080×1920, Clean; highlight/caption/title aktif, hook mati |
| Podcast Kotak | 720×720, rounded frame, uppercase per kata; hook mati; font referensi masih pendekatan |
| Tegas 4:3 | 1440×1080, vignette, subtitle kapital kanan atas; mula-mula nonaktif |
| Sinematik 16:9 | 1920×1080, B-roll campaign, subtitle bertingkat/oranye dan blur/fade; mula-mula nonaktif |
| Aset B-roll | Gambar/video immutable; peran B-roll, visual pengganti sementara dengan suara sumber tetap; diperlukan saat Sinematik aktif |
| Impor Kdenlive | `.ssrtemplate`, validasi paket/aset/service/runtime; salinan lokal versi immutable |
| Preview template | Contoh layout; preset bawaan menampilkan contoh subtitle, MLT komposisi/judul |
| Aktif/bobot | Aktif/nonaktif, bobot 1–100, persen relatif, minimal satu aktif |
| Pemilihan | Acak per clip; pilihan disimpan untuk resume/revisi; satu aktif berarti selalu dipakai |
| Feature template | Read-only; tidak diedit sebagai toggle per campaign |
| Framing | Speaker, seluruh frame/fit, crop tengah; bentuk source template menentukan tahap framing tersedia |
| Peran sumber | Materi resmi campaign atau materi luar campaign |
| Musik | Auto atau file campaign; path aset, volume 1–100%, offset awal, ducking |
| Penutup | File gambar/video, wajib/opsional, durasi |
| Rasio materi luar | Persen maksimum; strict berarti harus kurang dari, bukan sama dengan |
| Paralelisme | Worker clip 1–8, dibatasi kapasitas mesin |
| Mode review | Manual; atau automatic setelah semua pemeriksaan lolos |

Mode automatic adalah **auto-approval dan auto-distribution** untuk clip tanpa warning/blocker dari
job selesai penuh. Job partial tidak melewati review otomatis. Perubahan template impor memakai versi
baru; isi versi yang berubah setelah job dibuat ditolak. Lihat [batas MLT](TEMPLATE_SYSTEMS.md).

### Additional

- Kartu rounded **Additional**: Tambah → Watermark / Hanya clip wajah; aktif/nonaktif dan hapus.
- Rasio output template sebagai scope: 9:16, 1:1, 4:3, 16:9 dan rasio custom template impor.
- Sosmed: TikTok / IG; template: semua, hanya pilihan, atau mengecualikan pilihan.
- Upload gambar immutable, preview, validasi format/hash; gambar terpisah dari scene sisipan. Watermark mendukung maksimal 24 gambar dalam satu Additional, multi-pilih dan tambah bertahap.
- Watermark: posisi dan ukuran per gambar melalui drag/pegangan sudut; ikon sampah di kiri atas menghapus satu gambar. Opasitas tetap 100%. Preview 9:16 memakai referensi safe area TikTok, hanya sebagai panduan.
- Foto satu orang target: pencocokan lokal YuNet/SFace; hanya highlight dengan bukti kemunculan yang cukup diterima. Beberapa foto pada satu rasio berlaku sebagai alternatif.
- Filtering sesudah pilihan template/validasi akhir ucapan, sebelum konversi rasio. Kandidat gagal tidak menghabiskan kuota clip atau mendapat undian template baru.
- Musik wajib dipasang setelah template/subtitle; versi watermark dibuat sesuai sosmed sebelum review. Review dapat mengganti preview versi, persetujuan mencakup semua hash file, dan distribusi memilih file sesuai akun. Bukti tersimpan dalam metadata; resume/revisi memeriksa ulang filter.
- Model/gambar hilang dan frame tidak terbaca menjadi error; rasio tanpa template aktif menghasilkan peringatan. Lihat [panduan dan batas Additional](CAMPAIGN_ADDITIONALS.md).

### Akun dalam campaign

- Pilih akun Repliz; count akun terpilih; status koneksi dan kecocokan audiens/bahasa.
- Hanya dua jenis kontrol per akun: **jam upload** (tambah/hapus, AM/PM) dan **maks upload/hari** (1–100).
- Default 09:00 AM, 02:30 PM; maks 2/hari.
- Profil audiens/bahasa mengikuti campaign saat jadwal akun disimpan; satu scope audiens per akun.
- Profil keyed account ID dan berlaku lintas campaign; bukan profil berbeda untuk tiap assignment.
- `Simpan jadwal akun` terpisah dari `Save Campaign` dan banner. Campaign/assignment perlu disimpan dulu.
- Assignment lama dipertahankan bila daftar provider gagal dimuat.
- Zona waktu read-only di sini; perubahan hanya di Settings.

## 5. Create Clip dan pekerjaan

| Input utama | Perilaku |
|---|---|
| Sumber | Satu sumber/baris, paste, picker/drop lokal; YouTube watch/shorts/live/embed/youtu.be |
| Campaign | Campaign active wajib; ringkasan template/readiness |
| Jumlah | Fixed 1–100 per sumber; atau AI menentukan (0 pada backend) |
| Cookie | File cookies.txt tersimpan; opsional sesuai akses sumber |

- 1–50 sumber per enqueue; satu sumber menghasilkan satu job. Form siap menambah job berikutnya saat
  job sebelumnya masih berjalan. Sumber dikosongkan sesudah enqueue, pilihan lain dipertahankan.
- Job serial; clip dalam job paralel. Tidak ada janji banyak video sumber diproses bersamaan.
- Judul sumber diambil asynchronous; posisi antrean, target/hasil, selesai/gagal/batal, tahap/progress/log.
- Pilih job untuk melihat clip berjalan, waiting, error; copy log. Refresh otomatis saat halaman terlihat.
- Pause queued; cancel queued/running; resume failed/partial/interrupted/paused/cancelled dari tab Pekerjaan.
- Restart mendeteksi interrupted; resume memakai snapshot asal dan cache valid. Config global tertentu
  masih dibaca saat eksekusi, misalnya model/GPU/watermark/output.
- Tidak mendukung input playlist atau URL TikTok/Instagram umum sebagai sumber Create Clip saat ini.

## 6. Kemampuan mesin produksi

| Tahap | Fitur |
|---|---|
| Sumber | Hash lokal, identitas YouTube, download/cache sumber, deteksi perubahan sejak enqueue |
| Transkrip | Full source, cache, subtitle/SRT sumber bila ada, Whisper fallback, timestamp kata untuk caption |
| Sumber visual | Sampel 12 frame bertimestamp untuk sumber tanpa transkrip yang berguna |
| Highlight | Brief lengkap, skor/judul/deskripsi, chunk overlap untuk sumber panjang, timestamp absolut, dedup |
| Jumlah/overlap | Fixed/AI; highlight overlap boleh; conflict group dicatat; invalid tidak menghabiskan target |
| Akhir ucapan | Budget min/max campaign, boundary kalimat/jeda, penolakan conjunction/question belum selesai |
| Cut/framing | Timestamp FFmpeg/VFR, portrait tracking, scene reset, smooth camera, detector fallback |
| Rencana | Source range/hash, source role, template/versi, aset wajib, endcard, rasio material, musik |
| Komposisi | Concat aset + endcard; Podcast frame; MLT impor sebagai tahap visual terpisah |
| Caption | Subtitle dibakar setelah komposisi; renderer sesuai pilihan template |
| Musik | Wajib, required asset prioritas, auto mood/tempo + Jamendo atau lokal, loop/fade/duck/limiter |
| Validasi musik | File/volume/window lagu harus valid dan audible; metadata mixed/hash diperlukan |
| Audio | Audio sumber dipertahankan pada MLT; analisis LUFS, true peak, loudness range dan warnings |
| Final | Durasi/dimensi/audio, metadata title/caption/platform, source provenance, final SHA-256 |
| Cache render | Render key/version/hash/musik valid; output lama tanpa bukti musik tidak dianggap selesai |

Deteksi speaker masih geometris/visual; bukan diarization audiovisual penuh. AI/transkrip dapat keliru;
validasi boundary meningkatkan keamanan akhir cerita tetapi tidak menjamin semua narasi semantik 100%.

## 7. Review dan revisi

- Search judul; filter semua/pending/approved/rejected; filter campaign dari shortcut.
- List judul/durasi/template/campaign/status; selection hanya clip approved; empty state dan refresh.
- Pemutar file final; judul, caption umum, caption override TikTok/IG/YT/FB/Threads/LinkedIn.
- Caption publikasi berbeda dari subtitle yang dibakar dalam video.
- Blocker/warning, pengukuran audio, JSON ClipPlan/sumber; simpan metadata, tolak, setujui.
- Approval mengikat revision/hash file dan memeriksa title/caption/CTA/hashtags/mentions/rules teknis.
- Simpan revisi metadata mengembalikan clip ke pending. Reject tidak menghapus file.
- Render revisi: framing/musik dari kontrol yang tersedia, job dan hasil baru, review ulang wajib.
- Template pilihan clip dikunci; clip legacy dapat memiliki opsi subtitle clean/social/bold.
- Tanpa source provenance lokal, clip legacy tidak bisa dirender ulang; perlu job baru.
- Belum ada timeline bebas, editor kata/timing subtitle, waveform, trim manual atau project round-trip.

## 8. Distribusi, jadwal dan tracking

| Fitur | Perilaku |
|---|---|
| Preview | Clip approved terpilih → satu akun eligible per clip; caption final per assignment |
| Pemilihan akun | Scope/bahasa/platform/koneksi; earliest slot lalu load sebagai tie-break |
| Kapasitas | Jam akun, kuota per hari, histori lintas batch/campaign; hindari duplikat akun + overlap |
| Jadwal awal | Slot masa depan, default 5 menit buffer; AM/PM dalam zona global |
| Edit inline | Tanggal + jam/menit/AMPM; bisa di luar jam rutin tetapi future/quota/collision diperiksa |
| Dirty/pending | Upload paket disabled sampai semua perubahan tersimpan |
| Kedaluwarsa | Preview 15 menit; konfirmasi memeriksa ulang file/approval/kapasitas/schedule |
| Konfirmasi | Persists assignment dengan transaksi; retry konfirmasi idempotent |
| Worker | File final ke storage provider → create schedule; queued bukan langsung published |
| Tracking | Sync manual/background saat app hidup; status provider, link posting, statistik tersedia |
| CSV | Ekspor tracking, waktu tampilan global AM/PM |
| Retry | Aman bila submit belum terjadi; schedule existing diretry dengan ID yang sama |
| Uncertain | Needs attention/reconcile, tanpa blind submit yang membuat duplikat |
| Cancel | Local queued/failed yang belum punya schedule provider dan bukan uncertain |

Published/failed/needs-attention tertentu tetap memengaruhi reservasi duplikat. Setelah schedule
dikirim, editor inline tidak mereschedule/cancel provider. Metrik bukan jaminan seluruh platform
menyediakan jenis/kecepatan statistik yang sama. Worker membutuhkan aplikasi tetap berjalan.

## 9. Semua kelompok Settings

| Kelompok | Kontrol yang ada |
|---|---|
| Dependency | Status/install alat lokal, refresh readiness, model transkripsi lokal |
| Zona global | WITA / Asia/Makassar default; zona lain hanya di sini; format AM/PM |
| AI provider per fitur | Highlight Finder, Caption Maker, Hook Maker; provider/API key/base URL/model sesuai registry |
| Model | Pilih/load/validasi/test readiness sesuai provider; model lokal Whisper sesuai dependency |
| Repliz | Access key/secret key, load akun, status integrasi, akun yang terlihat |
| Watermark | Enable, file gambar, posisi X/Y, opacity, scale |
| Credit | Enable, posisi X/Y, text size, opacity; nama channel |
| Hook style | Font sistem, warna font/background, ukuran font, radius, posisi X/Y |
| Face tracking | OpenCV / MediaPipe; konfigurasi engine yang tersedia |
| GPU | Enable, detect GPU, encoder/hardware/fallback CPU |
| Output | Path, pilih folder, buka folder |
| YouTube OAuth | Connect/disconnect, status/channel, client_secret error |

Hook style/Hook Maker tetap terlihat tetapi empat preset bawaan mematikan hook. Jamendo client ID ada
pada konfigurasi backend; jalur inputnya tidak dinyatakan tersedia dalam UI aktif audit. YouTube OAuth
tetap memiliki panel tetapi distribusi aktif menggunakan Repliz; jalur direct upload legacy bukan
fitur upload alternatif yang sudah terbukti pada flow sekarang.

MLT memiliki CLI setup/status dan status bridge; belum ada panel installer MLT tersendiri di Settings.
Preset bawaan tidak membutuhkan MLT. Library template bukan editor visual di dalam SSR.

## 10. Yang belum menjadi fitur produk

- Pencarian/auto-selection campaign, pembayaran/pendapatan, wallet/notifikasi/global search yang masih placeholder.
- Render/import seluruh format/project/efek editor tanpa kontrak; font custom terbundel; migrasi dua preset
  bawaan ke MLT; kecocokan 100% terhadap referensi video.
- Satu clip auto fan-out ke semua akun/platform, provider reschedule/cancel dari editor inline.
- Operasi produksi/tracking ketika aplikasi ditutup, full audiovisual speaker diarization, semua cerita
  dijamin utuh tanpa review, OCR scan penuh, input URL semua platform.

## 11. Catatan untuk redesign

1. Tampilkan scope pengaturan: template version, campaign, akun global, job snapshot, clip revision, publication.
2. Satukan pusat kontrol job; bedakan tab produksi, konten final, dan publikasi.
3. Perjelas tiga aksi simpan campaign, simpan jadwal akun, dan simpan banner.
4. Bedakan template authoring di sistem 1 dari impor/aktivasi/bobot di sistem 2.
5. Bedakan approval konten, antrean pengiriman, schedule provider dan published.

Audit sumber rinci: [_audit_baseline.md](_audit_baseline.md), [_audit_current_ui.md](_audit_current_ui.md),
[_audit_backend.md](_audit_backend.md). Audit tersebut mendahului integrasi MLT; tambahan terbaru ada
di [TEMPLATE_SYSTEMS.md](TEMPLATE_SYSTEMS.md) dan kode SDK/adapter. Tidak semua tombol legacy masih dipakai
oleh view aktif; `workflow-review.js` menggantikan view Stock Clip lama.
