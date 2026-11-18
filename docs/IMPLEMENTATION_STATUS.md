# Status implementasi SSR_CLIPPER

Pembaruan: 28 September 2026. Validasi perubahan terbaru memakai tes lokal dan transport tiruan. Pengguna akan mencoba antarmuka serta integrasi nyata; kontrol GUI tidak dijalankan pada tahap perbaikan ini.

## Terbaru: Highlight Finder per campaign dan dua template referensi

- **Profil highlight campaign** memuat audiens, tujuan, topik, sudut cerita, pola pembuka, hal yang dihindari, konteks wajib, bobot penilaian, dan nilai minimum. Referensi video opsional terpisah dari aset editing. Tombol AI mengusulkan profil; pengguna meninjau, menerapkan, dan menyimpannya. Koreksi manual serta respons terlambat dilindungi.
- Finder campaign memakai profil tersebut, pemeriksaan audiens/brief/gagasan/konteks, nilai per dimensi, serta kutipan bertimestamp. Perbaikan batas ucapan memerlukan penilaian ulang; kandidat diurutkan berdasarkan nilai akhirnya sebelum kuota clip diterapkan. Bukti hilang pada resume tidak boleh diloloskan sebagai hasil lama.
- Review menampilkan alasan, skor, profil, dan bukti sumber. Penilaian pengguna tersimpan pada revisi video yang sesuai dan menjadi masukan usulan profil berikutnya; tidak mengubah persetujuan/publikasi. [Panduan finder](CAMPAIGN_HIGHLIGHT_FINDER.md).
- Setelah fase finder selesai, ditambahkan **Tegas 4:3** dan **Sinematik 16:9** dari dua referensi Timothy. Keduanya mula-mula nonaktif, memiliki fitur tetap, dan mengikuti undian berbobot yang tersimpan. Tegas memakai kapital kanan atas/vignette; Sinematik memakai B-roll campaign, teks bertingkat, serta aksen oranye. [Panduan template](TEMPLATE_TIMOTHY_REFERENCES.md).
- B-roll berupa gambar/video campaign dengan salinan/hash; tidak ditambahkan sebagai scene wajib dan tidak mengganti audio pembicara. Pergantiannya saat ini bergilir, belum dipilih menurut makna. Penutup campaign tidak ditimpa B-roll. Kedua template memakai timestamp kata, musik wajib, dan Additional berdasarkan rasio hasil; 4:3 ikut tersedia.
- Fase finder lulus 256 tes Python dan 34 tes DOM, kemudian pemeriksaan resume/cache tambahan lulus pada suite terkait. Sepuluh tes template lokal berikutnya lulus, termasuk render nyata subtitle, B-roll, musik, dan penutup. **Regresi gabungan lulus 268 tes Python dan 35 tes DOM**, tanpa tes dilewati, termasuk preview native kedua template. Bukti: `output/additional-proof/highlight-reference-final-regression.log` dan `highlight-reference-final-frontend.log`.
- Setelah penyempurnaan pemisahan kata penting/filler dan pasangan frasa pada subtitle sinematik, **7 tes terkait lulus**: kontrak frasa, posisi/font, timing subtitle FFmpeg nyata, dan preview kedua template. Bukti: `output/additional-proof/reference-caption-final-targeted.log`. Contoh visual tanpa suara tersedia di `output/_reference_templates/tegas-preview.mp4` dan `sinematik-preview.mp4`.
- MLT membutuhkan waktu lebih panjang pada pemeriksaan plugin pertama di mesin ini. Timeout diperluas dengan batas yang tetap; error tetap dilaporkan, tanpa membuka editor.
- Batas: kesamaan visual belum identik piksel 100%, pemilihan B-roll masih bergilir, dan tidak ada uji AI/provider produksi atau GUI pada fase ini.

## Terbaru: banyak gambar dan tag akun per sosmed

- **Tambah gambar** dalam satu Watermark mendukung multi-pilih dan unggahan bertahap sampai 24 gambar. Posisi/ukuran tiap gambar terpisah; ikon sampah di kiri atas menghapus satu lapisan. Daftar nama gambar menyediakan tombol hapus tambahan ketika gambar tertutup atau preview gagal. Rasio, sosmed, dan aturan template berlaku untuk seluruh gambar dalam Additional tersebut.
- Gambar lama otomatis menjadi satu lapisan dengan ID/layout yang sama. Penghapusan tidak merusak snapshot atau aset job lama. Jika semua gambar dihapus, draft bisa disimpan; aturan aktif yang berlaku memerlukan gambar sebelum produksi.
- **Tag akun** memiliki dropdown **TikTok / Instagram**. Dua daftar bertahan saat berpindah pilihan dan disimpan terpisah. Tag lama ditampilkan di kedua pilihan untuk mempertahankan data; pengguna dapat mengubahnya per sosmed.
- Caption baru dibuat per sosmed menggunakan tag yang sesuai. Review memeriksa mention wajib pada platform tersebut; preview distribusi dan pengiriman memakai caption tujuan yang sama. Caption kosong per sosmed memakai caption dasar ditambah tag dari snapshot campaign. Ekstraksi AI mendukung dua daftar beserta provenance/konflik; highlight finder tidak diberi daftar tag agar deskripsi bersama tidak mencampurkan tag sosmed.
- Validasi: **225 tes Python dan 26 tes DOM lulus**, tanpa tes dilewati. Setelah penyempurnaan pencocokan username bertitik, **38 tes Python terkait tag/workflow lulus** dan 26 tes DOM diulang. Bukti: `output/additional-proof/multi-images-tags-regression.log`, `multi-images-tags-frontend.log`, `tags-final-targeted.log`.
- Render FFmpeg nyata memperlihatkan dua gambar pada posisi berbeda dan penghapusan satu gambar tanpa menghilangkan gambar lainnya; audio dan durasi dipertahankan. Dialog file diuji dengan tiruan, bukan jendela desktop. GUI/provider produksi tidak dioperasikan.

## Tambahan: Additional per campaign

- Kartu **Additional → Tambah** menyediakan watermark dan filter highlight berdasarkan foto orang target.
- Aturan mengikuti rasio **hasil template**, pilihan sosmed **TikTok/IG**, dan pilihan template **semua/hanya/tidak digunakan pada**. Gambar disalin ke aset lokal dengan hash dan menjadi bagian snapshot campaign/job.
- Watermark diatur langsung pada kanvas melalui drag dan pegangan resize, dengan opasitas tetap 100%; kotak angka dihapus. Preview 9:16 memakai referensi safe area TikTok pengguna sebagai panduan yang tidak dirender.
- Musik dicampur pada video dasar, kemudian versi watermark dibentuk sesuai sosmed. Review dapat memilih preview versi; persetujuan mengikat semua hash versi, dan distribusi memakai file yang sesuai akun. Gambar Additional tidak menjadi scene sisipan.
- Filter lokal OpenCV YuNet/SFace memeriksa rentang highlight utuh sesudah undian template. Kandidat yang tidak cocok dilewati tanpa menghabiskan kuota atau mengundi ulang template. Resume/revisi memeriksa lagi; override Review tidak dapat menghilangkan Additional campaign.
- Foto tanpa satu wajah yang jelas, model/gambar berubah/hilang, serta terlalu banyak frame gagal dibaca menjadi error. Rasio tanpa template aktif memberi peringatan dan belum menerapkan aturan itu.
- Model resmi sudah dipasang dan hash diverifikasi di workspace ini. Installer dan lisensi tersedia; tidak perlu menjalankan Kdenlive/Template Studio.
- Validasi akhir: **217 tes Python dan 21 tes DOM lulus**, tanpa tes dilewati. Ini mencakup 14 tes Additional/sosmed: watermark FFmpeg nyata pada tiga rasio dengan alpha/audio/durasi, model wajah nyata positif/negatif/blank/banyak wajah, include/exclude template, file berbeda menurut sosmed, penolakan varian yang berubah setelah review, snapshot, kandidat pengganti, resume/revisi, drag/resize, upload gagal, dan respons terlambat lintas campaign. Bukti lokal: `output/additional-proof/scopes-regression.log` dan `scopes-frontend.log`.
- Batas filter: sampel maksimal sekitar dua detik dan kehadiran minimal 20% sampel, bukan jaminan wajah terus-menerus atau kecocokan sempurna pada semua video. [Panduan dan urutan Additional](CAMPAIGN_ADDITIONALS.md).

## Tambahan: dua sistem template

- Kdenlive dipilih untuk authoring; toolkit Template Studio dan SDK format dapat didistribusikan sebagai wheel tersendiri.
- SSR mengimpor paket `.ssrtemplate` ke library lokal, menampilkan template pada campaign, dan memasukkannya ke pilihan acak berbobot.
- Runtime MLT Windows tersedia terpisah tanpa executable editor. Rendering memakai template/aset lokal; program serta folder authoring tidak diperlukan.
- Versi/hash paket diikat ke snapshot job/clip. Source duration dipertahankan; audio ucapan berasal dari source SSR, kemudian subtitle dan musik wajib tetap diproses.
- Kontrak awal membatasi efek/tipe project yang didukung. Dua preset bawaan belum dimigrasikan menjadi paket MLT; editor round-trip per clip belum tersedia.
- Validasi terbaru: **203 tes Python dan 17 tes DOM lulus**. MLT sungguhan merender clip 1,4 dan 34,2 detik dari template contoh 3 detik, overlay terbundel, serta pipeline subtitle/musik. Toolkit standalone juga mengekspor paket dalam Python terisolasi; program authoring dihapus sebelum consumer merender.
- [Arsitektur dan panduan dua sistem](TEMPLATE_SYSTEMS.md), [user flow sebelum–sekarang](USER_FLOW_BEFORE_AFTER.md), [inventaris fitur](FEATURE_INVENTORY.md).
- Bukti lokal: `output/_mlt_probe/regression-final.log`, `output/_mlt_probe/frontend-tests.log`, `output/template-distribution/proof/proof.json` dan `proof-without-editor.mp4`. Tidak ada GUI, AI berbayar, akun provider, atau upload nyata yang dijalankan.

## Hasil yang sudah tersedia

Alur aplikasi sekarang menghubungkan **campaign → sumber video → produksi → review hasil final → antrean distribusi → tracking**. Campaign dipilih pengguna, dapat berasal dari platform mana pun, dan dipakai ulang. Pembayaran serta pendapatan tidak menjadi bagian sistem.

### Campaign dan akun

- Beberapa PDF, DOCX, teks, gambar brief, video, gambar campaign, musik, dan penutup dapat dimasukkan. Peran file serta status wajibnya bisa diatur.
- AI mengusulkan data dalam bidang yang diizinkan. Nilai yang bertentangan tampil sebagai konflik; koreksi pengguna dipertahankan. AI tidak diberi kemampuan mengaktifkan publikasi otomatis atau menetapkan akun.
- Asal file hasil ekstraksi dicatat. Campaign disimpan dengan versi; pekerjaan memakai snapshot campaign saat masuk antrean.
- Additional menambahkan watermark atau filter orang target per rasio hasil template; pengaturan ikut snapshot yang sama.
- Pengaturan per akun di campaign hanya **jadwal jam upload** dan **maks upload per hari**. Audiens/bahasa diambil dari campaign saat jadwal akun disimpan, dan tetap diperiksa untuk menjaga satu lingkup audiens per akun.
- Zona waktu berlaku global, default **WITA / Asia/Makassar**, hanya dapat diubah di **Settings**. Jam ditampilkan dengan **AM/PM**, termasuk tracking dan CSV. Batas akun yang disimpan tidak lagi tertahan oleh batas harian campaign lama.
- Form mempertahankan penugasan sebelumnya jika layanan akun gagal dimuat, dan mengabaikan respons lama ketika pengguna berganti campaign.

### Produksi dan editing

- Input beberapa link YouTube atau file video lokal, dengan antrean persisten. File lokal diperiksa dengan hash; perubahan sesudah masuk antrean terdeteksi.
- Create Clip memiliki empat kelompok input: sumber video, campaign, jumlah clip, dan cookie. Form dapat dipakai untuk menambah job saat job lain berjalan. Daftar job dapat dibuka untuk melihat clip, progress, antrean, dan log per sumber.
- Cache sumber dan transkrip, subtitle sumber bila tersedia, fallback transkripsi, pencarian highlight dalam bagian transkrip yang bertumpang tindih, dan fallback analisis sampel gambar untuk sumber tanpa transkrip.
- Campaign menyediakan **Standar**, **Podcast Kotak**, **Tegas 4:3**, dan **Sinematik 16:9**, dengan pilihan aktif/nonaktif dan bobot peluang per template. Setiap clip mendapat satu template secara acak; pilihannya disimpan untuk resume dan revisi. Satu template aktif berarti semua clip memakai template tersebut. Fitur di dalam template tetap ditentukan backend. Lihat [template campaign dan job](CAMPAIGN_TEMPLATES_AND_JOBS.md).
- Podcast Kotak memakai kanvas 720×720, sudut membulat, dan subtitle kapital per kata dengan font terbundel. Musik mengikuti campaign. Kecocokan font dengan referensi masih berupa pendekatan, belum identik 100%. Lihat [catatan referensi dan akhir ucapan](TEMPLATE_PODCAST_KOTAK.md).
- Pencarian akhir highlight memakai seluruh sisa durasi campaign; tidak ada target 30 detik. Pertanyaan yang menunggu jawaban dan jeda setelah kata penghubung ditolak sebagai akhir. Kandidat gagal tidak menghabiskan jumlah clip yang diminta. Akhir highlight dicocokkan dengan batas kalimat/jeda transkrip. Cue YouTube yang tumpang tindih memerlukan jeda audio lokal. Potongan tanpa akhir yang didukung bukti dalam durasi campaign dilewati; ketidakpastian muncul pada Review. Kasus Bangkit diperiksa dari sumber lokal: akhir 03:42.000 bergeser ke 03:44.712, tanpa menimpa video lama.
- `ClipPlan` mencatat rentang sumber, sisipan wajib, penutup, template, musik, framing, dan batas materi luar campaign. Gambar wajib juga menjadi bagian timeline.
- Semua render baru wajib berhasil mencampur musik sebelum selesai. Pemilihan otomatis yang gagal/kosong, bagian lagu yang hening, dan volume nol menjadi error; hasil tanpa musik tidak diterima sebagai render selesai. Cache lama tanpa bukti pencampuran musik tidak dipakai ulang. Musik selesai sebelum review: file wajib/pilihan pengguna, rekomendasi otomatis melalui integrasi yang tersedia, titik masuk, looping, fade, volume, ducking dialog, dan limiter. Atribusi yang tersedia diteruskan ke metadata.
- Audio file final diukur tanpa mengubah video: loudness terpadu, true peak, dan rentang loudness tersedia pada Review. Audio hening, tanpa track, peak bermasalah, atau analisis gagal menjadi peringatan. Lihat [pengukuran audio final](AUDIO_ANALYSIS.md).
- Framing memakai identitas wajah geometris, reset saat pergantian scene, pembatasan gerak kamera, jeda perpindahan target, serta tampilan seluruh frame ketika pembicara tidak pasti. Keputusan kamera tersimpan.
- Jika file detector OpenCV tidak tersedia, render memakai seluruh frame dan mencatat fallback. Peringatan framing diteruskan ke review; kekurangan file detector tidak lagi menjatuhkan proses.
- Pembacaan frame memakai timestamp FFmpeg sebelum dinormalisasi ke frame rate tetap. Durasi utama memakai stream video, sehingga audio yang lebih panjang tidak dianggap sebagai tambahan gambar.
- Produksi paralel dibatasi jumlah worker. Decoder, encoder, dan filter FFmpeg juga diberi batas thread untuk mengurangi perebutan sumber daya, terutama pada input 4K.

### Review, distribusi, dan tracking

- Halaman **Review & Upload** memutar file final yang berisi hasil editing dan musik. Caption publikasi dapat diedit, termasuk override per platform.
- Persetujuan terikat ke hash video dan revisi metadata. Perubahan membatalkan persetujuan yang terdampak. Tombol upload lama diarahkan melalui review.
- Preview distribusi menunjukkan akun, platform, caption, serta jadwal yang dapat diedit langsung per baris. Tombol **Simpan jadwal** menyimpan perubahan; upload menunggu semua perubahan tersimpan. Backend menolak waktu lewat, bentrok, dan pelampauan kuota, lalu memeriksa ulang revisi, file, profil akun, campaign, serta masa berlaku preview saat konfirmasi. Edit dan konfirmasi diserialkan dalam transaksi.
- Kuota dihitung lintas batch dan campaign. Reservasi slot memakai transaksi. Overlap materi dicegah pada akun yang sama berdasarkan identitas sumber dan rentang waktu global.
- Upload menyimpan hasil storage dan ID schedule. Respons pengiriman yang tidak pasti ditahan untuk rekonsiliasi; tidak langsung mengirim duplikat. Retry jadwal gagal memakai ID provider yang sama.
- Payload jadwal tanpa sound native tidak mengirim objek musik kosong. Penolakan pasti dapat dicoba lagi tanpa upload storage kedua; timeout atau hasil ambigu tetap menunggu rekonsiliasi. Lihat [perbaikan dan uji upload](UPLOAD_VALIDATION.md).
- Status antrean, terjadwal, diproses provider, dan benar-benar tayang dibedakan. Tracking menampilkan link, error, metrik yang tersedia, waktu sinkronisasi, dan ekspor CSV.
- Mode awal tetap review manual. Mode otomatis dapat dipilih per campaign; clip dengan blocker atau peringatan kembali memerlukan pemeriksaan.

### Ketahanan aplikasi

- SQLite WAL menyimpan pekerjaan, versi campaign, revisi, dan publikasi. Klaim pekerjaan serta reservasi publikasi bersifat atomik.
- Worker tunggal memakai lock sistem operasi. Jendela tambahan tidak mengambil alih pekerjaan yang sedang berjalan; lock dilepas sistem operasi jika proses berhenti.
- Pekerjaan yang terputus dipulihkan menjadi status yang dapat ditindaklanjuti. Clip yang sudah selesai dapat dipakai kembali saat resume.
- Metadata lama diindeks tanpa menulis ulang video sumber. Penulisan judul/caption baru mengikuti revisi review.
- Perbaikan dependency mencakup perbandingan versi, update dependency yang sudah terpasang, status/error installer, pembatasan pemeriksaan berulang, dan keterangan kebutuhan restart.
- Data zona waktu `tzdata` diperiksa dengan membaca zona IANA dan dapat diperbaiki melalui Settings.

## Cara mencoba alur utama

1. Jalankan `py -3.12 app.py` dengan lingkungan dan dependency proyek. Buka ulang aplikasi setelah perubahan kode.
2. Buka **Campaign**, tambahkan brief/aset, pilih peran file, lalu gunakan **Baca brief dengan AI**. Periksa konflik dan aturan wajib.
3. Tetapkan lingkup audiens campaign, akun tujuan, template, Additional jika diperlukan, framing, musik, penutup, dan mode review. Simpan campaign, kemudian atur jam dan maksimum upload tiap akun melalui **Simpan jadwal akun**.
4. Di **Create Clip**, pilih campaign, masukkan link/file, tentukan jumlah clip, dan jalankan produksi. Setiap sumber menjadi satu job. Tambahkan job lain tanpa menunggu produksi selesai; klik job untuk melihat detailnya.
5. Di **Review & Upload**, periksa video final, caption, serta peringatan. Simpan revisi dan setujui hasil yang sesuai.
6. Pilih clip, buat preview distribusi, edit tanggal/jam jika diperlukan, simpan setiap perubahan, lalu konfirmasikan. Pantau pekerjaan dan publikasi melalui tab tracking.

Proses lokal berjalan selama aplikasi/worker hidup. Jika aplikasi ditutup, proses lokal tidak terus berjalan; pekerjaan dapat dipulihkan setelah dibuka kembali. Jadwal yang sudah diserahkan ke provider mengikuti layanan provider.

## Bukti pengujian

### Pengujian otomatis lokal

**189 tes Python lulus** pada Python 3.12 (24 September 2026) melalui:

```powershell
py -3.12 -m unittest discover -s tests -q
py -3.12 -m compileall -q app.py clipper_core.py services tests utils config
```

Pemeriksaan syntax Node untuk JavaScript yang diubah dan `git diff --check` juga lulus.

Tes mencakup konflik/provenance brief, pembatasan usulan AI, versi campaign, kecocokan akun, kuota lintas batch, overlap, pembatalan, restart, resume tanpa render ulang, penolakan file/revisi berubah, pengiriman tidak pasti, pagination rekonsiliasi, retry provider, kepemilikan worker, serta dependency. Regresi terbaru juga memeriksa edit jadwal dan konfirmasi bersamaan, rollback bentrok/kuota, zona global, bagian lagu yang terpilih, dan akhir jawaban sepanjang rentang campaign. Tes lain memeriksa payload/HTTP Repliz, retry tanpa upload file kedua, perbaikan data zona waktu rusak, pesan validasi akun, fallback detector yang hilang, dan pengukuran audio final.

Tes media memakai FFmpeg sungguhan untuk composition, gambar/penutup wajib, musik pendek yang di-loop, audio/durasi, gaya subtitle, preview HTTP dengan byte ranges, framing 1080×1920 dan 720×720, serta waktu perubahan gambar pada media dengan frame rate variabel. Tes terbaru mencakup dua template dalam satu job, timestamp/jeda kata, sudut bingkai, akhir ucapan, pilihan berbobot, resume, dan revisi tanpa pengacakan ulang. Respons transkripsi pada tes subtitle menggunakan fixture.

### Pengujian antarmuka

Validasi tahap sebelumnya: UI asli dijalankan dengan bridge offline dalam direktori temporer melalui `tests/ui_fixture.py`. Alur yang diuji: membuka dan memutar clip, edit/review, approve, preview distribusi, konfirmasi antrean, ekstraksi brief, mempertahankan koreksi durasi, menyelesaikan konflik, menyimpan campaign, dan memutar contoh template. Tidak ada error/warning console pada pemeriksaan tersebut.

Pada 24 September, **16 tes DOM tanpa browser/GUI** lulus melalui `tests/frontend_workflow.test.cjs` (Node dengan `linkedom`). Tes menjalankan komponen/form dan controller sebenarnya: empat input Create Clip, aktivasi template dan bobot peluang, penolakan semua template nonaktif, preview, penyimpanan/reopening, respons campaign yang terlambat, penambahan beberapa job, pemisahan progress/log/clip antar-job, pencegahan kirim ganda, dua pengaturan akun, AM/PM lintas zona, penyimpanan jadwal inline, penguncian saat penyimpanan, penolakan jadwal gagal, dan pesan error zona. Syntax JavaScript juga diperiksa. Tampilan visual dan interaksi pywebview nyata tetap diuji oleh pengguna.

### Pembanding video nyata

Lihat [laporan framing](FRAMING_BENCHMARK.md). Sampel berasal dari salinan potongan video yang sudah ada di `output`; sumber tidak diedit. Hasil visual dibandingkan dengan jalur OpenCV sebelumnya. Data benchmark tersimpan lokal dalam `output/_benchmarks/` dan tidak masuk Git.

## Status terhadap roadmap M0–M9

| Paket | Status saat ini | Pekerjaan yang masih diperlukan |
| --- | --- | --- |
| M0 — Baseline/stabilitas | Tes terisolasi, dependency, dan benchmark lokal tersedia | Korpus lebih beragam, termasuk trailer, banyak pembicara, dan dua sumber panjang |
| M1 — Data/pekerjaan | Penyimpanan, lock, versi, resume, dan indeks legacy tersedia | Validasi migrasi serta pemulihan pada salinan dataset pengguna yang lebih besar |
| M2 — Campaign/akun | Input beberapa file, konflik, aset wajib, dan profil tersedia | OCR PDF hasil scan; rujukan halaman per bidang yang presisi; masa aktif campaign; halaman akun khusus dan saran kecocokan |
| M3 — Analisis sumber | Input/cache/transkrip/chunk, profil highlight per campaign, contoh opsional, bukti sumber/penilaian tersedia | Pilot AI pada sumber panjang dan indeks visual seluruh aset campaign |
| M4 — Template/editing | Empat template campaign, aktivasi/bobot acak per clip, pilihan tersimpan, B-roll, ClipPlan, sisipan, penutup, preview tersedia | Penyempurnaan kecocokan font referensi; pemilihan B-roll berdasarkan makna; AI menyusun ulang cerita lintas sumber; perbandingan kualitas pendekatan editing |
| M5 — Audio | Musik sebelum review, looping/fade/ducking/limiter, pengukuran loudness/peak final tersedia | Penilaian mix pada kumpulan referensi; preview lagu terpisah; sound native platform |
| M6 — Framing | Tracker stabil, scene reset, fallback, timestamp dan benchmark tersedia | Uji MediaPipe; audio-visual speaker detection; split screen; kunci target/posisi per segmen; pembanding model lain |
| M7 — Review/QA | File final, revisi, metadata, aturan wajib dan rerender tersedia | QA keterbacaan/area teks dan semantik; cache render per tahap agar perubahan musik tidak mengulang seluruh render |
| M8 — Publikasi | Planner, antrean, rekonsiliasi, tracking, CSV tersedia | Pilot provider nyata dan verifikasi pemetaan metrik/link tiap platform |
| M9 — Otomasi | Batch, worker, mode otomatis dengan fallback review tersedia | Pengendalian biaya AI menyeluruh, pengukuran RAM/GPU, evaluasi kualitas dari feedback, dan worker latar terpisah bila diperlukan |

Roadmap menyeluruh **belum seluruhnya selesai**. Jalur utama sudah tersambung, sedangkan baris pekerjaan tersisa di atas tetap merupakan backlog, bukan kemampuan yang diklaim sudah tersedia.

## Batas verifikasi

- Tes perbaikan terbaru tidak mengirim permintaan AI berbayar, upload nyata, atau perubahan jadwal provider. Keberhasilan publikasi pada akun pengguna masih perlu dikonfirmasi lewat uji manual.
- Suite terbaru menggunakan Python 3.12. Framing diuji dengan media sintetis; kualitas MediaPipe dan deteksi pembicara pada materi nyata tetap memerlukan pengujian terpisah.
- Pemeriksaan narasi, emosi, dan kepatuhan visual masih membutuhkan review. Resolusi 1080×1920 tidak membuktikan detail video sumber bertambah.
- Native drag/drop pywebview dan executable hasil packaging belum diuji pada aplikasi desktop terpasang.
- Preview template menggunakan teks contoh. Kualitas caption AI dan sinkronisasi kata pada beragam bahasa tetap perlu pilot transkripsi nyata.

## Lokasi implementasi

- Backend: `services/campaigns.py`, `core_workflow.py`, `editing.py`, `framing.py`, `face_tracking.py`, `workflow.py`, `storage.py`, `publishing.py`, `worker_lease.py`, `media_preview.py`, `dependencies.py`.
- Integrasi desktop: `app.py`, `clipper_core.py`, `utils/dependency_manager.py`.
- UI: `web/campaign-workspace.js`, `web/workflow-source.js`, `web/components/workflow-review.js`, dan komponen campaign/dashboard/settings yang terkait.
- Tes: `tests/test_*.py`, `tests/ui_fixture.py`, `tests/benchmark_framing.py`.

Kontrak integrasi diperiksa terhadap dokumentasi primer [status jadwal Repliz](https://docs.repliz.com/api/schedule/get-schedule), [retry jadwal Repliz](https://docs.repliz.com/api/schedule/retry-schedule), [statistik konten Repliz](https://docs.repliz.com/api/content/get-statistic), dan [filter FFmpeg](https://ffmpeg.org/ffmpeg-filters.html).
