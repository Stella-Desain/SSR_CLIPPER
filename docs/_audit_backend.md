# Audit kemampuan backend saat ini

Audit statis kode pada 24 September 2026. Tidak membuka GUI, menjalankan job, membaca credential/data produksi, mengunggah, atau memanggil layanan AI. Dokumen kerja untuk penyusunan user flow; bukan daftar janji roadmap.

## 1. Jalur implementasi yang benar-benar aktif

- `app.py:254`: `WebAPI(WorkflowMixin, CampaignMixin, DependencyMixin)`. Frontend menggunakan bridge `window.pywebview.api`; tidak ada REST API aplikasi tersendiri.
- `clipper_core.py:92`: `AutoClipperCore(CoreWorkflowMixin)`. Pipeline campaign saat ini berasal dari `services/core_workflow.py`; renderer lama dipakai sebagai `_render_clip_base` (`clipper_core.py:2728`). Jangan menyimpulkan flow aktif dari fungsi lama/komentar lama saja.
- Semua job memakai campaign snapshot; perubahan campaign setelah job dibuat tidak otomatis mengubah antrean tersebut (`workflow.py:113`, `:306`). Konfigurasi global AI, GPU, watermark, face-tracking, output masih dibaca saat job berjalan (`app.py:471`).
- Worker lokal hidup selama aplikasi hidup. Satu jendela memegang lease worker; jendela kedua dapat mengambil alih setelah jendela utama berhenti (`workflow.py:944`). Tidak ada daemon cloud penelusur campaign atau sumber otomatis.

## 2. Alur operasional, batas, dan keputusan

### A. Menyiapkan campaign

1. User memilih campaign di luar aplikasi; masukkan identitas, genre/audiens, bahasa, sumber/platform, brief, aturan, dan akun di aplikasi.
2. Dapat menempel teks serta menambahkan beberapa dokumen/aset: PDF teks, DOCX, TXT/MD/SRT, PNG/JPG/JPEG/WebP; MP4/MOV/MKV/WebM; MP3/WAV/M4A/AAC/FLAC/OGG (`campaigns.py:26`, `:322`).
3. AI mengekstrak fakta dari dokumen/gambar/teks menjadi usulan field terstruktur. Video/audio menjadi aset, tidak otomatis ditranskrip sebagai brief. URL dalam dokumen diperlakukan sebagai data; extractor tidak membuka link. PDF scan perlu gambar halaman. Batas 16 file/ekstraksi, brief maksimal 20 MB/file, teks maksimal 120.000 karakter (`campaigns.py:366`, `:391`).
4. Sumber asal setiap field, field belum ada, konflik antarfile dan konflik dengan nilai user disimpan. Nilai user dipertahankan. Konflik yang belum diselesaikan memblokir produksi (`campaigns.py:290`, `:564`).
5. Aset memiliki peran brief/video/music/endcard/image, flag wajib, optional rentang detik. Simpan campaign menyalin aset ke penyimpanan campaign dan mencatat checksum; perubahan file wajib terdeteksi (`campaigns.py:335`, `:436`).
6. Campaign mempunyai status draft/active/archived. Hanya campaign aktif yang dapat membuat job. Readiness membedakan **siap produksi** dan **siap publikasi**; produksi dapat berjalan walau akun/audiens belum siap publikasi (`campaigns.py:143`, `:564`; `workflow.py:113`). Readiness ini belum merupakan tes koneksi AI/Jamendo/Repliz lengkap.

### B. Template dan aturan produksi

- Template editing publik lengkap saat ini **dua**: Standar (vertikal 9:16, Clean) dan Podcast Kotak (720×720/30fps, sudut membulat, kata putih kapital satu per satu). Keduanya: highlight on, caption on, Hook Maker off, YT Title Maker on (`campaigns.py:38`).
- Daftar renderer subtitle internal ada empat (`clean`, `social`, `bold`, `podcast_square`), tetapi Social/Bold bukan template lengkap baru yang tampil di campaign; masih untuk kompatibilitas revision lama (`editing.py:22`).
- Pool template: user aktif/nonaktifkan dan memberi bobot 1–100. Peluang = bobot/total bobot aktif. Pilihan dilakukan per clip, bukan sekali per job; bukan jaminan jumlah hasil tepat sama dengan persentase. Retry/revisi menyimpan pilihan sama; job baru dapat berbeda. Semua template nonaktif ditolak (`template_selection.py:27`, `:78`).
- Aturan bersama: speaker-follow/full frame/center crop; sumber resmi campaign atau materi luar; musik otomatis/file; volume, awal lagu, ducking; endcard wajib/opsional + durasi; batas proporsi materi luar (≤ atau <); jumlah render clip bersamaan; review manual/otomatis (`campaigns.py:143`, `editing.py:242`).
- Required video/gambar menjadi sisipan berurutan setelah highlight; endcard di akhir. Komposisi sekarang hard cut, bukan editor timeline transisi bebas (`editing.py:242`, `:350`). Rentang cerita dikurangi ruang untuk sisipan/endcard agar total memenuhi durasi.

### C. Membuat job

1. Sumber yang lolos backend: **YouTube URL valid** (watch/shorts/live/embed/youtu.be) atau file lokal yang ada. Tidak mencakup sembarang URL TikTok/Instagram/web/playlist walau downloader memakai yt-dlp (`editing.py:69`). Dialog source: MP4/MOV/MKV/WebM; drop native menerima format tersebut (`workflow.py:45`, `app.py:1866`).
2. `enqueue_sources` menerima 1–50 sumber sekali panggil. Tiap sumber menjadi satu job terpisah. Pilih campaign + jumlah clip; feature editing dari form lama diabaikan dan diambil dari campaign. Jumlah 0 = AI menentukan, 1–100 = target count (`workflow.py:113`, `campaigns.py:57`).
3. Queue menerima job baru saat job lain berlangsung. Judul YouTube dicari worker metadata terpisah; gagal judul tidak menggagalkan job. File lokal memakai nama file (`workflow.py:196`).
4. **Antarjob serial**, **clip dalam satu job paralel** sesuai max_workers (1–8, dibatasi CPU). Caption memakai lock sehingga tidak semua tahap render clip benar-benar simultan (`workflow.py:155`, `core_workflow.py:162`).
5. UI menerima judul, posisi antrean, step, progress, maksimal 100 baris log terbaru/job, jumlah diminta/direncanakan/selesai/gagal/dibatalkan. Sebelum highlight terpilih jumlah clip nyata belum diketahui (`workflow.py:180`, `:565`).

### D. Proses otomatis per job

`Validasi identitas/aset → download/pakai file → probe media → subtitle/transkrip penuh → highlight → perbaiki akhir ucapan → pilih template per clip → render paralel → musik → pemeriksaan final → metadata + review`.

- Download & analisis disimpan dalam cache per source. Urutan transkrip: cache valid → sidecar SRT/subtitle sumber → full-video transcription. Sumber tanpa transkrip bermakna dapat memakai deskripsi visual AI atas 12 frame bertimestamp (`core_workflow.py:18`, `:191`).
- Highlight menimbang brief, persona/audiens, aturan dan konteks cerita. Transkrip panjang dibagi chunk overlap, timestamp tetap absolut; kandidat didedup, diurut skor. Overlap highlight diperbolehkan dalam produksi (`core_workflow.py:238`).
- Jumlah diminta adalah target, hasil dapat lebih sedikit bila kandidat tidak aman/layak. Range durasi adalah batas, bukan target 30 detik atau kewajiban memakai maksimum. Aligner memakai timestamp dan jeda audio, menolak akhir pertanyaan sebelum jawabannya/dangling clause; tetap bukan jaminan pemahaman cerita sempurna (`speech_boundaries.py:95`).
- Pipeline render: potong/framing/watermark/credit legacy base → sisipan/endcard → bingkai template jika square → subtitle di final composition → musik → probe durasi/audio/hash (`core_workflow.py:274`).
- Face tracking menjaga identitas geometris, memperhitungkan scene cut dan durasi shot, beralih ke whole-frame bila pembicara ambigu. Gerak mulut adalah petunjuk, **bukan diarization audio-visual yang andal** (`face_tracking.py:1`, `framing.py:11`).
- **Musik wajib semua render baru**, termasuk job lama ketika di-resume. Local file atau auto. Auto: LLM menentukan mood/tempo → Jamendo mencari instrumental downloadable (filter non-commercial) → window energi musik → download → mix. Butuh provider Highlight Finder + Jamendo client ID; tidak ada musik auto berarti render gagal (`app.py:755`, `:1586`; `workflow.py:327`). Filter kode tidak boleh dipasarkan sebagai jaminan lisensi untuk segala penggunaan.
- Mix menyertakan gain, ducking, fade dan limiter. Musik tidak valid/hening/missing/volume nol ditolak. Track/music checksum dan `mixed=true` wajib sebelum selesai; cache versi lama yang tidak memenuhi itu tidak dianggap render berhasil (`editing.py:384`; `core_workflow.py:286`, `:352`).
- Durasi final di luar batas = blocker; audio peak/perhitungan tidak tersedia, kamera ambigu, aturan narasi/visual yang perlu diperiksa = warning. Tidak semua aturan bahasa/narasi diverifikasi otomatis (`core_workflow.py:341`).

### E. Review manual dan revisi

- Setiap render tersimpan sebagai clip `pending`, file `master.mp4`, data JSON dan record SQLite; preview memakai file final sebenarnya (`workflow.py:378`, `:450`).
- Metadata: judul, deskripsi, caption + CTA + tagged accounts + hashtags + kredit musik; caption spesifik platform; source IDs/ranges, campaign ID/version/snapshot, job, highlight/score/overlap group, template terpilih, plan, musik/hash, kamera/audio checks, warning/blocker.
- User dapat mengubah judul/caption umum/per platform, simpan pending, approve atau reject. Caption approve harus mengandung CTA/hashtag/tag wajib dan judul/caption tidak kosong; blocker mencegah approve. Warning dapat ditinjau lalu disetujui manual (`workflow.py:466`).
- Approval melekat pada hash video + revision + caption + campaign version. Perubahan file atau metadata membatalkan persetujuan. Review tidak boleh diubah saat publication queued/uploading/publishing; perlu membatalkan queue yang aman dahulu.
- Render revisi membuat **job baru + clip hasil baru**, memakai source/highlight dan campaign snapshot sebelumnya; template acak terpilih dipertahankan. Revision UI menawarkan framing/musik; clip legacy bisa memilih renderer subtitle. Semua revisi kembali ke review manual sekalipun campaign otomatis (`workflow.py:515`).
- Clip lama tanpa provenance source/highlight tidak bisa direvisi otomatis; buat ulang dari sumber.

### F. Preview distribusi → upload → publikasi

1. Pilih approved clips; sistem cek approval/hash dan campaign/account aktual.
2. Eligibility akun: terhubung, ditugaskan ke campaign, audience_scope sama, bahasa sama, platform dalam brief (jika dibatasi). Satu akun boleh beberapa campaign **jika lingkup audiens dan bahasa sama** (`campaigns.py:528`; `publishing.py:37`).
3. Profil akun disimpan berdasarkan account ID, **bukan campaign+account**. Dua kontrol user (jam harian + max/hari) berlaku untuk akun itu lintas campaign. Audiens/bahasa diturunkan dari campaign. Mengubah profil pada campaign A juga memengaruhi akun yang sama di B.
4. **Setiap clip dialokasikan ke satu akun tujuan**; bukan menyalin tiap clip ke semua akun/platform. Memilih slot paling awal; tie-break beban harian lalu total history. Menggunakan waktu akun, kuota global akun lintas campaign, jeda minimal 5 menit untuk rencana otomatis (`publishing.py:81`).
5. Akun yang pernah menerima clip sama/segmen overlap (status aktif termasuk failed/needs_attention/published) dilewati. Overlap dicegah sepanjang history aktif akun, bukan hanya per hari. Dengan satu akun, beberapa overlapping highlights dapat membuat preview satu batch gagal (`publishing.py:18`, `:104`).
6. Preview berisi akun/platform/schedule per clip; jadwal dapat diedit in-place sebelum confirm. Edit tidak harus persis salah satu jam rutin: waktu masa depan yang tidak bentrok/kuota lebih diterima. Akun tujuan tidak dapat diedit dengan API ini (`workflow.py:693`).
7. Satu timezone global (default Asia/Makassar/WITA), tampilan AM/PM; waktu publikasi tersimpan UTC. Perubahan timezone hanya Settings. Jadwal absolut yang telah dikirim tidak bergeser. Preview lama invalid saat timezone/jam/kuota/policy berubah; expiry 15 menit (`workflow.py:656`; `scheduling.py`).
8. Confirm merevalidasi dan reserve satu batch secara atomik; tombol ganda tidak menyebabkan duplikat. Preview yang telah confirm tidak bisa diedit lagi (`storage.py:223`).
9. Worker upload file final ke storage Repliz lalu membuat jadwal. **Upload diterima/scheduled ≠ konten sudah terbit**. Repliz bertugas menerbitkan pada waktunya; scheduler lokal bukan langsung menekan tombol sosmed (`workflow.py:748`, `app.py:58`).

### G. Cabang otomatis

- Trigger: `editing.review_mode == automatic` pada snapshot **dan job berakhir completed**. Partial/failed tidak menjalankan autopublish (`workflow.py:290`).
- Hanya clip tanpa satu pun warning/blocker yang auto-approve. Lalu preview + confirm memakai aturan biasa. Jadi otomatis tetap bergantung akun, kuota, caption, music, provider, slot, dan overlap.
- Brief yang mempunyai do/don't/aturan umum memunculkan warning review narasi; hasil seperti itu **tidak otomatis di-upload**. Kamera/audio warning juga menahan autopublish. Tidak boleh mengiklankan mode otomatis sebagai "semua pasti upload".
- Gagal preview memberi `attention` job. Jika tidak ada clip eligible, cabang ini tidak membuat publication. Tidak ada pemilihan campaign baru/sumber baru/revenue otomatis (`workflow.py:804`).

### H. Tracking dan pemulihan

- Sinkronisasi background setiap sekitar 5 menit ketika aplikasi hidup; bisa force sync. Status provider dipetakan pending→scheduled, process→publishing, error→failed, success→published (`workflow.py:819`, `:944`; `publishing.py:231`).
- Published + post ID → statistik provider disimpan sebagai snapshot + timestamp; link post dicari bila belum ada. Metric unavailable adalah error terpisah, bukan angka nol palsu. CSV tracking memakai timezone global + AM/PM (`workflow.py:837`, `:923`).
- Error sinkronisasi memakai backoff hingga 1 jam; tidak otomatis mengunggah ulang seluruh clip.
- Gagal sebelum create_schedule: retry aman bisa memakai media_url tersimpan. Hasil create_schedule tidak pasti: `needs_attention`, rekonsiliasi mencari satu jadwal persis cocok; tidak blind retry. Failed dengan schedule ID: retry via provider terhadap jadwal yang sama setelah mengecek status terbaru (`workflow.py:899`; `publishing.py:190`).
- Pembatalan lokal hanya queued/failed yang belum punya schedule ID dan hasil submit tidak uncertain. Jadwal yang sudah terkirim perlu dikelola di provider; belum ada reschedule/cancel provider di backend ini.

## 3. Entitas dan state untuk desain UI

| Entitas | Makna/pemisahan penting |
|---|---|
| Campaign workspace | Brief + aset + pool template + akun + aturan sekarang; editable |
| Campaign version | Snapshot produksi immutable; jejak versi untuk job/clip |
| Account profile | Satu genre/bahasa serta jam dan kuota per account ID lintas campaign |
| Source identity/cache | Video YouTube ID atau hash file; download/transcript bersama, bukan job |
| Job | Satu source + snapshot campaign + target count + log/status |
| Highlight/clip plan | Rentang sumber, pilihan template tetap, komposisi/rasio; belum tentu render final |
| Clip + clip revision | Hasil video, metadata, approval hash, warning/blocker; banyak hasil per job |
| Distribution preview | Rencana sementara 15 menit; editable sebelum confirm |
| Publication | Satu clip/revision/file/caption ke satu akun pada satu waktu; status upload/provider |
| Metric snapshot | Pengamatan statistik di waktu tertentu, bukan revenue |

Job: `queued → running → completed / partial / failed`; queued→paused; queued/paused→cancelled; running→cancelling→cancelled. Shutdown running/cancelling→interrupted. Resume interrupted/failed/partial/cancelled/paused→queued, urutan antrean baru, memakai cache yang valid (`workflow.py:610`, `storage.py:119`). Tidak ada pause-mid-render; tombol pause hanya job queued.

Clip renderer: `waiting → running → done/error/cancelled`. Clip review terpisah: `pending ↔ approved/rejected` (save kembali pending). Publication terpisah: `queued → uploading → publishing → scheduled → published` dengan failed/needs_attention/cancelled; `publishing` dapat muncul kembali dari status proses provider. Jangan gunakan satu badge "selesai" untuk semua lapisan ini.

## 4. API internal/legacy yang jangan otomatis dijadikan feature utama

Hasil pencarian nama method di semua JS frontend: `get_progress`, `get_clips_status`, `get_repliz_tiktok_music`, `get_jamendo_tracks`, `save_default_config`, `get_default_config`, `get_editing_templates`, `start_processing`, `campaign_readiness` tidak dipanggil dengan nama itu pada frontend saat audit. Sebagian dipakai internal (Jamendo), sebagian compatibility (start_processing), sebagian capabilities data yang sudah disertakan endpoint lain (readiness).

`quick_upload` dan `upload_clip` secara eksplisit mengembalikan `review_required`; tidak melewati review. Hook/TTS serta renderer Social/Bold masih ada untuk legacy/settings, tetapi kedua preset campaign baru mematikan Hook Maker. Backend `ai_select` lower-level tidak berarti template campaign sekarang dipilih AI: flow utama **weighted random**.

## 5. Batas yang perlu ditampilkan jelas dalam UI baru

1. Bisa siap produksi tetapi belum siap publikasi.
2. Target jumlah clip ≠ hasil final yang dijamin.
3. Campaign edited ≠ queued job ikut berubah.
4. Pool peluang template ≠ kuota pasti per batch.
5. Worker job serial ≠ setiap clip serial.
6. Render selesai ≠ disetujui ≠ upload tersimpan ≠ scheduled ≠ published.
7. Musik wajib tetapi kesuksesan auto bergantung konfigurasi/provider dan track tersedia.
8. Dua account settings milik akun lintas campaign, bukan per-campaign copy.
9. Default distribution satu clip satu akun; overlap history dapat menghabiskan kandidat akun.
10. Schedule inline hanya untuk preview belum confirm; bukan editor jadwal provider yang sudah terkirim.
11. Auto mode berjalan untuk job selesai dengan hasil tanpa warning; tetap mempunyai jalur manual/attention.
12. AI/heuristik kualitas cerita, subtitle, face tracking perlu review; belum ada jaminan "100% benar" atau reproduksi pixel-identical semua video sumber.

