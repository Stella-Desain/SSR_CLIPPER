# INSTRUKSI IMPLEMENTASI — Subtitle V2 & V3 (SSR_CLIPPER)

**Target:** dikerjakan oleh AI coding assistant (Gemini) di repo `SSR_CLIPPER`
(branch `Master`). Dokumen ini berdiri sendiri, tidak bergantung ke dokumen
`GEMINI_INSTRUCTIONS_campaign.md` / `GEMINI_INSTRUCTIONS_upload.md` yang
sudah ada di `source sementara/`. Taruh file ini juga di folder yang sama.

**Tujuan:** nambah dropdown baru "Subtitle Style" di halaman **Create Clip**
(bagian Features) dengan **3 pilihan**: **Subtitle V1** (perilaku lama,
fallback), **Subtitle V2** (fix timing + pop animation, **default**), dan
**Subtitle V3** (V2 + emphasis lebih besar di kata-kata "power word",
opsional, bukan default).

> Catatan: V3 di dokumen ini BUKAN port 1:1 dari "advanced kinetic
> typography" di repo referensi (yang butuh AI call buat milih kata emphasis
> + font custom + manual pixel positioning). Itu terlalu berat/rapuh buat
> codebase ini — lihat §0 poin 1 buat alasan lengkap kenapa scope-nya
> disederhanakan begini.

---

## 0. Fakta penting dari source code

1. **Riset referensi** (`opensource-clipping`, repo terpisah — HANYA dibaca
   untuk referensi teknik, TIDAK di-clone/dipakai library-nya) punya 2 mode
   render ASS: (a) *karaoke sederhana* — tiap kata jadi 1 event `Dialogue`,
   window durasi kata aktif = **sampai kata berikutnya mulai diucapkan**
   (bukan `end` milik kata itu sendiri), teks direwrite ulang tiap event
   dengan 1 kata diwarnai kuning; (b) *advanced kinetic typography* — posisi
   tiap kata dihitung manual pakai PIL (`ImageFont.getlength`) buat word-wrap
   manual, plus tag `\pos`/`\move`/`\t` buat animasi bounce/stagger, kata
   mana yang di-emphasis ditentukan AI (`typography_plan` dari Gemini).
   **Mode (b) versi PERSIS/1:1 sengaja TIDAK dibangun** — 2 alasan konkret:
   (1) butuh 1x panggilan AI ekstra per klip cuma buat milih kata emphasis
   → nambah biaya + waktu proses nyata (bukan cuma polish gratis kayak V2),
   dan (2) manual pixel positioning butuh file font `.ttf` fisik buat diukur
   PIL — SSR_CLIPPER cuma pakai nama font sistem (`"Arial Black"`, string
   biasa, bukan path file), TIDAK ADA file `.ttf` yang dibundle
   (`assets/` cuma isi icon & gambar dokumentasi), dan path font sistem beda
   antara Windows/macOS (app ini build buat dua-duanya — lihat
   `build.spec`/`build_macos.spec`) → gampang patah, terlalu rapuh buat
   dikerjain junior dev. **Subtitle V3** di dokumen ini adalah versi
   **disederhanakan**: efek "kata penting jadi lebih menonjol" tetap dapet,
   TAPI pemilihan kata emphasis pakai **daftar kata statis** (bukan AI call)
   dan render-nya tetap inline kayak V2 (bukan manual `\pos`, tanpa font
   baru). Detail lengkap di §2b/§3.2b.
2. SSR_CLIPPER **sudah** punya versi word-by-word karaoke sendiri:
   `create_ass_subtitle_capcut()` di `clipper_core.py:3552`. Ini yang nanti
   disebut **"Subtitle V1"**. Bedanya dengan referensi: window durasi tiap
   kata pakai `current_word.end` milik kata itu sendiri (`clipper_core.py:3590`),
   BUKAN start-time kata berikutnya — jadi ada micro-gap/kurang nempel
   dibanding pola di poin 1(a). Subtitle V2 (dokumen ini) memperbaiki ini.
3. **BUG kritis pre-existing, WAJIB diperbaiki dulu sebagai prasyarat** —
   kalau tidak, fitur ini (dan semua fitur lain) tidak bisa dites sama
   sekali: fungsi `_run()` di `app.py:215` **tidak punya parameter
   `campaign_id`**, padahal dipakai di `app.py:295`
   (`core.process(..., campaign_id=campaign_id)`) dan di-pass sebagai
   argumen ke-9 dari `threading.Thread` di `app.py:209`. Efeknya: **setiap
   klik tombol "Create Clip" sekarang langsung gagal** dengan
   `NameError: name 'campaign_id' is not defined` (ketangkep silent oleh
   `try/except` di `app.py:303`, job langsung berstatus "Failed", tidak ada
   crash yang keliatan di UI selain status error). Perbaikan bug ini
   digabung di §3.1 karena momennya pas (kita toh sedang mengubah signature
   fungsi yang sama untuk menambah parameter `subtitle_style`).
4. Pola "Features" toggle di Create Clip (`web/components/home.js` baris
   ~85-136) pakai helper `makeToggle()` yang menghasilkan `{element, input,
   subEl}`. `subEl` itu dropdown kecil di bawah label toggle, TAPI fungsinya
   sudah dipakai untuk sinkronisasi nama model AI provider (lihat
   `web/app.js` baris 673-960, contoh: `captionSub` nampilin model Whisper
   yang aktif). **JANGAN pakai/modifikasi `subEl` manapun buat opsi
   Subtitle Style** — bisa merusak sinkronisasi AI model yang sudah jalan.
   Buat dropdown baru yang berdiri sendiri, taruh di area "Subtitle
   Language" (`home.js` baris ~153-164), pola field biasa (bukan lewat
   `makeToggle`).
5. Alur render subtitle saat ini: `process()` (`clipper_core.py:605`) →
   `process_clip()` (`clipper_core.py:2589`) →
   `add_captions_api_with_progress()` (`clipper_core.py:4558`) →
   `create_ass_subtitle_capcut()` (`clipper_core.py:3552`) → FFmpeg burn
   (`-vf ass='...'`). Semua di file yang sama, `clipper_core.py`. Dropdown
   di UI harus tembus jalur ini sampai ke pemilihan fungsi ASS builder mana
   yang dipanggil.

---

## 1. Scope

**Dikerjakan:**
- Fix bug `campaign_id` di `_run()` (`app.py`) — prasyarat wajib, lihat §3.1.
- Fungsi baru `create_ass_subtitle_v2()` di `clipper_core.py` — word-by-word
  highlight dengan window durasi "sampai kata berikutnya mulai" + animasi
  scale "pop" di kata aktif pakai tag `\t()` inline (tanpa perlu `\pos`
  manual atau font custom).
- Fungsi baru `create_ass_subtitle_v3()` di `clipper_core.py` — sama seperti
  V2, TAPI kata yang match daftar statis `POWER_WORDS_V3` dapat animasi pop
  yang lebih besar (efek "kata penting lebih menonjol", tanpa AI call, tanpa
  font baru). Detail §2b/§3.2b.
- Parameter baru `subtitle_style` (nilai `"v1"`, `"v2"`, atau `"v3"`)
  di-thread dari UI sampai ke pemanggilan ASS builder, default `"v2"` di
  **setiap** layer (Python maupun JS).
- Dropdown baru **"Subtitle Style"** di halaman Create Clip, 3 opsi:
  "Subtitle V2 (Dynamic Word Pop)" **terpilih sebagai default**, "Subtitle
  V3 (Kinetic Emphasis)", dan "Subtitle V1 (Classic)".
- Persist pilihan dropdown ke `default_clip_settings` (pola save/load yang
  sudah ada, sama seperti field lain di form itu).

**TIDAK dikerjakan (jangan disentuh):**
- Versi 1:1 dari advanced mode `opensource-clipping` yang PAKAI AI call buat
  milih kata emphasis, font custom per gaya, dan manual `\pos`/`\move`
  pixel-perfect positioning. Alasan lengkap kenapa ini di-skip ada di §0
  poin 1 — kalau nanti tetap dibutuhkan versi itu, itu dokumen instruksi
  terpisah, bukan bagian dari §2b/§3.2b di sini.
- Mengubah `chunk_size` pengelompokan kata (tetap 4 kata per baris, identik
  V1/V2, dipakai juga di V3).
- Mengubah isi/perilaku `create_ass_subtitle_capcut()` (V1) ATAU
  `create_ass_subtitle_v2()` (V2) sama sekali — dua-duanya HARUS tetap
  persis seperti sekarang, V3 adalah fungsi baru yang berdiri sendiri.
- Apa pun di luar 3 file ini: `clipper_core.py`, `app.py`,
  `web/components/home.js`, `web/app.js`.
- Bug/TODO lain yang ditemukan di luar scope subtitle — cukup catat
  `// TODO:`, jangan diperbaiki di PR yang sama (lihat §6).

---

## 2. Desain teknis Subtitle V2 (ikuti persis, jangan improvisasi)

- **Base ASS header/style:** sama persis dengan V1 (font `Arial Black`,
  size `65`, warna, outline, margin — semua identik). Cuma `Title:` di
  `[Script Info]` diganti jadi `Auto-generated captions (V2)` supaya gampang
  dibedain pas debug file `.ass` mentahnya.
- **Chunking:** sama seperti V1, `chunk_size = 4` kata per baris. Jangan
  diubah.
- **Timing tiap kata (INI inti perubahan dibanding V1):**
  - `word_start = current_word.start + time_offset` (sama seperti V1).
  - Kalau kata ini **bukan kata terakhir di dalam chunk**:
    `word_end = chunk[j + 1].start + time_offset` — window kata aktif
    berakhir tepat saat kata berikutnya mulai diucapkan. Ini pola persis
    dari `opensource-clipping` (`clipping/studio/subtitles.py` baris
    ~172-180), bikin transisi highlight lebih nempel ke suara asli
    dibanding V1.
  - Kalau kata ini **kata terakhir di chunk**: `word_end = current_word.end
    + time_offset` (fallback, sama seperti V1 — tidak ada kata berikutnya
    dalam chunk yang sama buat dijadikan patokan).
- **Animasi kata aktif:** tambahkan 2 tag transform `\t()` di override block
  kata yang lagi aktif, SEBELUM tag warna `\c&H00FFFF&`. Efeknya: kata itu
  membesar dari 100% → 122% dalam 80ms pertama, lalu balik ke 100% dalam
  80ms berikutnya ("pop" sekali tiap kata muncul).
  - Karena tiap kata = 1 `Dialogue` event sendiri (bukan digabung 1 baris
    seperti mode advanced di referensi), `\t(0,80,...)` **otomatis relatif
    ke waktu mulai event itu sendiri** (= `word_start`). **Tidak perlu**
    hitung offset milidetik manual dari awal segmen/klip seperti yang
    dilakukan mode advanced di `opensource-clipping` — itu bagian yang
    bikin kode referensi rumit, dan tidak relevan di sini.
- **Efek samping yang DITERIMA, jangan dicoba "diperbaiki":** pas scale lagi
  di puncak (122%, ~80ms), kata aktif bisa numpuk sedikit dengan kata di
  sebelahnya secara visual. Ini normal untuk efek pop instan gaya CapCut,
  dan **tidak butuh** `\pos` manual buat mengatasinya — itu domain "advanced
  mode" yang sengaja di-skip di scope ini (§1).

## 2b. Desain teknis Subtitle V3 (ikuti persis, jangan improvisasi)

V3 = V2 + 1 lapis tambahan: kata tertentu ("power word") dapat animasi pop
yang lebih gede. Semua yang sudah berlaku di §2 (base style, chunking,
timing "sampai kata berikutnya mulai") **berlaku sama persis** di V3, tidak
diulang di sini.

- **Sumber daftar kata emphasis:** konstanta Python statis
  `POWER_WORDS_V3` (set berisi string kapital), didefinisikan tepat di atas
  fungsi `create_ass_subtitle_v3()`. **Bukan** dari AI, **bukan** dari
  `typography_plan` — murni string matching. User bisa edit isi set ini
  kapan saja tanpa nyentuh logic lain.
- **Cara cek match:** untuk kata yang lagi aktif (`k == j`), bersihkan dulu
  tanda baca di ujung kata (pakai `.strip('.,!?"\':;()')`, **jangan** pakai
  modul `string` — biar tidak perlu nambah `import` baru di
  `clipper_core.py`), lalu `.upper()` (transkrip sudah di-uppercase duluan
  di alur yang ada, jadi tinggal cocokkan langsung ke isi `POWER_WORDS_V3`
  yang juga kapital semua).
- **Animasi kata power word:** scale 100% → **140%** (bukan 122% seperti V2)
  dalam 80ms, balik ke 100% dalam 80ms berikutnya. Warna highlight TETAP
  kuning sama seperti kata aktif biasa (`&H00FFFF&`) — **jangan** tambah
  warna baru, biar bahasa visualnya tetap konsisten ("kuning = lagi
  diucapkan"), cuma ukurannya yang beda buat kasih penekanan.
- **Kata aktif yang BUKAN power word:** animasinya identik V2 (100% →
  122% → 100%).
- Tidak ada perubahan lain di luar 2 poin di atas (tag warna, timing window,
  chunking, header ASS — semua sama persis V2).

---

## 3. Backend

### 3.1 WAJIB DIKERJAKAN DULU — fix bug `campaign_id` + siapkan param baru di `app.py`

**a) `app.py:215`** — ganti signature `_run()`:

```python
# SEBELUM (baris 215) — BUG: campaign_id tidak ada di sini padahal dipakai di baris 295
def _run(self, url, num_clips, add_captions, add_hook, subtitle_lang, portrait, highlight_finder, yt_title_maker):

# SESUDAH
def _run(self, url, num_clips, add_captions, add_hook, subtitle_lang, portrait, highlight_finder, yt_title_maker, campaign_id, subtitle_style):
```

**b) `app.py:295`** — teruskan `subtitle_style` ke `core.process()`:

```python
# SEBELUM
core.process(url, num_clips=num_clips, add_captions=add_captions, add_hook=add_hook, portrait=portrait, highlight_finder=highlight_finder, yt_title_maker=yt_title_maker, campaign_id=campaign_id)

# SESUDAH
core.process(url, num_clips=num_clips, add_captions=add_captions, add_hook=add_hook, portrait=portrait, highlight_finder=highlight_finder, yt_title_maker=yt_title_maker, campaign_id=campaign_id, subtitle_style=subtitle_style)
```

**c) `app.py:192`** — tambah parameter `subtitle_style` di `start_processing()`,
default `"v2"`:

```python
# SEBELUM
def start_processing(self, url, num_clips=5, add_captions=True, add_hook=False, subtitle_lang="id", portrait=False, highlight_finder=True, yt_title_maker=True, campaign_id=None):

# SESUDAH
def start_processing(self, url, num_clips=5, add_captions=True, add_hook=False, subtitle_lang="id", portrait=False, highlight_finder=True, yt_title_maker=True, campaign_id=None, subtitle_style="v2"):
```

**d) `app.py:209`** — tambahkan `subtitle_style` di akhir tuple `args`
(urutan argumen lain JANGAN diubah):

```python
# SEBELUM
args=(url, int(num_clips), bool(add_captions), bool(add_hook), subtitle_lang, bool(portrait), bool(highlight_finder), bool(yt_title_maker), campaign_id),

# SESUDAH
args=(url, int(num_clips), bool(add_captions), bool(add_hook), subtitle_lang, bool(portrait), bool(highlight_finder), bool(yt_title_maker), campaign_id, subtitle_style),
```

### 3.2 Fungsi baru `create_ass_subtitle_v2()` — `clipper_core.py`

Taruh **PERSIS** di antara akhir fungsi `create_ass_subtitle_capcut`
(baris 3629, baris kosong sebelum `def format_time`) dan `def format_time`
(baris 3631). Jangan ubah satu karakter pun di `create_ass_subtitle_capcut`
yang sudah ada — fungsi baru ini berdiri sendiri, copy-paste persis di
bawah ini:

```python
    def create_ass_subtitle_v2(self, transcript, output_path: str, time_offset: float = 0):
        """Create ASS subtitle file - Subtitle V2: word-by-word highlight
        dengan window durasi 'sampai kata berikutnya mulai' (lebih snappy,
        tanpa gap) + animasi scale-pop di kata aktif. Base visual style
        identik dengan V1 (CapCut style)."""

        ass_content = """[Script Info]
Title: Auto-generated captions (V2)
ScriptType: v4.00+
WrapStyle: 0
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial Black,65,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,2,2,50,50,400,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

        events = []

        if hasattr(transcript, 'words') and transcript.words:
            words = transcript.words
            chunk_size = 4

            for i in range(0, len(words), chunk_size):
                chunk = words[i:i + chunk_size]
                if not chunk:
                    continue

                for j, current_word in enumerate(chunk):
                    word_start = current_word.start + time_offset
                    if j < len(chunk) - 1:
                        word_end = chunk[j + 1].start + time_offset
                    else:
                        word_end = current_word.end + time_offset

                    if word_end <= word_start:
                        continue

                    text_parts = []
                    for k, w in enumerate(chunk):
                        word_text = w.word.strip().upper()
                        if k == j:
                            # PENTING: "\\t" di sini WAJIB double backslash persis
                            # seperti ini (literal Python f-string), JANGAN
                            # disederhanakan jadi "\t" — kalau cuma 1 backslash,
                            # Python akan baca itu sebagai karakter TAB, bukan
                            # tag ASS, dan subtitle akan rusak/tidak muncul.
                            text_parts.append(
                                f"{{\\c&H00FFFF&\\t(0,80,\\fscx122\\fscy122)\\t(80,160,\\fscx100\\fscy100)}}{word_text}{{\\c&HFFFFFF&}}"
                            )
                        else:
                            text_parts.append(word_text)

                    text = " ".join(text_parts)

                    events.append({
                        'start': self.format_time(word_start),
                        'end': self.format_time(word_end),
                        'text': text
                    })

        elif hasattr(transcript, 'segments') and transcript.segments:
            for segment in transcript.segments:
                start = segment.get('start', 0) + time_offset
                end = segment.get('end', 0) + time_offset
                text = segment.get('text', '').strip().upper()

                if text:
                    events.append({
                        'start': self.format_time(start),
                        'end': self.format_time(end),
                        'text': text
                    })

        for event in events:
            ass_content += f"Dialogue: 0,{event['start']},{event['end']},Default,,0,0,0,,{event['text']}\n"

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(ass_content)
```

### 3.2b Fungsi baru `create_ass_subtitle_v3()` — `clipper_core.py`

Taruh **PERSIS** di bawah fungsi `create_ass_subtitle_v2()` yang barusan
ditambahkan di §3.2 (jadi urutannya: `create_ass_subtitle_capcut` →
`create_ass_subtitle_v2` → `create_ass_subtitle_v3` → `format_time`).
Copy-paste persis, termasuk konstanta `POWER_WORDS_V3` di paling atas (di
luar/sebelum `def`, sejajar level indentasi method lain di dalam class —
taruh sebagai class attribute, PERSIS seperti contoh di bawah):

```python
    # Daftar kata "power word" buat Subtitle V3 — kata di daftar ini dapat
    # animasi pop LEBIH BESAR (140%) dibanding kata aktif biasa (122%).
    # Silakan tambah/kurangi sesuai selera, tinggal edit set ini, tidak ada
    # logic lain yang perlu diubah. Semua HARUS kapital (huruf besar semua).
    POWER_WORDS_V3 = {
        "GILA", "PARAH", "TERNYATA", "RAHASIA", "JANGAN", "HARUS", "WOW",
        "SERIUS", "SUMPAH", "PENTING", "BAHAYA", "SEKARANG", "LANGSUNG",
        "TERBUKTI", "FAKTA", "MUSTAHIL", "WAJIB", "DILARANG",
        "NEVER", "ALWAYS", "SECRET", "STOP", "WARNING", "CRAZY", "INSANE",
        "PROOF", "TRUTH", "NOBODY", "EVERYONE",
    }

    def create_ass_subtitle_v3(self, transcript, output_path: str, time_offset: float = 0):
        """Create ASS subtitle file - Subtitle V3: sama persis seperti V2
        (window durasi next-word-start + pop animation), TAPI kata yang
        match POWER_WORDS_V3 dapat animasi pop lebih besar (140% vs 122%).
        Tidak butuh AI call, tidak butuh font baru, tidak butuh manual
        positioning."""

        ass_content = """[Script Info]
Title: Auto-generated captions (V3)
ScriptType: v4.00+
WrapStyle: 0
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial Black,65,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,2,2,50,50,400,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

        events = []

        if hasattr(transcript, 'words') and transcript.words:
            words = transcript.words
            chunk_size = 4

            for i in range(0, len(words), chunk_size):
                chunk = words[i:i + chunk_size]
                if not chunk:
                    continue

                for j, current_word in enumerate(chunk):
                    word_start = current_word.start + time_offset
                    if j < len(chunk) - 1:
                        word_end = chunk[j + 1].start + time_offset
                    else:
                        word_end = current_word.end + time_offset

                    if word_end <= word_start:
                        continue

                    text_parts = []
                    for k, w in enumerate(chunk):
                        word_text = w.word.strip().upper()
                        if k == j:
                            word_clean = word_text.strip('.,!?"\':;()')
                            if word_clean in self.POWER_WORDS_V3:
                                scale_peak = 140
                            else:
                                scale_peak = 122
                            # PENTING: "\\t" WAJIB double backslash persis
                            # seperti ini (literal Python f-string) — sama
                            # aturan kayak di create_ass_subtitle_v2().
                            text_parts.append(
                                f"{{\\c&H00FFFF&\\t(0,80,\\fscx{scale_peak}\\fscy{scale_peak})\\t(80,160,\\fscx100\\fscy100)}}{word_text}{{\\c&HFFFFFF&}}"
                            )
                        else:
                            text_parts.append(word_text)

                    text = " ".join(text_parts)

                    events.append({
                        'start': self.format_time(word_start),
                        'end': self.format_time(word_end),
                        'text': text
                    })

        elif hasattr(transcript, 'segments') and transcript.segments:
            for segment in transcript.segments:
                start = segment.get('start', 0) + time_offset
                end = segment.get('end', 0) + time_offset
                text = segment.get('text', '').strip().upper()

                if text:
                    events.append({
                        'start': self.format_time(start),
                        'end': self.format_time(end),
                        'text': text
                    })

        for event in events:
            ass_content += f"Dialogue: 0,{event['start']},{event['end']},Default,,0,0,0,,{event['text']}\n"

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(ass_content)
```

### 3.3 Update `add_captions_api_with_progress()` — `clipper_core.py:4558`

**a)** Tambah parameter `subtitle_style` di signature:

```python
# SEBELUM
def add_captions_api_with_progress(self, input_path: str, output_path: str, audio_source: str = None, time_offset: float = 0, progress_callback=None):

# SESUDAH
def add_captions_api_with_progress(self, input_path: str, output_path: str, audio_source: str = None, time_offset: float = 0, progress_callback=None, subtitle_style: str = "v2"):
```

**b)** Di dalam fungsi yang sama, cari baris `clipper_core.py:4639`
(`self.create_ass_subtitle_capcut(transcript, ass_file, time_offset)`),
ganti jadi pemilihan berdasarkan `subtitle_style`:

```python
# SEBELUM
self.create_ass_subtitle_capcut(transcript, ass_file, time_offset)

# SESUDAH
if subtitle_style == "v1":
    self.create_ass_subtitle_capcut(transcript, ass_file, time_offset)
elif subtitle_style == "v3":
    self.create_ass_subtitle_v3(transcript, ass_file, time_offset)
else:
    self.create_ass_subtitle_v2(transcript, ass_file, time_offset)
```

Perhatikan: default-nya `else` (jatuh ke V2) — jadi kalau ada value
`subtitle_style` yang tidak dikenal/kosong, tetap aman jatuh ke V2, bukan
error. Urutan `if/elif/else` di atas WAJIB persis begini (v1 dicek duluan,
v3 kedua, sisanya jatuh ke v2) — jangan diubah urutannya.

### 3.4 Thread parameter `subtitle_style` ke `process_clip()` dan `process()`

**a) `clipper_core.py:2589`** — tambah parameter di `process_clip()`:

```python
# SEBELUM
def process_clip(self, video_path: str, highlight: dict, index: int, total_clips: int = 1, add_captions: bool = True, add_hook: bool = True, pre_cut: bool = False, portrait: bool = True):

# SESUDAH
def process_clip(self, video_path: str, highlight: dict, index: int, total_clips: int = 1, add_captions: bool = True, add_hook: bool = True, pre_cut: bool = False, portrait: bool = True, subtitle_style: str = "v2"):
```

**b)** Di dalam `process_clip()`, ada **2 tempat** yang manggil
`add_captions_api_with_progress()` — `clipper_core.py:2757` (jalur
watermark aktif → `temp_captioned`) dan `clipper_core.py:2766` (jalur tanpa
watermark → `final_file`). **Kedua-duanya** wajib ditambah
`subtitle_style=subtitle_style`:

```python
# SEBELUM (baris 2757)
self.add_captions_api_with_progress(str(current_output), str(temp_captioned), audio_source, hook_duration,
    lambda p: clip_progress("Adding captions...", current_step, p))

# SESUDAH
self.add_captions_api_with_progress(str(current_output), str(temp_captioned), audio_source, hook_duration,
    lambda p: clip_progress("Adding captions...", current_step, p), subtitle_style=subtitle_style)
```

```python
# SEBELUM (baris 2766)
self.add_captions_api_with_progress(str(current_output), str(final_file), audio_source, hook_duration,
    lambda p: clip_progress("Adding captions...", current_step, p))

# SESUDAH
self.add_captions_api_with_progress(str(current_output), str(final_file), audio_source, hook_duration,
    lambda p: clip_progress("Adding captions...", current_step, p), subtitle_style=subtitle_style)
```

**c) `clipper_core.py:605`** — tambah parameter di `process()`:

```python
# SEBELUM
def process(self, url: str, num_clips: int = 5, add_captions: bool = True, add_hook: bool = True, portrait: bool = True, highlight_finder: bool = True, yt_title_maker: bool = True, campaign_id: str = None):

# SESUDAH
def process(self, url: str, num_clips: int = 5, add_captions: bool = True, add_hook: bool = True, portrait: bool = True, highlight_finder: bool = True, yt_title_maker: bool = True, campaign_id: str = None, subtitle_style: str = "v2"):
```

**d) `clipper_core.py:659`** — teruskan ke `process_clip()`:

```python
# SEBELUM
self.process_clip(video_path, highlight, i, total_clips, add_captions=add_captions, add_hook=add_hook, portrait=portrait)

# SESUDAH
self.process_clip(video_path, highlight, i, total_clips, add_captions=add_captions, add_hook=add_hook, portrait=portrait, subtitle_style=subtitle_style)
```

Cek juga: `process_clip()` dan `process()` masing-masing **cuma punya 1**
titik pemanggilan di seluruh codebase (sudah diverifikasi) — jadi tidak ada
tempat lain yang perlu disentuh untuk 2 fungsi ini.

---

## 4. Frontend

### 4.1 Dropdown baru "Subtitle Style" — `web/components/home.js`

Cari blok "Subtitle select" yang sudah ada (`home.js` baris ~153-164,
diakhiri `configBody.appendChild(subtitleSelect);`). **Tepat setelah** baris
itu, tambahkan blok baru (pola identik dengan blok Subtitle Language di
atasnya, jangan pakai `makeToggle()` — lihat §0 poin 4):

```javascript
  // Subtitle Style select (V2 = default)
  const subtitleStyleLabel = document.createElement('label');
  subtitleStyleLabel.className = 'field-label';
  subtitleStyleLabel.style.cssText = 'display:block;margin-top:10px;margin-bottom:6px;';
  subtitleStyleLabel.textContent = 'Subtitle Style';
  configBody.appendChild(subtitleStyleLabel);
  const subtitleStyleSelect = document.createElement('select');
  subtitleStyleSelect.className = 'input';
  subtitleStyleSelect.id = 'subtitle-style';
  subtitleStyleSelect.style.marginBottom = '10px';
  subtitleStyleSelect.innerHTML = '<option value="v2" selected>Subtitle V2 (Dynamic Word Pop)</option><option value="v3">Subtitle V3 (Kinetic Emphasis)</option><option value="v1">Subtitle V1 (Classic)</option>';
  configBody.appendChild(subtitleStyleSelect);
```

### 4.2 Wiring field baru — masih di `home.js`

**a) Object `fields` yang di-return** (baris ~374-401) — cari baris
`subtitle: subtitleSelect,`, tambahkan baris baru **tepat setelahnya**:

```javascript
      subtitle: subtitleSelect,
      subtitleStyle: subtitleStyleSelect,
```

**b) `loadDefaultConfig()`** (baris ~337-350) — tambahkan 1 baris baru
mengikuti pola field lain di fungsi yang sama:

```javascript
          if (config.subtitle_style !== undefined) subtitleStyleSelect.value = config.subtitle_style;
```

**c) Listener `saveConfigBtn`** (baris ~353-372), di dalam object
`settings` — tambahkan key baru mengikuti pola key lain:

```javascript
      subtitle_style: subtitleStyleSelect.value,
```

### 4.3 `web/app.js`

**a) `lockControls()`** (baris ~142-155) — cari baris
`homeView.fields.subtitle.disabled = state;`, tambahkan baris baru **tepat
setelahnya**:

```javascript
  homeView.fields.subtitleStyle.disabled = state;
```

**b) Fungsi `start()`** (baris ~268-290) — cari pemanggilan
`window.pywebview.api.start_processing(...)`. Tambahkan
`homeView.fields.subtitleStyle.value` sebagai argumen **terakhir**
(urutan argumen yang sudah ada JANGAN diubah):

```javascript
    const res = await window.pywebview.api.start_processing(
      url,
      parseInt(homeView.fields.clips.value, 10),
      homeView.fields.captions.checked,
      homeView.fields.hook.checked,
      homeView.fields.subtitle.value,
      homeView.fields.portrait.checked,
      homeView.fields.highlight.checked,
      homeView.fields.ytTitle.checked,
      homeView.fields.campaign ? homeView.fields.campaign.value : "",
      homeView.fields.subtitleStyle.value
    );
```

---

## 5. Checklist testing manual

- [ ] Buka halaman Create Clip → dropdown baru **"Subtitle Style"** muncul
      persis di bawah "Subtitle Language", default terpilih **"Subtitle V2
      (Dynamic Word Pop)"**.
- [ ] Klik "Save Default Configuration", reload app → dropdown tetap ke
      value yang barusan disimpan (verifikasi §4.2b/c jalan).
- [ ] Generate 1 clip pendek dengan setting default (V2 aktif) → proses
      **tidak** langsung gagal dengan error `campaign_id` (ini verifikasi
      fix bug §3.1 — kalau masih muncul error ini, berarti §3.1 belum
      kepasang dengan benar).
- [ ] Buka video hasil: subtitle muncul kata-per-kata, kata yang lagi aktif
      ada efek "membesar sebentar lalu balik normal" (pop) barengan sama
      highlight kuning nyala, transisi highlight ke kata berikutnya terasa
      lebih nempel ke suara dibanding sebelumnya.
- [ ] Ganti dropdown ke **"Subtitle V1 (Classic)"**, generate ulang → hasil
      subtitle balik ke perilaku lama (highlight flat, tanpa animasi
      scale, tanpa perubahan lain).
- [ ] Test kombinasi Hook aktif (`add_hook=true`) + Watermark aktif → pastikan
      `subtitle_style` yang dipilih tetap konsisten diterapkan (cek §3.4b,
      2 jalur `temp_captioned` dan `final_file` dua-duanya kepasang).
- [ ] Buka file `.ass` mentah dari salah satu clip V2 (ada di temp folder
      selama proses berjalan, atau tambahkan log sementara kalau perlu) →
      pastikan tag `\t(0,80,\fscx122\fscy122)` muncul sebagai teks biasa,
      **bukan** karakter tab/whitespace aneh (verifikasi warning escaping
      di §3.2 diikuti dengan benar).
- [ ] Ganti dropdown ke **"Subtitle V3 (Kinetic Emphasis)"**, pastikan
      transkrip clip yang digenerate ngandung minimal 1 kata yang ada di
      `POWER_WORDS_V3` (kalau perlu, generate clip dari video yang emang
      ngomong salah satu kata itu, misal "HARUS" atau "TERNYATA") →
      cek kata itu pop-nya kelihatan JAUH lebih besar dibanding kata aktif
      biasa di sekitarnya.
- [ ] Generate clip V3 dari video yang TIDAK ngandung kata apa pun dari
      `POWER_WORDS_V3` → pastikan hasilnya tetap identik V2 (tidak ada error,
      tidak ada kata yang tiba-tiba pop besar tanpa alasan).
- [ ] Cek `.ass` mentah dari clip V3 → pastikan cuma value `\fscx`/`\fscy`
      yang beda (122 vs 140) antara kata biasa dan power word, warna
      `\c&H00FFFF&` harus tetap sama persis di kedua kasus.

---

## 6. Reminder — jangan scope creep

Jangan bangun versi 1:1 advanced kinetic typography (AI call buat milih
kata emphasis, font custom per gaya, manual `\pos`/`\move` pixel-perfect)
— itu di luar scope dokumen ini (lihat §0 poin 1 buat alasannya), proyek
terpisah kalau nanti memang dibutuhkan. Jangan ubah
`create_ass_subtitle_capcut()` (V1) atau `create_ass_subtitle_v2()` (V2)
sama sekali — V3 murni fungsi tambahan baru. Kalau nemu bug atau hal aneh
lain di luar yang disebut di §0/§3.1 selama ngerjain ini, cukup catat
`// TODO:` di kode, **jangan** diperbaiki di PR yang sama.
