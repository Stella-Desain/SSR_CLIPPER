# FEATURE — Ganti Sistem Musik: Jamendo (library aman lisensi) + AI Editor Feeling + Mixing Lokal ffmpeg

**File yang diubah:** `config/config_manager.py` (2 lokasi) dan `app.py` (3 lokasi: 1 insert method baru, 1 replace method jadi 3 method baru, 1 replace body method)
**Model eksekutor:** Opus 4.6 thinking. **Aturan MD tetap sama seperti sebelumnya** — semua lokasi & kode sudah didesain persis, kamu (eksekutor) TIDAK PERLU memutuskan logic apapun. Cari blok "Kode SEKARANG" PERSIS, ganti/tambah dengan blok "Kode BARU". Kalau ketemu bagian yang TIDAK PERSIS sama, STOP dan laporkan — jangan ditebak/dipaksa cocokin.
**Tidak ada dependency baru** — semua pakai library yang sudah ada di project (`requests`, `subprocess`, `openai`, `get_ffmpeg_path` dari `utils/helpers.py`, semua sudah ter-import di `app.py`). Gak perlu ubah `requirements.txt`.

---

## Konteks — Apa yang berubah secara arsitektur (baca dulu)

Sistem musik LAMA: ambil "musik trending TikTok" dari Repliz (`get_repliz_tiktok_music()`, butuh tier Premium+), AI pilih 1 track, lalu track itu di-attach lewat field `additionalInfo.music` di Repliz Schedule API. Masalahnya: mekanisme attach resmi ini bikin **audio asli video hilang total** digantikan sound resmi tersebut (perilaku bawaan TikTok, bukan bug — sudah dikonfirmasi lewat riset sebelumnya).

Sistem musik BARU (yang dibangun di MD ini):
1. Musik diambil dari **Jamendo** (API publik, cukup `client_id`, katalog Creative Commons) — bukan lagi dari Repliz/TikTok.
2. AI (`_select_background_sound`) nentuin **mood/tempo/volume** yang cocok buat clip (bukan milih dari daftar tetap kayak sebelumnya).
3. Titik potong track (detik berapa sampai berapa) dihitung dari field `waveform.peaks` yang Jamendo kasih di response API — **gak perlu download+analisis audio manual**.
4. Musik di-**mix ke video secara LOKAL pakai ffmpeg** (auto-ducking pakai filter `sidechaincompress`, biar volume musik otomatis turun pas ada dialog) — SEBELUM di-upload. Jadi audio asli clip TETAP ADA, musiknya nempel di situ, bukan gantiin.
5. `additionalInfo.music` di Repliz Schedule API **gak dipakai lagi sama sekali** (selalu kosong) — karena musiknya udah jadi bagian dari file video itu sendiri.
6. Karena kebanyakan track Jamendo itu CC-BY (boleh dipakai komersial, TAPI wajib kasih kredit), caption otomatis ditambahin baris atribusi artis.

---

## TASK 1 — `config/config_manager.py`: tambah default Jamendo di jalur migrasi config lama

Cari blok ini (sekitar baris 73-78), PERSIS seperti ini:

```python
                # Add default Repliz settings if not exists
                if "repliz" not in config:
                    config["repliz"] = {
                        "access_key": "",
                        "secret_key": ""
                    }
                
```

GANTI jadi (nambahin blok baru tepat SETELAH blok Repliz, blok Repliz-nya sendiri TIDAK diubah):

```python
                # Add default Repliz settings if not exists
                if "repliz" not in config:
                    config["repliz"] = {
                        "access_key": "",
                        "secret_key": ""
                    }
                
                # Add default Jamendo settings if not exists
                if "jamendo" not in config:
                    config["jamendo"] = {
                        "client_id": ""
                    }
                
```

---

## TASK 2 — `config/config_manager.py`: tambah default Jamendo di config fresh/baru

Cari blok ini (sekitar baris 121-124), PERSIS seperti ini:

```python
            "repliz": {
                "access_key": "",
                "secret_key": ""
            },
            "gpu_acceleration": {
                "enabled": True
            }
```

GANTI jadi:

```python
            "repliz": {
                "access_key": "",
                "secret_key": ""
            },
            "jamendo": {
                "client_id": ""
            },
            "gpu_acceleration": {
                "enabled": True
            }
```

---

## TASK 3 — `app.py`: tambah method baru `get_jamendo_tracks()`

Cari blok ini di `app.py` (akhir method `get_repliz_tiktok_music`, sebelum `get_campaigns`), PERSIS seperti ini:

```python
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_campaigns(self):
```

GANTI jadi (nambahin method baru DI ANTARA dua baris itu; blok `except`/`return` di atas dan `def get_campaigns` di bawah **TIDAK diubah**, cuma disisipin di tengah):

```python
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_jamendo_tracks(self, tags="", speed="", target_duration=30):
        """Cari track musik instrumental dari Jamendo yang aman dipakai komersial:
        sudah difilter instrumental-only, lisensi bukan Non-Commercial, dan boleh
        di-download. Filter durasi dilakukan di sisi kita sendiri (bukan parameter
        API) biar dijamin benar, lalu diurutkan dari yang durasinya paling deket ke
        target_duration.

        Args:
            tags: string tag mood/genre bahasa Inggris, dipisah spasi, contoh
                "happy upbeat" (dikirim sebagai parameter fuzzytags ke Jamendo)
            speed: salah satu dari "verylow","low","medium","high","veryhigh", atau
                "" buat skip filter tempo
            target_duration: perkiraan durasi clip (detik) — track yang lebih
                PENDEK dari ini otomatis dibuang (gak cukup buat di-trim jadi window
                sepanjang durasi clip)

        Returns:
            {"status": "ok", "tracks": [ {id, name, artist, duration, license_ccurl,
                audiodownload, waveform}, ... ]} — sudah terurut, kandidat terbaik di depan
            atau
            {"status": "error", "message": "..."}
        """
        try:
            cfg = self._get_cfg()
            jamendo_cfg = cfg.get("jamendo", {})
            client_id = jamendo_cfg.get("client_id")

            if not client_id:
                return {"status": "error", "message": "Jamendo client_id belum diisi di Settings"}

            import requests
            url = "https://api.jamendo.com/v3.0/tracks/"
            target_duration = int(target_duration) if target_duration else 30
            params = {
                "client_id": client_id,
                "format": "json",
                "limit": 30,
                "vocalinstrumental": "instrumental",
                "include": "musicinfo",
                "audioformat": "mp32",
                "audiodlformat": "mp32"
            }
            if tags:
                params["fuzzytags"] = tags
            if speed:
                params["speed"] = speed

            response = requests.get(url, params=params, timeout=15)

            if response.status_code != 200:
                return {"status": "error", "message": f"HTTP {response.status_code}"}

            data = response.json()
            results = data.get("results", [])

            tracks = []
            for t in results:
                if not t.get("audiodownload_allowed"):
                    continue
                license_url = t.get("license_ccurl") or ""
                license_segments = license_url.rstrip("/").split("/")
                license_code = license_segments[-2].lower() if len(license_segments) >= 2 else ""
                if "nc" in license_code.split("-"):
                    continue
                duration = t.get("duration") or 0
                if duration and duration < target_duration:
                    continue
                tracks.append({
                    "id": t.get("id"),
                    "name": t.get("name"),
                    "artist": t.get("artist_name"),
                    "duration": duration,
                    "license_ccurl": t.get("license_ccurl"),
                    "audiodownload": t.get("audiodownload"),
                    "waveform": t.get("waveform")
                })

            tracks.sort(key=lambda x: (x["duration"] or 0) - target_duration)

            return {"status": "ok", "tracks": tracks}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_campaigns(self):
```

---

## TASK 4 — `app.py`: ganti total `_select_background_sound()` jadi 3 method baru

Cari method ini di `app.py` (PERSIS, termasuk baris kosong setelahnya sebelum `def confirm_distribution`):

```python
    def _select_background_sound(self, transcript, title, hook_text, tracks):
        """AI pilih 1 track trending paling cocok buat 1 clip, berdasarkan isi clip.

        Args:
            transcript: potongan transcript clip (dari data.json, field "transcript")
            title: judul clip
            hook_text: hook clip
            tracks: list track dari get_repliz_tiktok_music() -> tracks

        Returns:
            dict {"id","artist","name","thumbnail"} kalau AI berhasil pilih 1 track valid
            None kalau gagal / tidak ada track cocok / API key belum diset
        """
        if not tracks:
            return None
        try:
            cfg = self._get_cfg()
            provider = cfg.get("ai_providers", {}).get("highlight_finder", {})
            api_key = provider.get("api_key")
            base_url = provider.get("base_url")
            model = provider.get("model")
            if not api_key:
                return None

            track_list_text = "\n".join(
                f'- id="{t["id"]}" | "{t.get("name","")}" by {t.get("artist","")}'
                for t in tracks[:20] if t.get("id")
            )
            if not track_list_text:
                return None

            from openai import OpenAI
            client = OpenAI(api_key=api_key, base_url=base_url)
            messages = [
                {"role": "system", "content": (
                    'Kamu memilih 1 lagu trending TikTok yang paling cocok jadi backsound '
                    'untuk sebuah clip video, berdasarkan isi/mood clip tersebut. '
                    'HANYA balas JSON persis format ini, tanpa teks lain: {"id": "..."}\n'
                    'id HARUS persis salah satu id dari daftar yang diberikan. '
                    'Kalau tidak ada yang cocok sama sekali, balas {"id": ""}.'
                )},
                {"role": "user", "content": (
                    f"Judul clip: {title}\n"
                    f"Hook: {hook_text}\n"
                    f"Transcript clip: {(transcript or '')[:1500]}\n\n"
                    f"Daftar lagu trending:\n{track_list_text}"
                )}
            ]
            response = client.chat.completions.create(model=model, messages=messages, temperature=0.3)
            raw = response.choices[0].message.content.strip()
            if raw.startswith("```json"):
                raw = raw[7:]
            if raw.endswith("```"):
                raw = raw[:-3]
            picked = json.loads(raw.strip())
            picked_id = picked.get("id")
            if not picked_id:
                return None
            for t in tracks:
                if t.get("id") == picked_id:
                    return {"id": t["id"], "artist": t.get("artist", ""), "name": t.get("name", ""), "thumbnail": t.get("thumbnail", "")}
            return None
        except Exception:
            return None

```

GANTI TOTAL jadi 3 method ini (tetap di posisi yang sama, tepat sebelum `def confirm_distribution`):

```python
    def _select_background_sound(self, transcript, title, hook_text, clip_duration):
        """AI tentuin mood/tempo/volume musik yang cocok buat 1 clip ('feeling editor'),
        cari track instrumental berlisensi aman dari Jamendo sesuai kriteria itu, lalu
        hitung titik potong (start-end detik) paling energic dari waveform track yang
        kepilih.

        Args:
            transcript: potongan transcript clip (dari data.json, field "transcript")
            title: judul clip
            hook_text: hook clip
            clip_duration: durasi clip dalam detik (dari data.json, field "duration_seconds")

        Returns:
            dict {"id","name","artist","license_ccurl","audiodownload","start","end","volume"}
            kalau berhasil, None kalau gagal / gak ada track cocok / API key belum diset /
            clip_duration gak valid
        """
        if not clip_duration or clip_duration <= 0:
            return None
        try:
            cfg = self._get_cfg()
            provider = cfg.get("ai_providers", {}).get("highlight_finder", {})
            api_key = provider.get("api_key")
            base_url = provider.get("base_url")
            model = provider.get("model")
            if not api_key:
                return None

            from openai import OpenAI
            client = OpenAI(api_key=api_key, base_url=base_url)
            messages = [
                {"role": "system", "content": (
                    'Kamu editor audio yang nentuin mood musik latar buat sebuah clip '
                    'video pendek, berdasarkan isi/mood clip tersebut. '
                    'HANYA balas JSON persis format ini, tanpa teks lain: '
                    '{"tags": "kata1 kata2", "speed": "low", "volume": 0.15}\n'
                    '"tags" adalah 1-3 kata bahasa Inggris buat mood/genre musik '
                    'instrumental (contoh: "happy upbeat", "sad emotional", "epic '
                    'cinematic"). '
                    '"speed" HARUS salah satu dari: "verylow","low","medium","high",'
                    '"veryhigh". '
                    '"volume" adalah level volume musik relatif ke suara asli clip, '
                    'angka antara 0.05 dan 0.4 (makin banyak dialog/narasi di '
                    'transcript, makin kecil volumenya, biar suara asli tetap jelas '
                    'kedengeran).'
                )},
                {"role": "user", "content": (
                    f"Judul clip: {title}\n"
                    f"Hook: {hook_text}\n"
                    f"Transcript clip: {(transcript or '')[:1500]}"
                )}
            ]
            response = client.chat.completions.create(model=model, messages=messages, temperature=0.3)
            raw = response.choices[0].message.content.strip()
            if raw.startswith("```json"):
                raw = raw[7:]
            if raw.endswith("```"):
                raw = raw[:-3]
            decision = json.loads(raw.strip())
            tags = decision.get("tags", "")
            speed = decision.get("speed", "")
            try:
                volume = max(0.05, min(0.4, float(decision.get("volume", 0.15))))
            except Exception:
                volume = 0.15

            jamendo_res = self.get_jamendo_tracks(tags=tags, speed=speed, target_duration=clip_duration)
            if jamendo_res.get("status") != "ok":
                return None
            candidates = jamendo_res.get("tracks", [])
            if not candidates:
                return None

            track = candidates[0]
            if not track.get("audiodownload"):
                return None
            track_duration = track.get("duration") or clip_duration
            start, end = self._find_best_music_window(track.get("waveform"), clip_duration, track_duration)

            return {
                "id": track.get("id"),
                "name": track.get("name"),
                "artist": track.get("artist"),
                "license_ccurl": track.get("license_ccurl"),
                "audiodownload": track.get("audiodownload"),
                "start": start,
                "end": end,
                "volume": volume
            }
        except Exception:
            return None

    def _find_best_music_window(self, waveform_raw, target_duration, track_duration):
        """Cari window sepanjang target_duration detik dengan energi tertinggi dari
        data waveform Jamendo (field 'peaks'), buat jadi titik potong (start,end) musik
        yang paling 'nendang' dipakai sebagai backsound — tanpa perlu download & analisis
        audio manual, karena Jamendo udah kasih peaks-nya langsung di response API.

        Args:
            waveform_raw: isi field "waveform" dari Jamendo (JSON string berisi
                {"peaks":[...]})
            target_duration: durasi clip (detik)
            track_duration: durasi total track musik (detik)

        Returns:
            (start_seconds, end_seconds) — float, sudah clamp ke batas durasi track.
            Fallback (0.0, target_duration) kalau data waveform gak ada / gagal diparse.
        """
        try:
            target_duration = max(1.0, float(target_duration))
            track_duration = max(target_duration, float(track_duration or target_duration))
            if target_duration >= track_duration:
                return 0.0, track_duration

            waveform = json.loads(waveform_raw) if isinstance(waveform_raw, str) else (waveform_raw or {})
            peaks = waveform.get("peaks", [])
            if not peaks:
                return 0.0, target_duration

            sec_per_peak = track_duration / len(peaks)
            window_size = max(1, int(target_duration / sec_per_peak))
            if window_size >= len(peaks):
                return 0.0, track_duration

            window_sum = sum(peaks[:window_size])
            best_sum = window_sum
            best_start_idx = 0
            for i in range(1, len(peaks) - window_size + 1):
                window_sum += peaks[i + window_size - 1] - peaks[i - 1]
                if window_sum > best_sum:
                    best_sum = window_sum
                    best_start_idx = i

            start = round(best_start_idx * sec_per_peak, 2)
            end = round(start + target_duration, 2)
            if end > track_duration:
                end = track_duration
                start = max(0.0, end - target_duration)
            return start, end
        except Exception:
            return 0.0, min(target_duration, track_duration)

    def _mix_music_into_video(self, video_path, music_info, clip_duration):
        """Download track musik terpilih dari Jamendo, trim ke window yang sudah
        dihitung _find_best_music_window(), lalu mix ke video pakai ffmpeg dengan
        auto-ducking (sidechaincompress) — musik otomatis pelan pas ada dialog di clip
        dan naik lagi pas jeda, plus fade in/out biar transisinya halus. Audio ASLI
        clip TETAP ADA (bukan digantikan) — cuma di-mix bareng musiknya.

        Args:
            video_path: path clip asli (Path atau str) — file ini TIDAK diubah
            music_info: dict hasil _select_background_sound() (butuh key
                audiodownload/start/end/volume)
            clip_duration: durasi clip (detik), dipakai buat hitung titik fade-out

        Returns:
            (output_path, tmp_dir) kalau berhasil — output_path (Path) adalah video
                baru hasil mixing, tmp_dir (Path) adalah folder temp yang HARUS
                dihapus caller pakai shutil.rmtree() setelah selesai dipakai (upload).
            (None, tmp_dir_or_None) kalau gagal di step manapun — tmp_dir tetap
                dibalikin (bisa None) supaya caller tetap bisa cleanup kalau folder
                sempat kebuat.
        """
        import tempfile
        try:
            tmp_dir = Path(tempfile.mkdtemp(prefix="ssrclip_music_"))
        except Exception:
            return None, None

        try:
            music_local = tmp_dir / "music_src.mp3"
            resp = requests.get(music_info["audiodownload"], timeout=60, stream=True)
            if resp.status_code != 200:
                return None, tmp_dir
            with open(music_local, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)

            output_path = tmp_dir / f"mixed_{Path(video_path).name}"
            ffmpeg_path = get_ffmpeg_path()
            fade_out_start = max(0.0, float(clip_duration) - 1.0)
            filter_complex = (
                "[0:a]asplit=2[voice_main][voice_sc];"
                f"[1:a]volume={music_info['volume']},afade=t=in:st=0:d=1,"
                f"afade=t=out:st={fade_out_start}:d=1[music_pre];"
                "[music_pre][voice_sc]sidechaincompress=threshold=0.02:ratio=8:"
                "attack=50:release=400[music_ducked];"
                "[voice_main][music_ducked]amix=inputs=2:duration=first:"
                "dropout_transition=0[aout]"
            )
            cmd = [
                ffmpeg_path, "-y",
                "-i", str(video_path),
                "-ss", str(music_info["start"]), "-to", str(music_info["end"]),
                "-i", str(music_local),
                "-filter_complex", filter_complex,
                "-map", "0:v", "-map", "[aout]",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                str(output_path)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            if result.returncode != 0 or not output_path.exists():
                return None, tmp_dir
            return output_path, tmp_dir
        except Exception:
            return None, tmp_dir

```

**PENTING soal method ke-3 (`_mix_music_into_video`):** kalau clip aslinya gak punya audio track sama sekali (kasus langka), ffmpeg bakal gagal di filter `[0:a]` dan `returncode != 0` — ini SUDAH DITANGANI dengan baik (fallback ke `None, tmp_dir`, yang di TASK 5 bikin proses lanjut upload TANPA musik, bukan crash). Gak perlu ditambah penanganan khusus lagi.

---

## TASK 5 — `app.py`: ganti body `confirm_distribution()`

Cari method ini di `app.py` PERSIS seperti ini (dari `def confirm_distribution` sampai akhir blok `if/else` sukses-gagal — baris setelah ini, mulai dari `if "scheduled_uploads" not in cdata:`, JANGAN disentuh, biarkan seperti aslinya):

```python
    def confirm_distribution(self, assignments):
        """Menerima hasil preview: upload video ke Repliz Storage, pilih background
        sound pakai AI, lalu buat scheduled post lewat Repliz Schedule API.
        Update data.json dengan hasil akhirnya (sukses/gagal), bukan cuma status lokal."""
        import uuid
        from datetime import datetime

        updated_clips = 0
        cfg = self._get_cfg()
        repliz_cfg = cfg.get("repliz", {})
        access_key = repliz_cfg.get("access_key")
        secret_key = repliz_cfg.get("secret_key")

        # Ambil daftar musik trending SEKALI untuk semua clip di batch upload ini
        music_tracks = []
        if access_key and secret_key:
            music_res = self.get_repliz_tiktok_music()
            if music_res.get("status") == "ok":
                music_tracks = music_res.get("tracks", [])

        try:
            all_clips = self.get_stock_clips()
            clip_path_map = {c["id"]: c["path"] for c in all_clips}

            for asn in assignments:
                clip_id = asn.get("clip_id")
                clip_path_str = clip_path_map.get(clip_id) or asn.get("clip_path")
                if not clip_path_str:
                     continue

                clip_path = Path(clip_path_str)
                data_json_path = clip_path.parent / "data.json"

                if not data_json_path.exists():
                     data_json_path = clip_path.parent.parent / "data.json"
                     if not data_json_path.exists():
                         continue

                with open(data_json_path, 'r', encoding='utf-8') as f:
                     cdata = json.load(f)

                caption = self._build_caption(asn.get("campaign_id"))
                platform = asn.get("platform", "repliz")

                entry = {
                    "id": f"sched_{uuid.uuid4().hex[:8]}",
                    "campaign_id": asn.get("campaign_id", ""),
                    "account_id": asn.get("account_id"),
                    "platform": platform,
                    "scheduled_at": asn.get("scheduled_at"),
                    "status": "terjadwal",
                    "attempted_at": None,
                    "error_message": None,
                    "caption": caption
                }

                entry["attempted_at"] = datetime.now().isoformat()
                if not access_key or not secret_key:
                    entry["status"] = "gagal"
                    entry["error_message"] = "Repliz keys not configured"
                else:
                    uploader = ReplizUploaderAdapter(access_key, secret_key)
                    storage_ok, storage_result = uploader.upload_video_to_storage(str(clip_path))
                    if not storage_ok:
                        entry["status"] = "gagal"
                        entry["error_message"] = storage_result
                    else:
                        media_url = storage_result
                        music = None
                        if music_tracks:
                            music = self._select_background_sound(
                                cdata.get("transcript", ""),
                                cdata.get("title", ""),
                                cdata.get("hook_text", ""),
                                music_tracks
                            )
                        if music:
                            entry["music_attached"] = {
                                "id": music["id"], "name": music["name"], "artist": music["artist"]
                            }

                        try:
                            sched_dt = datetime.fromisoformat(asn.get("scheduled_at"))
                            schedule_at_iso = sched_dt.strftime('%Y-%m-%dT%H:%M:%S.000Z')
                        except Exception:
                            schedule_at_iso = datetime.now().strftime('%Y-%m-%dT%H:%M:%S.000Z')

                        success, result = uploader.create_schedule(
                            account_id=asn.get("account_id"),
                            title=cdata.get("title", ""),
                            description=caption,
                            media_url=media_url,
                            schedule_at_iso=schedule_at_iso,
                            music=music
                        )
                        if success:
                            entry["status"] = "sukses"
                            entry["repliz_schedule_id"] = result
                        else:
                            entry["status"] = "gagal"
                            entry["error_message"] = result
```

GANTI TOTAL jadi ini:

```python
    def confirm_distribution(self, assignments):
        """Menerima hasil preview: pilih & mix background sound dari Jamendo ke video
        (lokal, pakai ffmpeg, audio asli TETAP ADA), upload video hasil mixing ke
        Repliz Storage, lalu buat scheduled post lewat Repliz Schedule API. Update
        data.json dengan hasil akhirnya (sukses/gagal), bukan cuma status lokal."""
        import uuid
        import shutil
        from datetime import datetime

        updated_clips = 0
        cfg = self._get_cfg()
        repliz_cfg = cfg.get("repliz", {})
        access_key = repliz_cfg.get("access_key")
        secret_key = repliz_cfg.get("secret_key")

        try:
            all_clips = self.get_stock_clips()
            clip_path_map = {c["id"]: c["path"] for c in all_clips}

            for asn in assignments:
                clip_id = asn.get("clip_id")
                clip_path_str = clip_path_map.get(clip_id) or asn.get("clip_path")
                if not clip_path_str:
                     continue

                clip_path = Path(clip_path_str)
                data_json_path = clip_path.parent / "data.json"

                if not data_json_path.exists():
                     data_json_path = clip_path.parent.parent / "data.json"
                     if not data_json_path.exists():
                         continue

                with open(data_json_path, 'r', encoding='utf-8') as f:
                     cdata = json.load(f)

                caption = self._build_caption(asn.get("campaign_id"))
                platform = asn.get("platform", "repliz")

                entry = {
                    "id": f"sched_{uuid.uuid4().hex[:8]}",
                    "campaign_id": asn.get("campaign_id", ""),
                    "account_id": asn.get("account_id"),
                    "platform": platform,
                    "scheduled_at": asn.get("scheduled_at"),
                    "status": "terjadwal",
                    "attempted_at": None,
                    "error_message": None,
                    "caption": caption
                }

                entry["attempted_at"] = datetime.now().isoformat()
                if not access_key or not secret_key:
                    entry["status"] = "gagal"
                    entry["error_message"] = "Repliz keys not configured"
                else:
                    uploader = ReplizUploaderAdapter(access_key, secret_key)

                    # Pilih musik dari Jamendo + mix lokal ke video pakai ffmpeg SEBELUM
                    # upload, biar audio asli clip + musik nyatu jadi satu file. Kalau
                    # gagal di step manapun (gak ada API key, gak ada track cocok, ffmpeg
                    # error, dst), fallback upload clip ASLI tanpa musik — upload tetap
                    # jalan, cuma tanpa backsound.
                    upload_source = clip_path
                    tmp_dir = None
                    clip_duration = cdata.get("duration_seconds", 0)
                    music = self._select_background_sound(
                        cdata.get("transcript", ""),
                        cdata.get("title", ""),
                        cdata.get("hook_text", ""),
                        clip_duration
                    )
                    if music:
                        mixed_path, tmp_dir = self._mix_music_into_video(clip_path, music, clip_duration)
                        if mixed_path:
                            upload_source = mixed_path
                            entry["music_attached"] = {
                                "id": music["id"], "name": music["name"], "artist": music["artist"],
                                "license_ccurl": music["license_ccurl"]
                            }
                            if music.get("name") and music.get("artist"):
                                attribution = f"🎵 {music['name']} by {music['artist']} (Jamendo)"
                                caption = f"{caption}\n\n{attribution}" if caption else attribution
                                entry["caption"] = caption
                        else:
                            music = None

                    storage_ok, storage_result = uploader.upload_video_to_storage(str(upload_source))

                    if tmp_dir:
                        shutil.rmtree(tmp_dir, ignore_errors=True)

                    if not storage_ok:
                        entry["status"] = "gagal"
                        entry["error_message"] = storage_result
                    else:
                        media_url = storage_result

                        try:
                            sched_dt = datetime.fromisoformat(asn.get("scheduled_at"))
                            schedule_at_iso = sched_dt.strftime('%Y-%m-%dT%H:%M:%S.000Z')
                        except Exception:
                            schedule_at_iso = datetime.now().strftime('%Y-%m-%dT%H:%M:%S.000Z')

                        success, result = uploader.create_schedule(
                            account_id=asn.get("account_id"),
                            title=cdata.get("title", ""),
                            description=caption,
                            media_url=media_url,
                            schedule_at_iso=schedule_at_iso
                        )
                        if success:
                            entry["status"] = "sukses"
                            entry["repliz_schedule_id"] = result
                        else:
                            entry["status"] = "gagal"
                            entry["error_message"] = result
```

**Catatan penting:** parameter `music=music` di pemanggilan `uploader.create_schedule(...)` SENGAJA DIHAPUS (dibanding kode lama) — karena sekarang musik udah dibakar ke video-nya langsung, bukan dikirim lewat API `additionalInfo.music` lagi. `create_schedule()` sendiri (method-nya, bukan pemanggilnya) **TIDAK PERLU DIUBAH** — dia udah otomatis handle `music=None` (default parameternya) dengan benar dari fix sebelumnya.

---

## ATURAN KETAT

- JANGAN ubah `create_schedule()`, `get_repliz_tiktok_music()`, `upload_video_to_storage()`, `_build_caption()`, `get_stock_clips()`, `preview_distribution()`, `_upload_scheduler()`, `upload_clip()` — semua itu di luar scope, JANGAN disentuh. (`get_repliz_tiktok_music()` sengaja DIBIARKAN ada walau gak dipanggil lagi dari `confirm_distribution()` — gak perlu dihapus, cukup jadi kode gak terpakai.)
- JANGAN ubah apapun di folder `web/` (frontend) — MD ini backend-only.
- JANGAN nambahin baris apapun ke `requirements.txt` / `requirements_web.txt` — semua dependency yang dipakai udah ada.
- Kalau ketemu bagian source code yang TIDAK PERSIS sama dengan blok "Kode SEKARANG" di atas — STOP, JANGAN ditebak-tebak, laporkan balik teks yang kamu temukan.

---

## Cara Test

1. **WAJIB langkah manual dulu (gak ada UI Settings buat ini, isi manual):** buka `config.json` (biasanya di folder app data / sebelah `app.py` pas development), cari key `"jamendo"`, isi `"client_id"` dengan Client ID dari dashboard Jamendo kamu (contoh: `997445ee`). **Client Secret & Redirect URL TIDAK PERLU diisi** — fitur ini cuma butuh Client ID.
2. Pastikan `ai_providers.highlight_finder` di Settings app masih terisi (dipakai buat AI nentuin mood musik).
3. Upload 1 clip yang transcript-nya lumayan jelas (biar AI ada bahan nentuin mood).
4. Proses upload bakal makan waktu SEDIKIT LEBIH LAMA dari sebelumnya (ada proses download musik + ffmpeg mixing sebelum upload ke storage) — ini NORMAL, bukan tanda gagal.
5. Cek `data.json` clip tersebut: `scheduled_uploads` entry terbaru harus `status: "sukses"`, ada `music_attached` (kalau musik ketemu & mixing sukses) dengan `id/name/artist/license_ccurl` terisi.
6. **Paling penting — download hasil videonya dari Repliz** (bukan cuma cek statusnya) dan putar: pastikan (a) suara asli/dialog clip MASIH ADA dan jelas kedengeran, (b) musik latar juga kedengeran dan otomatis mengecil pas ada dialog, (c) gak ada distorsi/clipping aneh di audio.
7. Cek `caption` di data.json / di Repliz — kalau ada musik yang attached, harus ada baris tambahan "🎵 [nama track] by [artist] (Jamendo)" di akhir caption.
8. Kalau musik gak nempel sama sekali (tapi upload tetep sukses) — itu fallback yang disengaja (misal AI gak nemu track cocok, atau ffmpeg gagal). Cek `error.log` di folder app buat lihat detail kalau mau debug lebih lanjut.
